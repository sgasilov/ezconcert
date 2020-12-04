from edc.motor import CLSLinear, ABRS, CLSAngle, SimMotor
from concert.quantities import q
from concert.devices.cameras.uca import Camera as UcaCamera
import time

ABRS_NAME = "ABRS1605-01:deg"
air_rot = ABRS(ABRS_NAME)
#air_rot.home()
#camera = UcaCamera("pco")




nsteps = 100
exp_time = 20.0
dead_time = 1500.0
range_ = 180.0

#camera.trigger_source = camera.trigger_sources.EXTERNAL
#camera.exposure_time = exp_time * q.msec
air_rot.stepvelocity = air_rot.calc_vel(nsteps, exp_time + dead_time, range_)
print(air_rot.stepvelocity )
air_rot.stepangle = (range_ / nsteps) * q.deg
print(air_rot.stepangle)
#camera.start_recording()
#air_rot.PSO_pulse(1000, 20000, 5000).join()
#time.sleep(20)
#air_rot.PSO_ttl(1000, 20, 0.1).join()
#air_rot.PSO_single(home=False).join()
#air_rot.PSO_multi(home=True).join()
air_rot.PSO_pulse(home=True).join()
#camera.stop_recording()
#camera.trigger_source = camera.trigger_sources.SOFTWARE
#air_rot.PSO_off().join()