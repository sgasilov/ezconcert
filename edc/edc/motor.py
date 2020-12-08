from concert.devices.motors.base import (
    LinearMotor,
    RotationMotor,
    ContinuousRotationMotor,
)
from concert.devices.motors import dummy
from concert.base import Quantity, check, HardLimitError
from concert.quantities import q
from concert.async import async, busy_wait, WaitError
from edc.base import PVObject
from concert.async import async
from numpy import NAN
import enum
import time


class ScanMode(enum.Enum):
    STEP, START, TRIGGER = range(3)


class CLSLinear(LinearMotor):
    """CLS "vme" type stepper motor.
    Motor with units of mm.

    Args:

        name (str): PV name of motor (including units)
        encoded (bool): whether motor has encoder or not, default = True
    """

    SLEEP_TIME = 0.01 * q.s
    TIMEOUT = 1.0 * q.s
    UNITS = q.mm

    def __init__(self, name, encoded=True):
        super(CLSLinear, self).__init__()
        self.name = name
        self.use_encoder = encoded
        name_parts = name.split(":")
        # units = name_parts[-1]
        self.name_root = ":".join(name_parts[:-1])
        self.pv_obj = PVObject()
        self.add_pv = self.pv_obj.add_pv  # alias add_pv function
        self.add_callback = self.pv_obj.add_callback  # alias add_callback function
        self.configure()

    def configure(self):
        """
        Configure PV
        """
        m = self.add_pv(self.name)
        self.VAL = m
        if self.use_encoder:
            m = self.add_pv("{}:fbk".format(self.name))
            self.RBV = m
        else:
            m = self.add_pv("{}:sp".format(self.name))
            self.RBV = m
        m = self.add_pv("{}:ccw".format(self.name_root))
        self.CCW_LIM = m
        m = self.add_pv("{}:cw".format(self.name_root))
        self.CW_LIM = m
        m = self.add_pv("{}:status".format(self.name_root))
        self.STAT = m
        m = self.add_pv("{}:stop".format(self.name_root))
        self.STOP = m
        print("...connected")

    def _get_position(self):
        """
        Get position quantity.

        Returns:
            position (q.mm): position of device
        """
        val = self.RBV.value
        if val is None:
            val = NAN * self.UNITS
        else:
            val *= self.UNITS
        self._position = val
        return self._position

    def _set_position(self, position):
        """
        Set position quantity.

        Args:
            position (q.mm): position to move to
        """
        self.VAL.put(position.magnitude)
        self["state"].wait("moving", sleep_time=self.SLEEP_TIME, timeout=1.0 * q.s)
        self["state"].wait("standby", sleep_time=self.SLEEP_TIME)
        self._position = position

    def _cancel_position(self):
        """
        Stop when user presses Ctrl-C
        """
        self.STOP.put(1)
        self["state"].wait("standby", sleep_time=self.SLEEP_TIME, timeout=self.TIMEOUT)

    def _get_state(self):
        """
        Get state of the motor.
        """
        state = "standby"
        val = self.STAT.value
        if val == 1:
            state = "moving"
        val = self.CW_LIM.value
        if val > 0:
            state = "hard-limit"
        val = self.CCW_LIM.value
        if val > 0:
            state = "hard-limit"
        return state

    def _stop(self):
        """
        Stop the motor from moving.
        """
        self.STOP.put(1)
        self["state"].wait("standby", sleep_time=self.SLEEP_TIME, timeout=self.TIMEOUT)


class CLSAngle(CLSLinear, RotationMotor):
    """CLS "vme" type stepper motor.
    Motor with units of deg.

    Args:
        name (str): PV name of motor (including units)
        encoded (bool): whether motor has encoder or not, default = True
    """

    SLEEP_TIME = 0.01 * q.s
    TIMEOUT = 1.0 * q.s
    UNITS = q.deg

    position = Quantity(
        q.deg,
        help="Angular position",
        check=check(source=["hard-limit", "standby"], target=["hard-limit", "standby"]),
    )

    def __init__(self, name, encoded=True):
        super(CLSLinear, self).__init__()
        # RotationMotor.__init__()
        self.name = name
        self.use_encoder = encoded
        name_parts = name.split(":")
        # units = name_parts[-1]
        self.name_root = ":".join(name_parts[:-1])
        self.pv_obj = PVObject()
        self.add_pv = self.pv_obj.add_pv  # alias add_pv function
        self.configure()


ABRS_NAME = "ABRS1605-01:deg"


class ABRS(ContinuousRotationMotor):
    """ Air Bearing Rotation Stage

    Args:
        name (str): PV name of motor (including units)
        encoded (bool): whether motor has encoder or not, default = True

    .. attribute:: stepvelocity

        Velocity of the motor for making steps in units of deg/s.

    .. attribute:: stepangle

        Step size of the motor in deg units.

    .. attribute:: accel

        Acceleration of the motor in units of deg / s^2
    """

    SLEEP_TIME = 0.01 * q.s
    TIMEOUT = 1.0 * q.s
    UNITS = q.deg
    VEL_UNITS = q.deg / q.s
    ACCEL_UNITS = q.deg / q.s ** 2
    LENGTH = 180 * q.deg
    scan_mode = ScanMode

    stepvelocity = Quantity(
        q.deg / q.s,
        help="Step angular velocity",
        check=check(
            source=["hard-limit", "standby", "moving"], target=["moving", "standby"]
        ),
    )
    stepangle = Quantity(q.deg, help="Angular step")
    accel = Quantity(q.deg / q.s ** 2, help="Angular acceleration")

    def __init__(self, name, encoded=True):
        super(ABRS, self).__init__()
        self.name = name
        name_parts = name.split(":")
        # units = name_parts[-1]
        self.name_root = ":".join(name_parts[:-1])
        self.pv_obj = PVObject()
        self.add_pv = self.pv_obj.add_pv  # alias add_pv function
        self.configure()
        self.enable()
        self._position = 0.0 * q.deg
        self._velocity = 0.0 * q.deg / q.s
        self._stepvelocity = 0.0 * q.deg / q.s
        self._delta = 0.0 * q.deg
        self._accel = 0.0 * q.deg / q.s ** 2
        self.CountsPerUnit = 359992.88888888917
        self.EXT_CMD_RST.put(1) # reset the command queue

    def configure(self):
        """
        Configure PVs to be used.
        """
        m = self.add_pv(self.name)
        self.VAL = m
        m = self.add_pv("{}:fbk".format(self.name))
        self.RBV = m
        m = self.add_pv("{}:cmd:enable".format(self.name_root))
        self.ENABLE_CMD = m
        m = self.add_pv("{}:cmd:disable".format(self.name_root))
        self.DISABLE_CMD = m
        m = self.add_pv("{}:cmd:clearFaults".format(self.name_root))
        self.CLEAR_FAULTS = m
        m = self.add_pv("{}:state:MoveActive".format(self.name_root))
        self.STAT = m
        m = self.add_pv("{}:cmd:abort".format(self.name_root))
        self.STOP = m
        m = self.add_pv("{}:velo:degps".format(self.name_root))
        self.VEL = m
        m = self.add_pv("{}:vel:degps:sp".format(self.name_root))
        self.CUR_VEL = m
        m = self.add_pv("{}:state:ConstVel".format(self.name_root))
        self.CONST_VEL = m
        m = self.add_pv("{}:cmd:home".format(self.name_root))
        self.HOME = m
        m = self.add_pv("{}:cmd:freerun:start".format(self.name_root))
        self.FREERUN = m
        m = self.add_pv("{}:par:delta".format(self.name_root))
        self.DELTA = m
        m = self.add_pv("{}:accel:degpss".format(self.name_root))
        self.ACCEL = m
        m = self.add_pv("{}:cmd:ext".format(self.name_root))
        self.EXT_CMD = m
        m = self.add_pv("{}:cmd:ext:fbk".format(self.name_root))
        self.EXT_CMD_FBK = m
        m= self.add_pv("{}:cmd:reset".format(self.name_root))
        self.EXT_CMD_RST = m
        print("...connected")

    def enable(self):
        """
        Enable the motor.
        """
        self.ENABLE_CMD.put(1)

    def disable(self):
        """
        Disable the motor.
        """
        self.DISABLE_CMD.put(1)

    def faultack(self):
        """
        Clear errors.
        """
        self.CLEAR_FAULTS.put(1)

    def _get_position(self):
        """
        Get position quantity.

        Returns:
            position (quantities.q): Position of device, unit = deg
        """
        val = self.RBV.value
        if val is None:
            val = NAN * self.UNITS
        else:
            val *= self.UNITS
        self._position = val
        return self._position

    def _set_position(self, position):
        """
        Set position quantity

        Args:
            position (quantities.q): Position, unit = deg
        """
        self.VAL.put(position.magnitude)
        try:
            self["state"].wait("moving", sleep_time=self.SLEEP_TIME, timeout=0.2 * q.s)
            self["state"].wait("standby", sleep_time=self.SLEEP_TIME)
        except WaitError:
            pass
        self._position = position

    def _get_state(self):
        """
        Get state information from controller.
        """
        state = "standby"
        val = self.STAT.value
        if val == 1:
            state = "moving"
        return state

    def _abort(self):
        """
        Send ABORT command to controller.
        """
        self.STOP.put(1)
        self["state"].wait("standby", sleep_time=self.SLEEP_TIME, timeout=self.TIMEOUT)

    def _cancel_position(self):
        """
        Ctrl-C from user is same as sbort.
        """
        self._abort()

    def _cancel_velocity(self):
        """
        Ctrl-C from user is same as sbort.
        """
        self._abort()

    def _get_stepvelocity(self):
        """
        Get stepvelocity quantity.

        Returns:
            velocity (quantities.q): Angular velocity, unit = deg / sec
        """
        val = self.VEL.value
        if val is None:
            val = NAN * self.VEL_UNITS
        else:
            val *= self.VEL_UNITS
        self._stepvelocity = val
        return self._stepvelocity

    def _set_stepvelocity(self, velocity):
        """
        Set position quantity

        Args:
            velocity (quantities.q): Angular velocity, unit = deg / sec
        """
        self.VEL.put(velocity.magnitude)
        self._stepvelocity = velocity

    def _cancel_stepvelocity(self):
        """
        Ctrl-C from user is same as sbort.
        """
        self._abort()

    def _is_velocity_stable(self):
        """
        Return True if the velocity is constant. This is True when moving at a
        constant velocity or if not moving.
        """
        val = self.CONST_VEL.value
        return bool(val)

    def _get_velocity(self):
        """
        Get velocity quantity.

        Returns:
            velocity (quantities.q): Angular velocity, unit = deg / sec
        """
        val = self.CUR_VEL.value
        if val is None:
            val = NAN * self.VEL_UNITS
        else:
            val *= self.VEL_UNITS
        self._velocity = val
        return self._velocity

    def _set_velocity(self, velocity):
        """
        Set velocity quantity.

        Using freerun mode for setting constant velocity. Setting this velocity also
        sets the stepvelocity.

        Args:
            velocity (quantities.q): Angular velocity, unit = deg / sec
        """
        self.VEL.put(velocity.magnitude)
        self.FREERUN.put(1)
        busy_wait(self._is_velocity_stable, sleep_time=self.SLEEP_TIME)
        self._velocity = velocity
        self._stepvelocity = velocity

    def _stop(self):
        """
        Set velocity to 0 deg/s if the motor is moving.
        """
        if self.state == "moving":
            self.velocity = 0 * q.deg / q.s
        
        self["state"].wait("standby", sleep_time=self.SLEEP_TIME)

    def _home(self):
        """
        Send HOME command to controller.
        """
        self.HOME.put(1)
        try:
            self["state"].wait(
                "moving", sleep_time=self.SLEEP_TIME, timeout=0.2 * q.s)
            self["state"].wait("standby", sleep_time=self.SLEEP_TIME)
        except WaitError:
            pass

    def _get_stepangle(self):
        """
        Get stepangle quantity.

        Returns:
            angle_step (quantities.q): angle step, unit = deg
        """
        val = self.DELTA.value
        if val is None:
            val = NAN * self.UNITS
        else:
            val *= self.UNITS
        self._delta = val
        return self._delta

    def _set_stepangle(self, value):
        """
        Set stepangle quantity

        Args:
            angle_step (quantities.q): angle, unit = deg
        """
        self.DELTA.put(value.magnitude)
        self._delta = value

    def _get_accel(self):
        """
        Get accel quantity.

        Returns:
            accel (quantities.q): acceleration, unit = deg / sec^2
        """
        val = self.ACCEL.value
        if val is None:
            val = NAN * self.ACCEL_UNITS
        else:
            val *= self.ACCEL_UNITS
        self._accel = val
        return self._accel

    def _set_accel(self, value):
        """
        Set accel quantity

        Args:
            accel (quantities.q): acceleration, units = deg / sec^2
        """
        self.ACCEL.put(value.magnitude)
        self._accel = value

    def scan(self, mode=1, home=False):
        """
        Scan the stage

        Args:
            mode (enum): select the scanning mode using enum :class:`ScanMode`
            home (bool): select whether to move to home position before scan, default=False
        """
        if mode == 1:
            self.PSO_single(home)

    def calc_vel(self, images, interval, distance):
        """
        Calculate velocity based on scan parameters.

        Args:
            images (int): number of images
            interval (float): interval between camera triggers (ms)
            distance (float): distance of scan (deg)

        Returns:
             velocity (float): velocity (deg/sec)
        """
        t = interval*images/1000.0
        return distance/t *q.deg/q.sec

    @async
    def PSO_n_pulses(self, cycles, totalTime=10000, onTime=5000):
        """
        Send a number of pulses via PSO system.

        Args:
            cycles (int): number of pulses
            totalTime (int): total time of the pulse (microseconds)
            onTime (int):  time the signal is high (microseconds)
        """
        delay = 0.1
        print("cycles: {}, time: {}, on: {}".format(cycles, totalTime, onTime))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(5) = {}".format(totalTime))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(6) = {}".format(onTime))
        time.sleep(delay)
        self.EXT_CMD.put("IGLOBAL(7) = {}".format(cycles))
        time.sleep(delay)
        self.EXT_CMD.put('PROGRAM RUN 4, "SinglePulseOutput.bcx"')

    @async
    def PSO_ttl(self, number, interval, duty=0.5):
        """
        Send a number of TTL pulses via the PSo system

        Args:
            number (int): number of pulses
            interval (float): time of interval (ms)
            duty (float): duty cycle (ms), default = 0.5
        """
        print("cycles: {}, time: {}, on: {}".format(number, interval, duty))
        onTime = interval*duty*1000
        self.PSO_n_pulse(number, interval*1000.0, onTime).join()

    @async
    def PSO_multi(self, home=True):
        """
        PSO scan with multiple trigger signal.

        The following quantities are used:

            - stepvelocity
            - accel
            - stepangle
            - length

        Args:
            home (bool): select whether to move to home position before scan, default=False
        """
        delay = 0.1
        if home:
            self.home().join()
        accel_dist = 0.5 * (self.stepvelocity * 1.5) ** 2 / self.accel
        init_pos = self.position + accel_dist
        final_pos = self.position + accel_dist + self.LENGTH
        total = accel_dist * 3 + self.LENGTH
        # print("initial position: {:10.4f}, final position: {:10.4f}, total distance: {:10.4f}".format(init_pos, final_pos, total))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(0) = {}".format(self.stepangle.magnitude))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(1) = {}".format(-final_pos.magnitude))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(2) = {}".format(-init_pos.magnitude))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(3) = {}".format(total))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(4) = {}".format(self.stepvelocity.magnitude))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(5) = {}".format(5000))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(6) = {}".format(2500))
        time.sleep(delay)
        self.EXT_CMD.put("IGLOBAL(7) = {}".format(1))
        time.sleep(delay)
        self.EXT_CMD.put('PROGRAM RUN 4, "FixedDistWindow.bcx"')

    @async
    def PSO_pulse(self, home=True):
        """
        PSO scan with multiple trigger signal.

        The following quantities are used:

            - stepvelocity
            - accel
            - stepangle
            - length

        Args:
            home (bool): select whether to move to home position before scan, default=False
        """
        delay = 0.1
        if home:
            self.home().join()
        accel_dist = 0.5 * (self.stepvelocity * 1.5) ** 2 / self.accel
        init_pos = self.position + accel_dist
        final_pos = self.position + accel_dist + self.LENGTH
        total = accel_dist * 3 + self.LENGTH
        # print("initial position: {:10.4f}, final position: {:10.4f}, total distance: {:10.4f}".format(init_pos, final_pos, total))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(0) = {}".format(self.stepangle.magnitude))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(1) = {}".format(-final_pos.magnitude))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(2) = {}".format(-init_pos.magnitude))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(3) = {}".format(total.magnitude))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(4) = {}".format(self.stepvelocity.magnitude))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(5) = {}".format(10000))
        time.sleep(delay)
        self.EXT_CMD.put("DGLOBAL(6) = {}".format(5000))
        time.sleep(delay)
        self.EXT_CMD.put("IGLOBAL(7) = {}".format(1))
        time.sleep(delay)
        self.EXT_CMD.put('PROGRAM RUN 4, "FixedDistPulse.bcx"')

    @async
    def PSO_off(self):
        """
        Turn off PSO

        Returns:
            None
        """
        delay = 0.1
        time.sleep(delay)
        self.EXT_CMD.put("PSOWINDOW OFF")
        time.sleep(delay)
        self.EXT_CMD.put("PSOCONTROL OFF")

    def reset(self):
        self.abort()
        time.sleep(1.0)
        self.disable()
        time.sleep(0.1)
        self.faultack()
        time.sleep(1.0)
        self.EXT_CMD.put('PROGRAM STOP 1')
        time.sleep(0.1)
        self.EXT_CMD.put('PROGRAM STOP 4')
        time.sleep(0.1)
        self.enable()
        time.sleep(0.1)
        self.EXT_CMD.put('PROGRAM RUN 1, "TCPClient.bcx"')
        time.sleep(10)
        self.stepvelocity = 5.0 * q.deg/q.sec
        time.sleep(0.1)
        self.accel = 100.0 * q.deg/ q.sec ** 2
        time.sleep(0.1)
        self.home()

class SimMotor(dummy.LinearMotor):
    """Sim Motor
    Motor with units of mm. Include a wait time when moving.
    """

    wait = 1 * q.s
    timer = True
    UNITS = q.mm

    @async
    def _set_position(self, position):
        """
        Set position quantity.

        Args:
            position (q.mm): position to move to
        """
        # print("move to {}".format(position))
        self.state = "moving"
        diff = position - self._position
        if position < self.lower:
            self._position = self.lower
            raise HardLimitError("hard-limit")
        elif position > self.upper:
            self._position = self.upper
            raise HardLimitError("hard-limit")
        else:
            if self.timer:
                time.sleep(self.wait.m*abs(diff.magnitude))
            self.state = "standby"
            self._position = position
        # print("...move done")

    def _home(self):
        """
        Reset to 0 mm quickly.
        """
        self.timer = False
        self.position = 0.0 * q.mm
        self.timer = True
