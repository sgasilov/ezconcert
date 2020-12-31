from scans_concert import ACQsetup, FFCsetup
from edc.shutter import CLSShutter
from edc.motor import ABRS, CLSLinear
from concert.quantities import q
import numpy as np
import time


def ttl_scan(acq, step_scan=False, goto_start=True):
    """Scan using triggers to camera. The camera is assumed to be controlled externally"""
    # go to start
    if goto_start:
        try:
            acq.motor['stepvelocity'].set(5.0 * q.deg / q.sec)
            # the motor does not always move but moving a small amount first seems
            # to result in the movement to the start position
            future = acq.motor['position'].set(acq.motor.position + 0.1).join()
            future = acq.motor['position'].set(acq.start*q.deg).join()
            result = future.result()
        except Exception as exp:
            print("Problem with returning to start position: {}".format(exp))
    # flats before
    print("Take flats before.")
    try:
        acq.ffcsetup.prepare_flats(True)
        acq.ffcsetup.open_shutter(True)
        acq.motor.PSO_ttl(acq.num_flats, acq.exp_time + acq.dead_time).result()
        acq.ffcsetup.close_shutter(True)
        acq.ffcsetup.prepare_radios(True)
    except Exception as exp:
        print("Problem with Flat Before: {}".format(exp))
    # darks
    print("Take darks.")
    try:
        acq.motor.PSO_ttl(acq.num_darks, acq.exp_time + acq.dead_time).result()
    except Exception as exp:
        print("Problem with Dark: {}".format(exp))
    # take projections
    print("Take projections.")
    try:
        acq.ffcsetup.open_shutter().join()
        region = np.linspace(acq.start, acq.range, acq.nsteps) * q.deg
        if step_scan:
            acq.motor['stepvelocity'].set(5.0 * q.deg / q.sec).result()
            for pos in region:
                acq.motor.position = pos
                acq.motor.PSO_ttl(1, acq.exp_time + acq.dead_time)
        else:
            acq.motor['stepvelocity'].set(acq.motor.calc_vel(
                acq.nsteps, acq.exp_time + acq.dead_time, acq.range)).result()
            acq.motor['stepangle'].set(float(acq.range) / float(acq.nsteps) * q.deg).result()
            acq.motor.LENGTH = acq.range * q.deg
            print("Velocity: {}, Step: {}, Range: {}".format(
                acq.motor.stepvelocity, acq.motor.stepangle, acq.motor.LENGTH))
            acq.motor.PSO_multi(False).join()
            time.sleep(acq.nsteps * (acq.exp_time + acq.dead_time)/1000.0 + 5)
        acq.ffcsetup.close_shutter()
    except Exception as exp:
        print("Problem with Tomo: {}".format(exp))
    # go to start
    if goto_start:
        try:
            acq.motor['stepvelocity'].set(5.0 * q.deg / q.sec)
            # the motor does not always move but moving a small amount first seems
            # to result in the movement to the start position
            future = acq.motor['position'].set(acq.motor.position + 0.1).join()
            future = acq.motor['position'].set(acq.start * q.deg).join()
            result = future.result()
        except Exception as exp:
            print("Problem with returning to start position: {}".format(exp))
    # flats after
    print("Take flats after.")
    try:
        acq.ffcsetup.prepare_flats(True)
        acq.ffcsetup.open_shutter(True)
        acq.motor.PSO_ttl(acq.num_flats, acq.exp_time + acq.dead_time).result()
        acq.ffcsetup.close_shutter(True)
        acq.ffcsetup.prepare_radios(True)
    except Exception as exp:
        print("Problem with Flat After: {}".format(exp))


if __name__ == "__main__":
    # connect some motors
    shutter = CLSShutter("ABRS1605-01:fis")
    CT_motor = ABRS("ABRS1605-01:deg", encoded=True)
    hor_motor = CLSLinear("SMTR1605-2-B10-11:mm", encoded=True)
    # setup flat
    ffc = FFCsetup(shutter)
    ffc.flat_motor = hor_motor
    ffc.flat_position = 30.0 * q.mm
    ffc.radio_position = 25.0 * q.mm
    # setup acquire
    camera = None
    acq = ACQsetup(camera, ffc)
    acq.num_darks = 10
    acq.num_flats = 20
    acq.exp_time = 100.0
    acq.dead_time = 100.0
    acq.motor = CT_motor
    acq.start = 0.0
    acq.nsteps = 1000
    acq.range = 180.0
    # acq.endp = False
    acq.step = 0.18
    acq.region = None
    acq.cont = False
    acq.units = q.deg
    # acq.ffc_motor = None
    ttl_scan(acq, step_scan=False, goto_start=True)
