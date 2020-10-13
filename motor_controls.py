from epics import PV
import atexit
from PyQt5.QtCore import pyqtSignal, QObject, QThread


class EpicsMonitorFloat(QObject):
    i0_state_changed_signal = pyqtSignal(str)

    def __init__(self, PV):
        super(EpicsMonitorFloat, self).__init__()
        self.i0 = PV
        self.call_idx = PV.add_callback(self.on_i0_state_changed)
        self.value = None

    def on_i0_state_changed(self, value, **kwargs):
        """
        :param value: the latest value from the PV
        :param kwargs: the rest of arguments
        :return: None
        """
        self.value = value
        self.i0_state_changed_signal.emit("{:.3f}".format(value))


class EpicsMonitorFIS(QObject):
    i0_state_changed_signal = pyqtSignal(str)

    def __init__(self, PV):
        super(EpicsMonitorFIS, self).__init__()
        self.i0 = PV
        self.call_idx = PV.add_callback(self.on_i0_state_changed)
        self.value = None

    def on_i0_state_changed(self, value, **kwargs):
        """
        :param value: the latest value from the PV
        :param kwargs: the rest of arguments
        :return: None
        """
        self.value = value
        if value == 1:
            value_str = 'Open'
        elif value == 2:
            value_str = 'Between'
        elif value == 4:
            value_str = 'Closed'
        else:
            value_str = 'Error'
        self.i0_state_changed_signal.emit(value_str)


class MotionThread(QThread):

    def __init__(self, motor, position):
        super(MotionThread, self).__init__()
        self.motor = motor
        self.thread_running = True
        atexit.register(self.stop)
        self.position = position

    def stop(self):
        self.thread_running = False
        self.wait()

    def run(self):  # .start() calls this function
        while self.thread_running:
            self.motor['position'].set(self.position.value() * self.motor.UNITS).join()
            self.thread_running = False

    def abort(self):
        try:
            self.motor.abort()
        except:
            pass


class HomeThread(QThread):

    def __init__(self, motor):
        super(HomeThread, self).__init__()
        self.motor = motor
        self.thread_running = True
        atexit.register(self.stop)

    def stop(self):
        self.thread_running = False
        self.wait()

    def run(self):  # .start() calls this function
        while self.thread_running:
            self.motor.home().join()
            self.thread_running = False

    def abort(self):
        try:
            self.motor.abort()
        except:
            pass


class ResetThread(QThread):

    def __init__(self, motor):
        super(ResetThread, self).__init__()
        self.motor = motor
        self.thread_running = True
        atexit.register(self.stop)

    def stop(self):
        self.thread_running = False
        self.wait()

    def run(self):  # .start() calls this function
        while self.thread_running:
            self.motor.reset()
            self.thread_running = False

    def abort(self):
        try:
            self.motor.abort()
        except:
            pass
