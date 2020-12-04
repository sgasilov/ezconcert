from concert.devices.shutters.base import Shutter
from edc.base import PVObject
from concert.quantities import q
from concert.async import WaitError


class CLSShutter(Shutter):
    """
    Epics-based control of shutters at CLS.

    Args:

        name (str): PV name of shutter
    """

    SLEEP_TIME = 0.01 * q.s
    TIMEOUT = 1.0 * q.s

    def __init__(self, name):
        super(CLSShutter, self).__init__()
        self.name = name
        self.pv_obj = PVObject()
        self.add_pv = self.pv_obj.add_pv  # alias add_pv function
        self.configure()

    def configure(self):
        """
        Configure PV
        """
        m = self.add_pv("{}:opr:open".format(self.name))
        self.OPEN = m
        m = self.add_pv("{}:opr:close".format(self.name))
        self.CLOSE = m
        m = self.add_pv("{}:state".format(self.name))
        self.STATE = m
        m = self.add_pv("{}:enabled".format(self.name))
        self.ENABLED = m
        print("...connected")

    def _open(self):
        if self["state"] in ["open", "error", "disabled"]:
            return
        self.OPEN.put(1)
        try:
            self["state"].wait(
                "between", sleep_time=self.SLEEP_TIME, timeout=self.TIMEOUT
            )
            self["state"].wait("open", sleep_time=self.SLEEP_TIME)
        except WaitError:
            pass

    def _close(self):
        if self["state"] in ["closed", "error", "disabled"]:
            return
        self.CLOSE.put(1)
        try:
            self["state"].wait(
                "between", sleep_time=self.SLEEP_TIME, timeout=self.TIMEOUT
            )
            self["state"].wait("closed", sleep_time=self.SLEEP_TIME)
        except WaitError:
            pass

    def _get_state(self):
        """
        Get state information.
        """
        s = self.STATE.get()
        a = self.STATE.get()
        if not bool(a):
            state = "disabled"
            return state
        if s == 1:
            state = "open"
        elif s == 2:
            state = "between"
        elif s == 4:
            state = "closed"
        else:
            state = "error"
        return state
