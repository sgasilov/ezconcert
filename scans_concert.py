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
from message_dialog import info_message, error_message, warning_message
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
                          exp_time, x0, width, y0, height):
        try:
            self.camera.trigger_source = self.camera.trigger_sources.SOFTWARE
            self.camera.acquire_mode = self.camera.uca.enum_values.acquire_mode.AUTO
            self.camera.buffered = buf
            self.camera.num_buffers = bufnum
            self.camera.roi_x0 = x0 * q.pixels
            self.camera.roi_y0 = y0 * q.pixels
            self.camera.roi_width = width * q.pixels
            self.camera.roi_height = height * q.pixels
            # if camera.acquire_mode != camera.uca.enum_values.acquire_mode.EXTERNAL:
            #     raise ValueError('Acquire mode must be set to EXTERNAL')
            # if camera.trigger_source != camera.trigger_sources.AUTO:
            #     raise ValueError('Trigger mode must be set to AUTO')
        except:
            info_message("Can't set camera parameters")

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

    # @coroutine
    # def on_data_changed(self):
    #     while True:
    #         im = yield
    #         print("{:0.3f}".format(np.std(im)))
    #         self.data_changed_signal.emit("{:0.3f}".format(np.std(im)))


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
        self.motor = None
        self.units = None
        self.start = 0.0
        self.nsteps = 0
        self.range = 0.0
        self.endp = False
        self.step = 0.0
        self.region = None
        self.cont = False
        self.units = q.mm
        self.x = None
        self.ffc_motor = None
        self.outer_motor = None
        # acquisitions
        self.dummy_flat0_acq = Acquisition('dummy_flat_before', self.take_dummy_flats)
        self.dummy_flat1_acq = Acquisition('dummy_flat_after', self.take_dummy_flats)
        self.dummy_tomo_acq = Acquisition('dummy_tomo', self.take_dummy_tomo)
        self.dummy_dark_acq = Acquisition('dummy_dark', self.take_dummy_darks)
        self.flats0_softr = Acquisition('flats', self.take_flats_softr)
        self.flats1_softr = Acquisition('flats2', self.take_flats_softr)
        self.darks_softr = Acquisition('darks', self.take_darks_softr)
        self.tomo_softr = Acquisition('tomo', self.take_tomo_softr)
        self.tomo_softr_buf = Acquisition('tomo', self.take_tomo_softr_buf)
        self.tomo_pso_acq = Acquisition('tomo', self.take_pso_tomo)
        self.tomo_async_acq = Acquisition('tomo', self.take_async_tomo)
        self.flats0_softr_buf = Acquisition('flats', self.take_flats_softr_buf)
        self.flats1_softr_buf = Acquisition('flats2', self.take_flats_softr_buf())
        self.darks_softr_buf = Acquisition('darks', self.take_darks_softr_buf)
        self.tomo_pso_acq_buf = Acquisition('tomo', self.take_pso_tomo_buf)
        self.exp = None
        #super(Radiography, self).__init__(self.acq, walker=walker,
        #                                  separate_scans=sep_scans,
        #                                  name_fmt=name_fmt)

    ## HELPER FUNCTIONS

    def calc_step(self):
        if self.endp:
            self.region = np.linspace(self.start, self.range, self.nsteps) * self.units
            #self.step = self.range / float(self.nsteps - 1)
        else:
            self.region = np.linspace(self.start, self.range, self.nsteps, False) * self.units
            #self.step = self.range / float(self.nsteps)
        self.step = self.region[1]-self.region[0]

    def finish(self):
        self.x = self.start * self.units
        #if block:
        self.scan_param.set(self.x).join()
        #else:
        #    self.scan_param.set(self.x)

    def move(self):
        """Move to the next step."""
        self.x += self.step * self.units
        self.motor['position'].set(self.x).join()

    def take_with_beam(self, generator_caller):
        """A generator which yields frames with the shutter open. *generator_caller*
        is a callable which returns a generator yielding frames.
        """
        #self.ffcsetup.open_shutter()
        try:
            for frame in generator_caller():
                yield frame
        except:
            info_message('Error acquiring images with beam')
        #finally:
        #    self.ffcsetup.shutter.close().join()

    def take_radios(self):
        """A generator which yields radiograms."""
        self.ffcsetup.prepare_radios()
        return self.take_with_beam(self.radio_producer)

    def take_darks_softr_old(self):
        """A generator which yields dark fields."""
        self.ffcsetup.close_shutter()
        return frames(self.num_darks, self.camera)

    def take_darks_softr(self):
        """A generator which yields dark fields."""
        print("take darks")
        try:
            self.camera.trigger_source = self.camera.trigger_sources.SOFTWARE
            if self.camera.state != 'recording':
                self.camera.start_recording()
            for i in range(self.num_darks):
                time.sleep(self.dead_time/1000.0) # a small delay seems to be needed when using buffers
                self.camera.trigger()
                yield self.camera.grab()
        except Exception as exp:
            print(exp)
            info_message("Something is wrong in take_darksoftr")
        finally:
            if self.camera.state == 'recording':
                self.camera.stop_recording()

    def take_flats_softr(self):
        """A generator which yields flat fields."""
        print("take flats")
        try:
            self.ffcsetup.prepare_flats()
            self.ffcsetup.open_shutter()
            self.camera.trigger_source = self.camera.trigger_sources.SOFTWARE
            if self.camera.state != 'recording':
                self.camera.start_recording()
            for i in range(self.num_flats):
                time.sleep(self.dead_time/1000.0)
                self.camera.trigger()
                yield self.camera.grab()
        except Exception as exp:
            print(exp)
            info_message("Something is wrong in take_flats_softr")
        finally:
            if self.camera.state == 'recording':
                self.camera.stop_recording()
            self.ffcsetup.close_shutter()
            self.ffcsetup.prepare_radios()

    def take_tomo_softr(self):
        print("take tomo")
        try:
            self.motor.stepvelocity = 5.0 * q.deg / q.sec
            self.ffcsetup.open_shutter()
            if self.camera.state != 'recording':
                self.camera.start_recording()
            for pos in self.region:
                self.motor['position'].set(pos).join()
                self.camera.trigger()
                yield self.camera.grab()
        except Exception as exp:
            print(exp)
            info_message("Something is wrong in take_tomo_softr")
        finally:
            self.ffcsetup.close_shutter()
            self.camera.stop_recording()

    def take_tomo_softr_buf(self):
        print("take tomo (buffer)")
        try:
            self.motor.stepvelocity = 5.0 * q.deg/q.sec
            self.ffcsetup.open_shutter()
            if self.camera.state != 'recording':
                self.camera.start_recording()
            for pos in self.region:
                self.motor['position'].set(pos).join()
                self.camera.trigger()
            self.camera.stop_recording()
            self.ffcsetup.close_shutter()
            self.camera.start_readout()
            for i in range(self.nsteps):
                yield self.camera.grab()
            self.camera.stop_readout()
        except Exception as exp:
            print(exp)
            info_message("Something is wrong in take_tomo_softr")

    def take_darks_softr_buf(self):
        """A generator which yields dark fields."""
        print("take darks (buffer)")
        try:
            self.camera.trigger_source = self.camera.trigger_sources.SOFTWARE
            if self.camera.state != 'recording':
                self.camera.start_recording()
            for i in range(self.num_darks):
                time.sleep(self.dead_time/1000.0)
                self.camera.trigger()
            if self.camera.state == 'recording':
                self.camera.stop_recording()
            self.camera.start_readout()
            for i in range(self.num_darks):
                yield self.camera.grab()
            self.camera.stop_readout()
        except Exception as exp:
            print(exp)
            info_message("Something is wrong in take_darksoftr")


    def take_flats_softr_buf(self):
        """A generator which yields flat fields."""
        print("take flats (buffer)")
        try:
            self.ffcsetup.prepare_flats()
            self.ffcsetup.open_shutter()
            self.camera.trigger_source = self.camera.trigger_sources.SOFTWARE
            if self.camera.state != 'recording':
                self.camera.start_recording()
            for i in range(self.num_flats):
                time.sleep(self.dead_time/1000.0)
                self.camera.trigger()
            if self.camera.state == 'recording':
                self.camera.stop_recording()
            self.ffcsetup.close_shutter()
            self.camera.start_readout()
            for i in range(self.num_flats):
                yield self.camera.grab()
            self.camera.stop_readout()
        except Exception as exp:
            print(exp)
            info_message("Something is wrong in take_flats_softr")
        finally:
            self.ffcsetup.prepare_radios()


    ## DUMMY ACQUISIONS
    def take_dummy_tomo(self):
        try:
            self.camera.start_recording()
            for pos in self.region:
                self.motor['position'].set(pos).join()
        #    for i in range(5):
                self.camera.trigger()
                yield self.camera.grab()
        except:
            error_message("Something is wrong in dummy tomo acq")
        finally:
            self.camera.stop_recording()
        #finally:
        #self.motor.position.set(start).join()

    def take_dummy_flats(self):
        for i in range(self.num_flats):
            yield self.camera.grab()
            sleep(0.5)

    def take_dummy_darks(self):
        for i in range(self.num_darks):
            yield self.camera.grab()
            sleep(0.5)

    def take_pso_tomo(self):
        print("start PSO")
        try:
            self.ffcsetup.open_shutter()
            self.motor.stepvelocity = self.motor.calc_vel(self.nsteps, self.exp_time + self.dead_time, self.range)
            self.motor.stepangle = float(self.range) / float(self.nsteps) * q.deg
            # can lose steps at the start so go a bit further to ensure full number of steps
            # remove this if a PSO window is used
            self.motor.LENGTH = (self.range + 5*float(self.range) / float(self.nsteps)) * q.deg
            print("Velocity: {}, Step: {}, Range: {}".format(self.motor.stepvelocity, self.motor.stepangle, self.motor.LENGTH))
            self.camera.trigger_source = self.camera.trigger_sources.EXTERNAL
            self.camera.start_recording()
            self.motor.PSO_pulse(False).join()
            time.sleep(1)
            for i in range(self.nsteps):
                # print("snap:{}".format(i))
                yield self.camera.grab()
        except Exception as exp:
            print(exp)
            error_message("Problem in PSO scan")
        finally:
            self.camera.stop_recording()
            self.ffcsetup.close_shutter()

    def take_pso_tomo_buf(self):
        print("start PSO (buffer)")
        try:
            self.ffcsetup.open_shutter()
            self.motor.stepvelocity = self.motor.calc_vel(self.nsteps, self.exp_time + self.dead_time, self.range)
            self.motor.stepangle = float(self.range) / float(self.nsteps) * q.deg
            self.motor.LENGTH = (self.range + 5*float(self.range) / float(self.nsteps)) * q.deg
            print("Velocity: {}, Step: {}, Range: {}".format(self.motor.stepvelocity, self.motor.stepangle, self.motor.LENGTH))
            self.camera.trigger_source = self.camera.trigger_sources.EXTERNAL
            self.camera.start_recording()
            self.motor.PSO_pulse(False).join()
            self.camera.stop_recording()
            self.ffcsetup.close_shutter()
            time.sleep(1)
            self.camera.start_readout()
            for i in range(self.nsteps):
                yield self.camera.grab()
            self.camera.stop_readout()
            self.camera.start_recording()
        except Exception as exp:
            print(exp)
            error_message("Problem in PSO scan")


    def take_async_tomo(self):
        print("start async scan")
        try:
            self.ffcsetup.open_shutter()
            velocity = self.motor.calc_vel(self.nsteps, self.exp_time + self.dead_time, self.range)
            self.motor["velocity"].set(velocity ).join()
            print("constant velocity: {}".format(self.motor._is_velocity_stable()))
            self.camera.trigger_source = self.camera.trigger_sources.AUTO
            self.camera.buffered = False
            with self.camera.recording():
                time.sleep((self.range / velocity.m))
            #self.camera.stop_recording()
            self.ffcsetup.close_shutter()
            self.motor["velocity"].set(0.0 * q.deg / q.sec).join()
            print("Number of Images: {}".format(self.camera.recorded_frames))
            self.camera.start_readout()
            for i in range(self.nsteps):
                yield self.camera.grab()
            self.camera.stop_readout()
        except Exception as exp:
            print(exp)
            error_message("Problem in sync scan")


class FFCsetup(object):

    """
    Provided by Tomas Farago, KIT
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



