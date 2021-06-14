"""CT scans with the ufo-kit Concert"""

import time
import numpy as np
import atexit
from time import sleep
from concert.quantities import q
from concert.experiments.base import Acquisition, Experiment
from PyQt5.QtCore import QTimer, QThread, pyqtSignal
from concert.experiments.addons import Consumer, ImageWriter
from message_dialog import info_message, error_message
from edc import log

LOG = log.get_module_logger(__name__)


def run(n, callback):
    for i in range(n):
        callback(i)
        sleep(0.5)


class ConcertScanThread(QThread):
    """
    Holds camera+viewer+viewer consumer and walker+write consumers
    Creates Concert Experiment and attaches consumers to it
    Acquisitions are selected from a collection of acquisitions predefined in Radiography class
    Acquisitions are functions which move motors and control camera
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
        self.exp = Experiment(
            acquisitions=acquisitions,
            walker=self.walker,
            separate_scans=sep_scans,
            name_fmt=ctsetname,
        )

    def attach_writer(self, async=True):
        self.cons_writer = ImageWriter(self.exp.acquisitions, self.walker, async=async)

    def attach_viewer(self):
        self.cons_viewer = Consumer(self.exp.acquisitions, self.viewer)

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
                    self.detach_and_del_writer()
                    self.scan_finished_signal.emit()
                    self.running_experiment = None
            except:
                pass

    def start_scan(self):
        self.starting_scan = True

    def abort_scan(self):
        try:
            self.exp.abort()
            self.detach_and_clean()
            self.running_experiment = None
        except:
            pass

    def detach_and_del_writer(self):
        if self.cons_writer is not None:
            self.cons_writer.detach()
            del self.cons_writer
            self.cons_writer = None
        # if self.cons_viewer is not None:
        #     self.cons_viewer.detach()
        #     del self.cons_viewer
        #     self.cons_viewer = None

    def delete_exp(self):
        if self.exp is not None:
            del self.walker
        if self.exp is not None:
            del self.exp
            self.exp = None


    def remove_all_acqs(self):
        if self.exp is None:
            return
        for a in self.exp.acquisitions:
            self.exp.remove(a)

class ACQsetup(object):

    """This is Class which holds a collection of acquisitions
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
        self.flats_before = False
        self.flats_after = False
        # acquisitions
        # flats/darks (always softr with immediate transfer)
        self.flats_softr = Acquisition("flats", self.take_flats_softr)
        self.flats2_softr = Acquisition("flats2", self.take_flats_softr)
        self.darks_softr = Acquisition("darks", self.take_darks_softr)
        # softr
        self.tomo_softr = Acquisition("tomo", self.take_tomo_softr)
        # auto
        self.tomo_auto_dimax = Acquisition("tomo", self.take_tomo_auto_dimax)
        self.tomo_auto = Acquisition("tomo", self.take_tomo_auto)
        # external
        self.tomo_ext = Acquisition("tomo", self.take_tomo_ext)
        self.tomo_ext_dimax = Acquisition("tomo", self.take_tomo_ext_dimax)
        # tests of sync with top-up inj cycles
        self.rec_seq_with_inj_sync = Acquisition("seq", self.test_rec_seq_with_sync)
        # pulses only to external camera
        self.ttl_acq = Acquisition("ttl", self.take_ttl_tomo)
        #

        self.exp = None
        self.top_up_veto_enabled = False
        self.top_up_veto_state = False
        self.message_entry = None

        # TWO Variable to be read directly from GUI entries when camera is not connected
        self.ttl_exp_time = None
        self.ttl_dead_time = None

        self.timer = QTimer()
        self.glob_tmp = 0

    # HELPER FUNCTIONS

    def calc_step(self):
        if self.endp:
            self.region = np.linspace(self.start, self.start + self.range, self.nsteps)
        else:
            self.region = np.linspace(
                self.start, self.start + self.range, self.nsteps, False
            )
        self.region *= self.units
        self.step = self.region[1] - self.region[0]

    # Use software trigger
    def take_darks_softr(self):
        LOG.info("Starting acquisition: darks")
        try:
            self.ffcsetup.close_shutter()
            sleep(1)  # to get rid of possible afterglow
        except:
            info_message("Cannot close shutter in take_darks_softr")
        try:
            if self.camera.state == "recording":
                self.camera.stop_recording()
            self.camera.trigger_source = self.camera.trigger_sources.SOFTWARE
            self.camera.start_recording()
            sleep(0.01)
        except Exception as exp:
            LOG.error(exp)
            info_message(
                "Something is wrong with setting camera params for take_darks_softr"
            )
        try:
            for i in range(self.num_darks):
                self.camera.trigger()
                yield self.camera.grab()
        except Exception as exp:
            LOG.error(exp)
            info_message("Something is wrong in take_darks_softr")
        finally:
            self.camera.stop_recording()
            LOG.info("Acquired darks")

    def take_flats_softr(self):
        LOG.info("Starting acquisition: flats")
        try:
            self.ffcsetup.prepare_flats()
            self.ffcsetup.open_shutter()
        except Exception as exp:
            LOG.error(exp)
            info_message("Something is wrong in preparations for take_flats_softr")
        try:
            if self.camera.state == "recording":
                self.camera.stop_recording()
            self.camera.trigger_source = self.camera.trigger_sources.SOFTWARE
            self.camera.start_recording()
            sleep(0.01)
        except Exception as exp:
            LOG.error(exp)
            info_message(
                "Something is wrong with setting camera params in take_flats_softr"
            )
        try:
            for i in range(self.num_flats):
                self.camera.trigger()
                yield self.camera.grab()
        except Exception as exp:
            LOG.error(exp)
            info_message("Something is wrong during acquisition of flats")
        finally:
            self.camera.stop_recording()
            self.ffcsetup.close_shutter()
            self.ffcsetup.prepare_radios()
            LOG.info("Acquired flats")

    def take_tomo_softr(self):
        """A generator which yields projections."""
        LOG.info("Start acquisition: step-and-shoot scan, soft trig")
        try:
            if self.motor.name.startswith("ABRS"):
                if self.nsteps == 2:
                    self.motor["stepvelocity"].set(20.0 * q.deg / q.sec).join()
                else:
                    self.motor["stepvelocity"].set(5.0 * q.deg / q.sec).join()
            self.ffcsetup.open_shutter()
            if self.camera.state == "recording":
                self.camera.stop_recording()
            self.camera.trigger_source = self.camera.trigger_sources.SOFTWARE
            self.camera.start_recording()
            sleep(0.01)
        except Exception as exp:
            LOG.error(exp)
            info_message("Something is wrong in preparations for tomo_softr")
        try:
            for pos in self.region:
                # while True:
                #    if self.top_up_veto_state:
                #        sleep(0.1)
                #    else:
                self.motor["position"].set(pos).join()
                self.camera.trigger()
                yield self.camera.grab()
                #        break
        except Exception as exp:
            LOG.error(exp)
            info_message("Something is wrong during tomo_softr")
        try:
            self.ffcsetup.close_shutter()
            if self.camera.state == "recording":
                self.camera.stop_recording()
            # return to start position with a small overshoot to
            # maintain unidirectional repeatability
            # self.motor['position'].set(self.start-self.step).join()
            LOG.debug("returning inner motor to starting point")
            self.motor["position"].set(self.region[0]).join()
            # if self.motor.name.startswith("ABRS"):
            #     self.motor["stepvelocity"].set(5.0 * q.deg / q.sec).join()
        except Exception as exp:
            LOG.error(exp)
            info_message("Something is wrong in final in tomo_softr")

    def take_tomo_ext(self):
        LOG.info("Starting acquisition: on-the-fly scan, ext trig, libuca buffer")
        self.prep4ext_trig_scan_with_PSO()
        self.camera.start_recording()
        sleep(0.01)
        LOG.info("Sending PSO command")
        self.motor.PSO_multi(False)
        sleep(0.5) # EPICS delays? shouldn't matter for grab, but just in case
        # read-out
        LOG.info("Starting read-out from libuca buffer")
        for i in range(self.nsteps):
            yield self.camera.grab()
        LOG.info("Read-out done; finilizing acquisition")
        self.camera.stop_recording()
        self.ffcsetup.close_shutter()
        self.return_ct_stage_to_start(block=True)

    def take_tomo_ext_dimax(self):
        """A generator which yields projections. """
        LOG.info("Starting acquisition: on-the-fly scan with Dimax, ext trig, int buffer")
        self.prep4ext_trig_scan_with_PSO()
        #rotation and recording
        try:
            self.camera.start_recording()
            sleep(0.01)
            self.motor.PSO_multi(False)
            #self.motor["state"].wait("moving", sleep_time=0.1, timeout=10)
            while self.motor.state == "standby":
                sleep(0.1)
            while self.motor.state == "moving":
                sleep(0.1)
            self.camera.stop_recording()
        except Exception as exp:
            LOG.error(exp)
            tmp = "Problem during recording/rotation in PSO scan"
            LOG.error(tmp)
            error_message(tmp)
        # read-out
        if self.camera.recorded_frames.magnitude < self.nsteps:
            tmp = "Number of recorded frames {:} less than expected {:}". \
                format(self.camera.recorded_frames.magnitude, self.nsteps)
            LOG.error(tmp)
            error_message(tmp)
            return
        self.ffcsetup.close_shutter()
        self.return_ct_stage_to_start(block=False)
        self.camera.uca.start_readout()
        for i in range(self.nsteps):
            yield self.camera.grab()
        self.camera.uca.stop_readout()
        while self.motor.state == "moving":
            sleep(0.5)

    def take_tomo_auto_dimax(self):
        # parallel read-out not possible: Dimax mode SEQUENCE:
        # parallel read out possible: Dimax mode: RECORDER + RING BUFFER:
        """A generator which yields projections. """
        LOG.info("Starting acquisition: on-the-fly scan with Dimax, auto trig, int buffer")
        if self.camera.state == "recording":
            self.camera.stop_recording()
        if self.camera.trigger_source != self.camera.trigger_sources.AUTO:
            self.camera.trigger_source = self.camera.trigger_sources.AUTO
        try:
            self.ffcsetup.open_shutter()
        except Exception as exp:
            LOG.error(exp)
            error_message("Cannot open shutter")
        velocity = self.range * q.deg / (self.nsteps / self.camera.frame_rate)
        sleep_time = self.nsteps / float(self.camera.frame_rate.magnitude) * 1.05
        LOG.debug("time to sleep for scan: {}".format(sleep_time))
        LOG.debug("Velocity: {}, Range: {}".format(velocity, self.range))
        self.motor["velocity"].set(velocity).join()
        with self.camera.recording():
            time.sleep(self.nsteps / float(self.camera.frame_rate.magnitude) * 1.05)
        self.ffcsetup.close_shutter()
        self.motor.stop().join()
        self.return_ct_stage_to_start(block=False)
        self.camera.uca.start_readout()
        for i in range(self.nsteps):
            yield self.camera.grab()
        self.camera.uca.stop_readout()
        while self.motor.state == "moving":
            sleep(0.5)

    def take_tomo_auto(self):
        """A generator which yields projections. """
        LOG.info("Starting acquisition: on-the-fly scan, auto trig, parallel readout")
        velocity = self.range * q.deg / (self.nsteps / self.camera.frame_rate)
        LOG.debug("Velocity: {}, Range: {}".format(velocity, self.range))
        if self.camera.state == "recording":
            self.camera.stop_recording()
        # increase the number of buffers to avoid overwriting if writing is slow
        if self.camera.trigger_source != self.camera.trigger_sources.AUTO:
            self.camera.trigger_source = self.camera.trigger_sources.AUTO
        try:
            self.ffcsetup.open_shutter()
        except Exception as exp:
            LOG.error(exp)
            error_message("Cannot open shutter")
        if self.camera.buffered:
            self.camera.num_buffers = self.nsteps * 1.5
        self.motor["velocity"].set(velocity).join()
        #time.sleep(1) # what is it for? Must proceed as soon as speed is constant
        #there must be signal from stage that it covered the 180/360 degrees
        #and as soon as it happens stage must be stopped and shutter closed
        #but grab cycle must go on at the same time
        try:
            with self.camera.recording():
                for i in range(self.nsteps):
                    yield self.camera.grab()
        except:
            LOG.exception('Error during data acquisition')
        self.ffcsetup.close_shutter()
        self.motor.stop().join()
        self.return_ct_stage_to_start(block=True)

    def prep4ext_trig_scan_with_PSO(self):
        if self.camera.state == "recording":
            self.camera.stop_recording()
        if self.camera.trigger_source != self.camera.trigger_sources.EXTERNAL:
            self.camera.trigger_source = self.camera.trigger_sources.EXTERNAL
        try:
            self.ffcsetup.open_shutter().join()
        except Exception as exp:
            LOG.error("Cannot open shutter")
            LOG.error(exp)
        try:
            self.motor["stepvelocity"].set(
                self.motor.calc_vel(
                    self.nsteps, self.exp_time + self.dead_time, self.range
                )
            ).join()
            self.motor["stepangle"].set(self.step).join()
            self.motor.LENGTH = self.step * self.nsteps * 1.05 #overshooting a bit for the sake of stability
            LOG.debug(
                "Velocity: {}, Step: {}, Range: {}".format(
                    self.motor.stepvelocity, self.motor.stepangle, self.motor.LENGTH
                )
            )
        except Exception as exp:
            LOG.error(exp)
            tmp="Cannot set parameters of CT stage/PSO for ext trig scan"
            LOG.error(tmp)
            error_message(tmp)

    def return_ct_stage_to_start(self, block=True):
        try:
            LOG.debug("returning inner motor to start after acquisition")
            LOG.debug("change velocity")
            self.motor["stepvelocity"].set(self.motor.base_vel).join()
            time.sleep(1)
            # the motor does not always move but moving a small amount first seems
            # to result in the movement to the start position
            self.motor["position"].set(self.motor.position + 0.1*q.deg).join()
            time.sleep(0.2)
            if block:
                self.motor["position"].set(self.start*self.units).join()
            else:
                self.motor["position"].set(self.start * self.units)
        except Exception as exp:
            LOG.error(exp)
            error_message(
                "can't return CT stage to start position after auto scan"
            )

    #def stop_rotation_and_close_shutter(self):
        #self.ffcsetup.close_shutter()
        #self.motor.stop().join()
        # the motor does not always move but moving a small amount first seems
        # to result in the movement to the start position
        # self.motor["stepvelocity"].set(self.motor.base_vel).join()
        # LOG.debug("return to start")
        # time.sleep(1)
        # # the motor does not always move but moving a small amount first seems
        # # to result in the movement to the start position
        # self.motor["position"].set(self.motor.position + 0.1).join()
        # self.motor["position"].set(self.glob_tmp).join()


        # Q - if I stop recording can I continue to read-out? A - No


    # external camera control
    # Camera is completely external and this is only moving stages and sending triggers
    def take_ttl_tomo(self, swi):
        """Scan using triggers to camera. The camera is assumed to be controlled externally"""
        LOG.info("start TTL scan")
        # set param
        step_scan = False
        total_time = self.exp_time + self.dead_time
        if total_time < 1.0:
            mesg = "Time is too short for TTL pulses: {} < 1 ms".format(total_time)
            error_message(mesg)
            LOG.error(mesg)
            return
        try:
            if self.flats_before or swi==1:
                LOG.debug("Take flats before.")
                self.ffcsetup.prepare_flats(True)
                self.ffcsetup.open_shutter(True)
                self.motor.PSO_ttl(self.num_flats, total_time).join()
                time.sleep((total_time / 1000.0) * self.num_flats * 1.1)
                self.ffcsetup.close_shutter(True)
                self.ffcsetup.prepare_radios(True)
        except Exception as exp:
            LOG.error("Problem with Flat Before: {}".format(exp))
        # darks
        try:
            if self.flats_before and self.num_darks > 0:
                LOG.debug("Take darks before.")
                time.sleep(2.0)
                self.motor.PSO_ttl(self.num_darks, total_time).join()
                time.sleep((total_time / 1000.0) * self.num_darks * 1.1)
        except Exception as exp:
            LOG.error("Problem with Dark before: {}".format(exp))
        # take projections
        LOG.debug("Take projections.")
        try:
            self.ffcsetup.open_shutter(True)
            region = np.linspace(self.start, self.range, self.nsteps) * q.deg
            if step_scan:
                self.motor["stepvelocity"].set(5.0 * q.deg / q.sec).result()
                for pos in region:
                    self.motor.position = pos
                    self.motor.PSO_ttl(1, total_time)
            else:
                vel = self.motor.calc_vel(self.nsteps, total_time, self.range)
                if vel.magnitude > 365.0:
                    mesg = "Velocity is too high: {} > 365 deg/s".format(vel)
                    error_message(mesg)
                    LOG.error(mesg)
                    return
                self.motor["stepvelocity"].set(vel).join()
                # self.motor['stepangle'].set(float(self.range) / float(self.nsteps) * q.deg).join()
                self.motor["stepangle"].set(self.step).join()
                # self.motor.LENGTH = self.range * q.deg
                self.motor.LENGTH = self.step * self.nsteps
                LOG.debug(
                    "Velocity: {}, Step: {}, Range: {}".format(
                        self.motor.stepvelocity, self.motor.stepangle, self.motor.LENGTH
                    )
                )
                self.motor.PSO_multi(False)
                # LOG.debug("Expected time to wait: {} s".format(self.nsteps * (total_time / 1000.0) * 1.05))
                self.motor.wait_until_stop(timeout=1.0 * q.sec)
            self.ffcsetup.close_shutter(True)
        except Exception as exp:
            LOG.error("Problem with Tomo: {}".format(exp))
        # flats after
        try:
            if self.flats_after or swi==2:
                LOG.debug("Take flats after.")
                self.ffcsetup.prepare_flats(True)
                self.ffcsetup.open_shutter(True)
                self.motor.PSO_ttl(self.num_flats, total_time).join()
                time.sleep((total_time / 1000.0) * self.num_flats * 1.1)
                self.ffcsetup.close_shutter(True)
                self.ffcsetup.prepare_radios(True)
        except Exception as exp:
            LOG.error("Problem with Flat After: {}".format(exp))
        try:
            LOG.debug("Return to start")
            self.motor["stepvelocity"].set(20.0 * q.deg / q.sec)
            # the motor does not always move but moving a small amount first seems
            # to result in the movement to the start position
            self.motor["position"].set(self.motor.position + 0.1).join()
            self.motor["position"].set(self.start * q.deg).join()
            self.motor["stepvelocity"].set(5.0 * q.deg / q.sec)
        except Exception as exp:
            LOG.error("Problem with returning to start position: {}".format(exp))

    # test
    def test_rec_seq_with_sync(self):
        if self.camera.trigger_source != "AUTO":
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
        operation = self.shutter.open if desired_state == "open" else self.shutter.close
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
        return self._manipulate_shutter("open", block=block)

    def close_shutter(self, block=True):
        return self._manipulate_shutter("closed", block=block)

    def prepare_flats(self, block=True):
        return self._manipulate_flat_motor(self.flat_position, block=block)

    def prepare_radios(self, block=True):
        return self._manipulate_flat_motor(self.radio_position, block=block)
