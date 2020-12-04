"""# *rti-stack* session manual

## Usage

## Notes
"""

from concert.devices.cameras.uca import Camera
from edc.motor import CLSLinear, ABRS, CLSAngle
from edc.shutter import CLSShutter
from concert.devices.shutters.dummy import Shutter
from concert.coroutines.base import coroutine, inject
from concert.experiments.addons import Consumer
from concert.experiments.base import Acquisition, Experiment
from concert.async import resolve
from concert.ext.viewers import PyplotImageViewer
from edc.motor import CLSLinear, ABRS, CLSAngle, SimMotor
from concert.devices.cameras.uca import Camera as UcaCamera
# from concert.devices.cameras.dummy import Camera
from concert.session.utils import ddoc, dstate, pdoc, code_of, abort
from concert.quantities import q
from functools import partial
from epics import caput
import logging
import concert
import json
import time


concert.require("0.11.0")

# import sys
# sys.path.append('/home/webba/soft-ioc/soloist/concert')
ABRS_NAME = "ABRS1605-01:deg"
air_rot = ABRS(ABRS_NAME)
air_rot.enable()

# stack motors
sam_pitch = CLSAngle("SMTR1605-2-B10-09:deg", encoded=True)
sam_vert = CLSLinear("SMTR1605-2-B10-10:mm", encoded=True)
sam_hor = CLSLinear("SMTR1605-2-B10-11:mm", encoded=True)
cam_rot = CLSAngle("SMTR1605-2-B10-12:deg", encoded=False)
cam_focus = CLSLinear("SMTR1605-2-B10-13:mm", encoded=False)
cam_vert = CLSLinear("SMTR1605-2-B10-14:mm", encoded=False)

# Shutter

shutter2 = CLSShutter("FIS1605-2-01")
shutter3 = CLSShutter("ABRS1605-01:fis")
shutter1 = Shutter()

# camera = Camera()
viewer = PyplotImageViewer()

camera = Camera("pco")


camera.exposure_time = 0.025 * q.s
camera.trigger_source = camera.trigger_sources.SOFTWARE

LOG = logging.getLogger(__name__)


def produce(num_frames):
    for i in range(num_frames):
        print("Click!")
        yield camera.grab()


def produce2(Timer):
    print("Click!")
    s1 = time.time()
    camera.trigger()
    s2 = time.time()
    data = camera.grab()
    s3 = time.time()
    Timer["image"] += s2 - s1
    Timer["transfer"] += s3 - s1
    return data


@coroutine
def consume():
    i = 1
    while True:
        yield
        LOG.info("Got frame number {}".format(i))
        i += 1


darks = Acquisition("darks", partial(produce, 1), consumers=[consume])
flats = Acquisition("flats", partial(produce, 2), consumers=[consume])
radios = Acquisition("radios", partial(produce, 20), consumers=[consume])
acquisitions = [darks, flats, radios]


def mk_timer():
    timer = {}
    timer["N"] = 0
    timer["move"] = 0
    timer["image"] = 0
    timer["total"] = 0
    timer["transfer"] = 0
    timer["save"] = 0
    timer["exposure"] = 0
    timer["points"] = []
    return timer


Timer = mk_timer()


def test_scan(name, num, exp):
    import numpy as np
    from concert.helpers import Region
    from concert.processes.common import scan

    Timer = mk_timer()
    camera.exposure_time = exp * q.s
    region = Region(sam_vert["position"], np.linspace(20.0, 25.0, num) * q.mm)
    Timer["N"] = num
    camera.start_recording()
    generator = scan(produce2, region)
    s0 = time.time()
    inject(resolve(generator), viewer())
    s1 = time.time()
    camera.stop_recording()
    Timer["total"] = s1 - s0
    Timer["exposure"] = exp
    Timer["points"] = np.linspace(20.0, 25.0, num).tolist()
    with open("{}.dat".format(name), "w") as f:
        json.dump(Timer, f)


def test_CT(name, num, exp):
    import numpy as np
    from concert.helpers import Region
    from concert.processes.common import scan

    Timer = mk_timer()
    camera.exposure_time = exp * q.s
    air_rot.stepvelocity = 5 * q.deg / q.s
    region = Region(air_rot["position"], np.linspace(0.0, 180.0, num) * q.deg)
    Timer["N"] = num
    camera.start_recording()
    generator = scan(produce2, region)
    s0 = time.time()
    inject(resolve(generator), viewer())
    s1 = time.time()
    camera.stop_recording()
    Timer["total"] = s1 - s0
    Timer["exposure"] = exp
    Timer["points"] = np.linspace(0.0, 180.0, num).tolist()
    with open("{}.dat".format(name), "w") as f:
        json.dump(Timer, f)


def test_step_CT(name, num, exp):
    import numpy as np
    import tifffile as tf

    Timer = mk_timer()
    camera.exposure_time = exp * q.s
    air_rot.stepvelocity = 5 * q.deg / q.s
    region = np.linspace(0.0, 180.0, num) * q.deg
    camera.start_recording()
    s0 = time.time()
    for pos in region:
        Timer["N"] += 1
        s2 = time.time()
        air_rot.position = pos
        e2 = time.time()
        Timer["move"] += e2 - s2
        data = produce2(Timer)
        s3 = time.time()
        tf.imsave("im{:04d}.tif".format(Timer["N"]), data)
        e3 = time.time()
        Timer["save"] += e3 - s3
    s1 = time.time()
    camera.stop_recording()
    Timer["total"] = s1 - s0
    Timer["exposure"] = exp
    Timer["points"] = np.linspace(0.0, 180.0, num).tolist()
    with open("{}.dat".format(name), "w") as f:
        json.dump(Timer, f)


def main():
    """Run the example and output the experiment data to a dummy walker.
    Also show the images in a live preview addon.
    """
    exper = Experiment(acquisitions)
    Consumer(exper.acquisitions, viewer)
    exper.run().join()
