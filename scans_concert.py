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
from concert.networking.base import get_tango_device
from concert.experiments.base import Acquisition, Experiment
from concert.experiments.imaging import (tomo_projections_number, tomo_max_speed, frames)
from concert.devices.cameras.base import CameraError
from concert.devices.cameras.pco import Timestamp
from concert.devices.cameras.uca import Camera as UcaCamera
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject
from concert.coroutines.base import coroutine, inject
from concert.experiments.addons import Consumer
from message_dialog import info_message
import numpy as np


def run(n, callback):
    for i in range(n):
        callback(i)
        sleep(0.5)


@coroutine
def on_data_changed():
    while True:
        im = yield
        #data_changed_signal.emit("{:0.3f}".format(np.std(im)))
        print("{:0.3f}".format(np.std(im)))
        ConcertScanThread.data_changed_signal.emit("{:0.3f}".format(np.std(im)))


class ConcertScanThread(QThread):
#class ConcertScanThread(QObject):
    """
    Creates Concert Experiment
    from Concert Acqusitions
    Acquisitons are functions which move motors and control camera
    Experiment can be run multiple times, a viewer and a file-writer are attached to it
    Parameters of Camera must be defined before calling Scan
    """
    scan_finished_signal = pyqtSignal()
    data_changed_signal = pyqtSignal(str)

    def __init__(self, viewer, camera, flat_motor=None, inner_motor=None):
        super(ConcertScanThread, self).__init__()
        print "hi"
        self.viewer = viewer
        self.camera = camera
        self.ffcsetup = FFCsetup()
        self.thread_running = True
        atexit.register(self.stop)
        self.scan_running = False
        self.exp = Radiography(self.camera, self.ffcsetup)#, callback=self.on_data_changed)
        self.cons = Consumer(self.exp.acquisitions, on_data_changed())
        #inject((camera.grab() for i in range(10)), self.on_data_changed())

    def stop(self):
        #self.thread_running = False
        self.wait()

    def run(self): # .start() calls this function
        #cons = Consumer(self.exp.acquisitions, on_data_changed())
        #inject((self.camera.grab() for i in range(10)), self.on_data_changed())
        running_experiment = self.exp.run()
        #run(10, callback=self.on_data_changed)
        while not running_experiment.done():
            sleep(1)
        self.scan_finished_signal.emit()


    # def on_data_changed(self, value, **kwargs):
    #     self.data_changed_signal.emit("{}".format(value))

class Radiography(Experiment):

    """A set of devices and acquisitions allowing to acquire radiograms with and without beam.
    .. attribute:: num_darks
    .. attribute:: num_flats
        Number of flat fields to acquire
    .. attribute:: radio_producer
        A callable which returns a generator which yields radiograms
    """

    def __init__(self, camera, FFCsetup, walker=None, separate_scans=True, num_darks=0, num_flats=0,
                 radio_producer=None, callback=None):
        self.ffcsetup = FFCsetup
        self.camera = camera
        self.num_darks = num_darks
        self.num_flats = num_flats
        self.radio_producer = radio_producer
        self.mainguicallback = callback
        # acquititions
        flats = Acquisition('flats', self.take_flats)
        acquisitions = [flats]
        #if darks_chackbox
        #    acquisitions.append(darks)
        #if flat_before:
            #acquisitions.append(flats)
        super(Radiography, self).__init__(acquisitions, walker=walker,
                                          separate_scans=separate_scans)

    def take_flats(self):
        for i in range(10):
            yield self.camera.grab()
            sleep(0.5)
            #self.mainguicallback(i)
            #info_message("Image std {:0.2f}".format(np.std(self.camera.grab())))
            #yield self.camera.grab()



class FFCsetup(object):

    """
    Written by Tomas Farago, KIT
    Imaging experiments setup holds necessary devices and settings
    to perform flat-field correction.
    """

    def __init__(self, shutter = None, flat_motor=None, flat_position=None, radio_position=None):
        self.shutter = shutter
        self.flat_motor = flat_motor
        self.flat_position = flat_position
        self.radio_position = radio_position

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