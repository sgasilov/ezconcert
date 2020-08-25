"""CT scans with the ufo-kit Concert"""
import logging
import time
from contextlib import contextmanager
import numpy as np
import atexit
from time import sleep

from concert.async import async, wait
from concert.base import identity
from concert.quantities import q
from concert.experiments.base import Acquisition, Experiment
from concert.experiments.imaging import (tomo_projections_number, tomo_max_speed, frames)
from concert.devices.cameras.base import CameraError
from concert.devices.cameras.pco import Timestamp
from concert.devices.cameras.uca import Camera as UcaCamera
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject
from concert.coroutines.base import coroutine, inject
from concert.experiments.addons import Consumer, ImageWriter
from message_dialog import info_message
from concert.storage import DirectoryWalker
import numpy as np


def run(n, callback):
    for i in range(n):
        callback(i)
        sleep(0.5)


class ConcertScanThread(QThread):
    """
    Holds camera+viewer+viewer consumer and walker+write consumers
    Creates Concert Experiment and attaches consumers to it
    Acqusitions are selected from a collection of acquisitions predefined in Radiography class
    Acquisitons are functions which move motors and control camera
    Experiment can be run multiple times, a viewer and a file-writer are attached to it
    Parameters of Camera must be defined before calling Scan
    """
    scan_finished_signal = pyqtSignal()
    data_changed_signal = pyqtSignal(str)

    def __init__(self, viewer, camera):
        super(ConcertScanThread, self).__init__()
        self.viewer = viewer
        self.camera = camera
        self.ffc_setup = FFCsetup()
        self.acq_setup = ACQsetup(self.camera, self.ffc_setup) # Collection of acqusitions we create it once
        self.exp = None # That is experiment. We create it each time before run is pressed
        # before that all camera, acquisition, and ffc parameters must be set according to the
        # user input and consumers must be attached
        self.cons_viewer = None
        self.cons_writer = None
        self.thread_running = True
        atexit.register(self.stop)
        self.starting_scan = False
        self.running_experiment = None

    def create_experiment(self, acquisitions, ctsetname, sep_scans):
        self.exp = Experiment(acquisitions=acquisitions, \
                              walker=self.walker, separate_scans=sep_scans, name_fmt=ctsetname)

    def attach_writer(self, async=True):
        self.cons_writer = ImageWriter(self.exp.acquisitions, self.walker, async=async)

    def attach_viewer(self):
        self.cons_viewer = Consumer(self.exp.acquisitions, self.viewer)

    def set_camera_params(self, trig_mode, acq_mode,
                          buf, bufnum,
                          exp_time, x, width, y, height):
        try:
            self.setup.camera.trigger_source = trig_mode
            self.setup.camera.acquire_mode = acq_mode
            # if camera.acquire_mode != camera.uca.enum_values.acquire_mode.EXTERNAL:
            #     raise ValueError('Acquire mode must be set to EXTERNAL')
            # if camera.trigger_source != camera.trigger_sources.AUTO:
            #     raise ValueError('Trigger mode must be set to AUTO')
        except:
            pass
        self.camera.buffered = buf
        self.camera.num_buffers = bufnum
        self.camera.exposure_time = exp_time * q.msec



    def stop(self):
        self.thread_running = False
        self.wait()

    def run(self): # .start() calls this function
        while self.thread_running:
            if self.starting_scan:
                self.running_experiment = self.exp.run()
                self.starting_scan = False
            else:
                sleep(1)
                self.check_scan_state()

    def check_scan_state(self):
        if self.running_experiment is not None:
            try:
                if self.running_experiment.done():
                    self.scan_finished_signal.emit()
                    self.running_experiment = None
            except:
                pass

    def start_scan(self):
        self.starting_scan = True

    def abort_scan(self):
        try:
            self.exp.abort()
            self.running_experiment = None
        except:
            pass

    @coroutine
    def on_data_changed(self):
        while True:
            im = yield
            print("{:0.3f}".format(np.std(im)))
            self.data_changed_signal.emit("{:0.3f}".format(np.std(im)))


class ACQsetup(object):

    """This is Class which holds a collection of acqusitions
    (each acquisition moves motors and get frames from camera)
    and all parameters which acqusitions require
    """

    def __init__(self, camera, ffcsetup):
        self.ffcsetup = ffcsetup
        self.camera = camera
        self.num_darks = 0
        self.num_flats = 0
        #self.radio_producer = radio_producer
        #self.mainguicallback = callback
        # physical parameters
        self.exp_time = 0.0
        self.dead_time = 0.0
        self.inner_motor = None
        self.inner_units = None
        self.inner_start = 0.0
        self.inner_nsteps = 0
        self.inner_range = 0.0
        self.inner_endp = False
        self.inner_step = 0.0
        self.inner_cont = False
        self.inner_scan_param = None
        self.inner_units = q.mm
        self.x = None
        self.ffc_motor = None
        self.outer_motor = None
        # acquisitions
        self.flats_softr = Acquisition('flats', self.take_flats_softr)
        self.darks_softr = Acquisition('darks', self.take_darks_softr)
        self.dummy_flat_acq = Acquisition('dummy_flat', self.take_dummy)
        self.dummy_tomo_acq = Acquisition('dummy_tomo', self.take_dummy)
        self.tomo_softr_notbuf = Acquisition('tomo', self.take_tomo_softr_notbuf)
        self.tomo_softr_buf = Acquisition('tomo', self.take_tomo_softr_buf)
        self.acquisitions = []
        self.exp = None
        #super(Radiography, self).__init__(self.acq, walker=walker,
        #                                  separate_scans=sep_scans,
        #                                  name_fmt=name_fmt)

    def prepare(self):
        if self.inner_endp:
            #step = (self.maximum - self.minimum) / float(self.intervals - 1)
            self.inner_step = self.inner_range / float(self.inner_nsteps - 1)
        else:
            self.inner_step = self.inner_range / float(self.inner_nsteps)
        self.inner_scan_param = self.inner_motor['position']

    def finish(self, block=True):
        self.x = self.inner_start * self.inner_units
        if block:
            self.inner_scan_param.set(self.x).join()
        else:
            self.inner_scan_param.set(self.x)

    def move(self):
        """Move to the next step."""
        self.x += self.inner_step * self.inner_units
        self.inner_scan_param.set(self.x).join()

    def take_tomo_softr_notbuf(self):
        #self.x = self.inner_start * self.inner_units
        #self.inner_motor.position.set(self.x).join()

        for i in range(11):
            yield self.camera.grab()
            sleep(0.5)

        #return frames(self.inner_nsteps, self.camera, callback=self.move)

    def take_dummy(self):
        for i in range(11):
            yield self.camera.grab()
            sleep(0.5)

    def take_tomo_softr_buf(self):
        for i in range(self.num_flats):
            yield self.camera.grab()
            sleep(0.5)

    def take_flats_softr(self):
        for i in range(self.num_flats):
            yield self.camera.grab()
            sleep(0.5)

    def take_darks_softr(self):
        for i in range(self.num_darks):
            yield self.camera.grab()
            sleep(0.5)

class FFCsetup(object):

    """
    Written by Tomas Farago, KIT
    Imaging experiments setup holds necessary devices and settings
    to perform flat-field correction.
    We create this object once but must update parameters according to the input
    each time before experiment is run
    """

    def __init__(self, shutter = None):
        self.shutter = shutter
        self.flat_motor = None
        self.flat_position = 0.0
        self.radio_position = 0.0

    def _manipulate_shutter(self, desired_state, block=True):
        future = None
        operation = self.shutter.open if desired_state == 'open' else self.shutter.close
        if self.shutter.state != desired_state:
            future = operation()
            if block:
                future.join()

        return future

    def _manipulate_flat_motor(self, position, block=True):
        future = None
        if self.flat_motor and position is not None:
            future = self.flat_motor.set_position(position)
            if block:
                future.join()

        return future

    def open_shutter(self, block=True):
        return self._manipulate_shutter('open', block=block)

    def close_shutter(self, block=True):
        return self._manipulate_shutter('closed', block=block)

    def prepare_flats(self, block=True):
        return self._manipulate_flat_motor(self.flat_position, block=block)

    def prepare_radios(self, block=True):
        return self._manipulate_flat_motor(self.radio_position, block=block)




        #print "STD {:0.2f}".format(np.std(im))

def test(camera):
    inject((camera.grab() for i in range(10)), mystd)
    #for i in range(self.ffc_controls_group.num_flats):
    #    yield camera.grab()