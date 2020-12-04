"""# *sim_stack* session manual

## Usage

## Notes
"""

import logging
import concert

concert.require("0.11.0")

from concert.quantities import q
from concert.session.utils import ddoc, dstate, pdoc, code_of, abort
from concert.devices.cameras.dummy import Camera
from concert.devices.motors.dummy import (
    LinearMotor,
    RotationMotor,
    ContinuousRotationMotor,
)
from concert.devices.storagerings.dummy import StorageRing
from concert.devices.cameras.uca import Camera as Camera2

LOG = logging.getLogger(__name__)

ring = StorageRing()
cam1 = Camera()
cam2 = Camera2("mock")

cam_vert = LinearMotor()
cam_focus = LinearMotor()
cam_rot = RotationMotor()
sam_vert = LinearMotor()
sam_horiz = LinearMotor()
sam_pitch = RotationMotor()
sam_rot = ContinuousRotationMotor()
