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
from concert.experiments.imaging import (
    tomo_projections_number, tomo_max_speed, frames)
from concert.devices.cameras.base import CameraError
from concert.devices.cameras.pco import Timestamp
from concert.devices.cameras.uca import Camera as UcaCamera
from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject
from concert.coroutines.base import coroutine, inject
from concert.experiments.addons import Consumer, ImageWriter
from message_dialog import info_message, error_message, warning_message
from concert.storage import DirectoryWalker



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
        # Collection of acquisitions we create it once
        self.acq_setup = ACQsetup(self.camera, self.ffc_setup)
        self.exp = None  # That is experiment. We create it each time before run is pressed
        # before that all camera, acquisition, and ffc parameters must be set according to the
        # user input and consumers must be attached
        self.cons_viewer = None
        self.cons_writer = None
        self.thread_running = True
        atexit.register(self.stop)
        self.starting_scan = False
        self.running_experiment = None

    def create_experiment(self, acquisitions, ctsetname, sep_scans):
        self.exp = Experiment(acquisitions=acquisitions,
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
            pass
            # info_message("Can't set camera parameters")

        self.camera.exposure_time = exp_time * q.msec

    def stop(self):
        self.thread_running = False
        self.wait()

    def run(self):  # .start() calls this function
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


class ACQsetup(object):

    """This is Class which holds a collection of acqusitions
    (each acquisition moves motors and get frames from camera)
    and all parameters which acquisitions require
    """

    def __init__(self, camera, ffcsetup):
        self.ffcsetup = ffcsetup
        self.camera = camera
        self.num_darks = 0
        self.num_flats = 0
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
        # flats/darks (always softr with immidiate transfer)
        self.flats_softr = Acquisition('flats', self.take_flats_softr)
        self.flats2_softr = Acquisition('flats2', self.take_flats_softr)
        self.darks_softr = Acquisition('darks', self.take_darks_softr)
        # softr
        self.tomo_softr = Acquisition('tomo', self.take_tomo_softr)
        # auto
        self.tomo_async_acq = Acquisition('tomo', self.take_async_tomo)
        # external
        self.tomo_pso_acq = Acquisition('tomo', self.take_pso_tomo)
        self.tomo_pso_acq_buf = Acquisition('tomo', self.take_pso_tomo_buf)
        # tests of sync with top-up inj cycles
        self.rec_seq_with_inj_sync = Acquisition('seq', self.test_rec_seq_with_sync)
        # pulses only
        self.ttl_acq = Acquisition('ttl', self.take_ttl_tomo)


        self.exp = None
        self.top_up_veto_enabled = False
        self.top_up_veto_state = False
        self.message_entry = None

    # HELPER FUNCTIONS

    def calc_step(self):
        if self.endp:
            self.region = np.linspace(self.start, self.start+self.range, self.nsteps)
        else:
            self.region = np.linspace(self.start, self.start+self.range,
                                      self.nsteps, False)
        self.region *= self.units
        self.step = self.region[1]-self.region[0]

    # Use software trigger
    def take_darks_softr(self):
        try:
            self.ffcsetup.close_shutter()
            sleep(1)  # to get rid of possible afterglow
        except:
            info_message("Cannot close shutter in take_darks_softr")
        try:
            if self.camera.state == 'recording':
                self.camera.stop_recording()
            self.camera.trigger_source = self.camera.trigger_sources.SOFTWARE
            self.camera.start_recording()
            sleep(0.01)
        except:
            info_message("Something is wrong with setting camera params for take_darks_softr")
        try:
            for i in range(self.num_darks):
                self.camera.trigger()
                yield self.camera.grab()
        except Exception as exp:
            info_message("Something is wrong in take_darks_softr")
        finally:
            self.camera.stop_recording()

    def take_flats_softr(self):
        try:
            self.ffcsetup.prepare_flats()
            self.ffcsetup.open_shutter()
        except:
            info_message("Something is wrong in preparations for take_flats_softr")
        try:
            if self.camera.state == 'recording':
                self.camera.stop_recording()
            self.camera.trigger_source = self.camera.trigger_sources.SOFTWARE
            self.camera.start_recording()
            sleep(0.01)
        except:
            info_message("Something is wrong with setting camera params in take_flats_softr")
        try:
            for i in range(self.num_flats):
                self.camera.trigger()
                yield self.camera.grab()
        except Exception as exp:
            info_message("Something is wrong during acquisition of flats")
        finally:
            self.camera.stop_recording()
            self.ffcsetup.close_shutter()
            self.ffcsetup.prepare_radios()

    def take_tomo_softr(self):
        """A generator which yields projections."""
        try:
            self.motor.stepvelocity = 5.0 * q.deg / q.sec
            self.ffcsetup.open_shutter()
            if self.camera.state == 'recording':
                self.camera.stop_recording()
            self.camera.trigger_source = self.camera.trigger_sources.SOFTWARE
            self.camera.start_recording()
            sleep(0.01)
        except:
            info_message("Something is wrong in preparations for take_tomo_softr")
        try:
            for pos in self.region:
                # while True:
                #    if self.top_up_veto_state:
                #        sleep(0.1)
                #    else:
                self.motor['position'].set(pos).join()
                self.camera.trigger()
                yield self.camera.grab()
                #        break
        except Exception as exp:
            info_message("Something is wrong during take_tomo_softr")
        finally:
            self.ffcsetup.close_shutter()
            self.camera.stop_recording()
            # return to start position with a small overshoot to
            # maintain unidirectional repeatability
            self.motor['position'].set(self.start-self.step).join()

    # Use software trigger. Use buffers and read during acquisition.

    # Use software trigger. Use buffer and read after acquisition.

    def take_tomo_softr_buf2(self):
        """A generator which yields projections. Use buffer and read after scan"""
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
            info_message("Something is wrong in take_tomo_softr_buf2")

    # Use hardware trigger

    def take_pso_tomo(self):
        """A generator which yields projections. Use triggers generated using PSO function from stage."""
        print("start PSO")
        try:
            if self.camera.state == 'recording':
                self.camera.stop_recording()
            self.ffcsetup.open_shutter()
            self.motor['stepvelocity'].set(self.motor.calc_vel(
                self.nsteps, self.exp_time + self.dead_time, self.range)).result()
            self.motor['stepangle'].set(float(self.range) / float(self.nsteps) * q.deg).result()
            # can lose steps at the start so go a bit further to ensure full number of steps
            # remove this if a PSO window is used
            self.motor.LENGTH = self.range * q.deg
            print("Velocity: {}, Step: {}, Range: {}".format(
                self.motor.stepvelocity, self.motor.stepangle, self.motor.LENGTH))
            self.camera.trigger_source = self.camera.trigger_sources.EXTERNAL
        except Exception as exp:
            print(exp)
            error_message("Something is wrong in preparations for PSO scan")
        try:
            self.camera.start_recording()
            sleep(0.01)
            self.motor.PSO_multi(False).join()
            for i in range(self.nsteps):
                yield self.camera.grab()
        except Exception as exp:
            print(exp)
            error_message("Problem in PSO scan")
        finally:
            try:
                self.camera.stop_recording()
                self.ffcsetup.close_shutter()
                print("change velocity")
                self.motor['stepvelocity'].set(5.0 * q.deg / q.sec).result()
                print("return to start")
                self.motor['position'].set(self.start).join()
            except Exception as exp:
                print(exp)
                error_message("Something is wrong in final for PSO scan")

    take_pso_tomo_buf = take_pso_tomo

    def take_pso_tomo_buf2(self):
        print("start PSO (buffer)")
        """A generator which yields projections. Use triggers generated using PSO function from stage. Use buffer."""
        try:
            self.ffcsetup.open_shutter()
            self.motor.stepvelocity = self.motor.calc_vel(
                self.nsteps, self.exp_time + self.dead_time, self.range)
            self.motor.stepangle = float(self.range) / float(self.nsteps) * q.deg
            self.motor.LENGTH = (self.range + 5*float(self.range) /
                                 float(self.nsteps)) * q.deg
            print("Velocity: {}, Step: {}, Range: {}".format(
                self.motor.stepvelocity, self.motor.stepangle, self.motor.LENGTH))
            self.camera.trigger_source = self.camera.trigger_sources.EXTERNAL
            self.camera.start_recording()
            self.motor.PSO_multi(False).join()
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
            error_message("Problem in PSO_buf scan")

    # Asynchronous
    def take_async_tomo(self):
        """A generator which yields projections. """
        try:
            if self.camera.state == 'recording':
                self.camera.stop_recording()
            self.ffcsetup.open_shutter()
            velocity = self.motor.calc_vel(
                self.nsteps, self.exp_time + self.dead_time, self.range)
            self.camera.trigger_source = self.camera.trigger_sources.AUTO
        except Exception as exp:
            print(exp)
            error_message("Problem in setup of async scan")
        try:
            self.motor["velocity"].set(velocity).join()
            print("constant velocity: {}".format(self.motor._is_velocity_stable()))
            #self.camera.buffered = False
            with self.camera.recording():
                #time.sleep((self.range / velocity.magnitude))
                time.sleep(0.01)
                for i in range(self.nsteps):
                    yield self.camera.grab()
        except Exception as exp:
            print(exp)
            error_message("Problem in run of async scan")
        try:
            self.ffcsetup.close_shutter()
            self.motor["velocity"].set(0.0 * q.deg / q.sec).join()
        except Exception as exp:
            print(exp)
            error_message("Problem in run of async scan")

    # external camera control
    # Camera is completely external and this is only moving stages and sending triggers
    def take_ttl_tomo(self):
        """A generator that """
        print("TTL scan")
        try:
            #self.ffcsetup.prepare_flats()
            #self.ffcsetup.open_shutter()
            pass
        except Exception as exp:
            print(exp)
            info_message("Something is wrong in preparations for take_ttl_tomo")
        time_interval = self.exp_time + self.dead_time
        #print("send {} ttl pulses".format(self.num_flats))
        #self.motor.PSO_ttl(self.num_flats, time_interval.magnitude)
        try:
            #self.ffcsetup.close_shutter()
            #self.ffcsetup.prepare_radios()
            pass
        except Exception as exp:
            print(exp)
            info_message("Something is wrong in preparations for take_ttl_tomo")




    # test
    def test_rec_seq_with_sync(self):
        if self.camera.trigger_source != 'AUTO':
            self.camera.trigger_source = self.camera.trigger_sources.AUTO
        if self.top_up_veto_enabled:
            while True:
                if self.top_up_veto_state:
                    with self.camera.recording():
                        sleep(2.0)
                    break
                sleep(0.1)
        else:
            with self.camera.recording():
                sleep(2.0)
        self.camera.uca.start_readout()
        for i in range(self.nsteps):
            yield self.camera.grab()
        self.camera.uca.stop_readout()


class FFCsetup(object):

    """
    Provided by Tomas Farago, KIT
    Imaging experiments setup holds necessary devices and settings
    to perform flat-field correction.
    We create this object once but must update parameters according to the input
    each time before experiment is run
    """

    def __init__(self, shutter=None):
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
