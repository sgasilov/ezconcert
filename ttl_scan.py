from scans_concert import ACQsetup, FFCsetup
from edc.shutter import CLSShutter
from edc.motor import ABRS, CLSLinear
from concert.quantities import q
import numpy as np
import time
import logging

LOG = logging.getLogger("ezconcert")
LOG.setLevel(logging.DEBUG)
# create handlers
ch = logging.StreamHandler()
# formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
# add handlers
LOG.addHandler(ch)

def error_message(msg):
    LOG.info(msg)

def take_ttl_tomo(self):
    """Scan using triggers to camera. The camera is assumed to be controlled externally"""
    LOG.info("start TTL scan")
    # set param
    step_scan = False
    goto_start = True
    total_time = self.exp_time + self.dead_time
    if (total_time) < 10.0:
        mesg = "Time is too short for TTL pulses: {} < 10 ms".format(total_time)
        error_message(mesg)
        LOG.error(mesg)
        return
    # go to start
    if goto_start:
        try:
            self.motor['stepvelocity'].set(5.0 * q.deg / q.sec).join()
            # the motor does not always move but moving a small amount first seems
            # to result in the movement to the start position
            future = self.motor['position'].set(self.motor.position + 0.1).join()
            future = self.motor['position'].set(self.start * q.deg).join()
            result = future.result()
        except Exception as exp:
            LOG.error("Problem with returning to start position: {}".format(exp))
    # flats before
    LOG.debug("Take flats before.")
    try:
        if self.num_flats > 0:
            self.ffcsetup.prepare_flats(True)
            self.ffcsetup.open_shutter(True)
            self.motor.PSO_ttl(self.num_flats, total_time).join()
            time.sleep((total_time / 1000.0) * self.num_flats * 1.1)
            self.ffcsetup.close_shutter(True)
            self.ffcsetup.prepare_radios(True)
    except Exception as exp:
        LOG.error("Problem with Flat Before: {}".format(exp))
    # darks
    LOG.debug("Take darks.")
    try:
        if self.num_darks > 0:
            time.sleep(2.0)
            self.motor.PSO_ttl(self.num_darks, total_time).join()
            time.sleep((total_time / 1000.0) * self.num_darks * 1.1)
    except Exception as exp:
        LOG.error("Problem with Dark: {}".format(exp))
    # take projections
    LOG.debug("Take projections.")
    try:
        self.ffcsetup.open_shutter().join()
        region = np.linspace(self.start, self.range, self.nsteps) * q.deg
        if step_scan:
            self.motor['stepvelocity'].set(5.0 * q.deg / q.sec).result()
            for pos in region:
                self.motor.position = pos
                self.motor.PSO_ttl(1, total_time)
        else:
            vel = self.motor.calc_vel(
                self.nsteps, total_time, self.range)
            if vel.magnitude > 365.0:
                mesg = "Velocity is too high: {} > 365 deg/s".format(vel)
                error_message(mesg)
                LOG.error(mesg)
                return
            self.motor['stepvelocity'].set(vel).result()
            self.motor['stepangle'].set(float(self.range) / float(self.nsteps) * q.deg).result()
            self.motor.LENGTH = self.range * q.deg
            LOG.debug("Velocity: {}, Step: {}, Range: {}".format(
                self.motor.stepvelocity, self.motor.stepangle, self.motor.LENGTH))
            self.motor.PSO_multi(False).join()
            time.sleep(self.nsteps * (total_time / 1000.0) * 1.05)
        self.ffcsetup.close_shutter()
    except Exception as exp:
        LOG.error("Problem with Tomo: {}".format(exp))
    # flats after
    LOG.debug("Take flats after.")
    try:
        if self.num_flats > 0:
            self.ffcsetup.prepare_flats(True)
            self.ffcsetup.open_shutter(True)
            self.motor.PSO_ttl(self.num_flats, total_time).result()
            time.sleep((total_time / 1000.0) * self.num_flats * 1.1)
            self.ffcsetup.close_shutter(True)
            self.ffcsetup.prepare_radios(True)
    except Exception as exp:
        LOG.error("Problem with Flat After: {}".format(exp))
    # go to start
    if goto_start:
        try:
            self.motor['stepvelocity'].set(20.0 * q.deg / q.sec)
            # the motor does not always move but moving a small amount first seems
            # to result in the movement to the start position
            future = self.motor['position'].set(self.motor.position + 0.1).join()
            future = self.motor['position'].set(self.start * q.deg).join()
            result = future.result()
            self.motor['stepvelocity'].set(5.0 * q.deg / q.sec)
        except Exception as exp:
            LOG.error("Problem with returning to start position: {}".format(exp))


if __name__ == "__main__":
    # connect some motors
    shutter = CLSShutter("ABRS1605-01:fis")
    CT_motor = ABRS("ABRS1605-01:deg", encoded=True)
    hor_motor = CLSLinear("SMTR1605-2-B10-11:mm", encoded=True)
    # setup flat
    ffc = FFCsetup(shutter)
    ffc.flat_motor = hor_motor
    ffc.flat_position = 36.0 * q.mm
    ffc.radio_position = 31.0 * q.mm
    # setup acquire
    camera = None
    acq = ACQsetup(camera, ffc)
    acq.num_darks = 10
    acq.num_flats = 20
    acq.exp_time = 50.0
    acq.dead_time = 50.0
    acq.motor = CT_motor
    acq.start = 0.0
    acq.nsteps = 200
    acq.range = 180.0
    # acq.endp = False
    acq.step = 0.18
    acq.region = None
    acq.cont = False
    acq.units = q.deg
    # acq.ffc_motor = None
    take_ttl_tomo(acq)
