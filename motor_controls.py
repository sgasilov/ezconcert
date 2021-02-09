from epics import PV
import atexit
from PyQt5.QtCore import pyqtSignal, QObject, QThread
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, \
    QPushButton, QComboBox, QFileDialog, QCheckBox, QDoubleSpinBox
from concert.base import TransitionNotAllowed
from message_dialog import info_message, error_message
# Adam's Concert-EPICS interface
from edc.shutter import CLSShutter
from edc.motor import CLSLinear, ABRS, SimMotor

from concert.devices.base import abort as device_abort
from concert.quantities import q

class MotorsControlsGroup(QGroupBox):

    def __init__(self, *args, **kwargs):
        super(MotorsControlsGroup, self).__init__(*args, **kwargs)
        # physical devices
        self.hor_motor = None
        self.vert_motor = None
        self.CT_motor = None
        self.shutter = None
        self.time_motor = None
        self.connect_time_motor_func()
        self.motors = [self.hor_motor, self.vert_motor, self.CT_motor, self.shutter, self.time_motor]

        # connect buttons
        self.connect_hor_mot_button = QPushButton("horizontal stage")
        self.connect_vert_mot_button = QPushButton("vertical stage")
        self.connect_CT_mot_button = QPushButton("CT stage")
        self.connect_shutter_button = QPushButton("Imaging shutter")
        # this are to be implemented depending on low-level interface (EPICS/Tango/etc)
        self.connect_hor_mot_button.clicked.connect(self.connect_hor_motor_func)
        self.connect_vert_mot_button.clicked.connect(self.connect_vert_motor_func)
        self.connect_CT_mot_button.clicked.connect(self.connect_CT_motor_func)
        self.connect_shutter_button.clicked.connect(self.connect_shutter_func)

        # position indicators
        self.mot_pos_info_label = QLabel()
        self.mot_pos_info_label.setText("Status")
        self.hor_mot_pos_label = QLabel()
        self.hor_mot_pos_label.setText("Not connected")
        self.hor_mot_pos_entry = QLabel()
        self.vert_mot_pos_label = QLabel()
        self.vert_mot_pos_label.setText("Not connected")
        self.vert_mot_pos_entry = QLabel()
        self.CT_mot_pos_label = QLabel()
        self.CT_mot_pos_label.setText("Not connected")
        self.CT_mot_pos_entry = QLabel()
        self.shutter_label = QLabel()
        self.shutter_label.setText("Not connected")
        self.shutter_entry = QLabel()

        # position entry
        self.hor_mot_pos_move = QDoubleSpinBox()
        self.hor_mot_pos_move.setDecimals(3)
        self.hor_mot_pos_move.setRange(-100, 100)
        self.vert_mot_pos_move = QDoubleSpinBox()
        self.vert_mot_pos_move.setDecimals(3)
        self.vert_mot_pos_move.setRange(-100, 100)
        self.CT_mot_pos_move = QDoubleSpinBox()
        self.CT_mot_pos_move.setDecimals(3)
        self.CT_mot_pos_move.setRange(-720, 720)

        # Move Buttons
        self.stop_motors_button = QPushButton("STOP ALL")
        self.move_hor_mot_button = QPushButton("Move To")
        self.move_hor_mot_button.setEnabled(False)
        self.move_vert_mot_button = QPushButton("Move To")
        self.move_vert_mot_button.setEnabled(False)
        self.move_CT_mot_button = QPushButton("Move To")
        self.move_CT_mot_button.setEnabled(False)
        self.home_CT_mot_button = QPushButton("Home")
        self.home_CT_mot_button.setEnabled(False)
        self.reset_CT_mot_button = QPushButton("Reset")
        self.reset_CT_mot_button.setEnabled(False)
        self.open_shutter_button = QPushButton("Open")
        self.open_shutter_button.setEnabled(False)
        self.close_shutter_button = QPushButton("Close")
        self.close_shutter_button.setEnabled(False)

        # signals
        self.move_hor_mot_button.clicked.connect(self.hor_move_func)
        self.move_vert_mot_button.clicked.connect(self.vert_move_func)
        self.home_CT_mot_button.clicked.connect(self.CT_home_func)
        self.reset_CT_mot_button.clicked.connect(self.CT_reset_func)
        self.move_CT_mot_button.clicked.connect(self.CT_move_func)
        self.open_shutter_button.clicked.connect(self.open_shutter_func)
        self.close_shutter_button.clicked.connect(self.close_shutter_func)
        self.stop_motors_button.clicked.connect(self.stop_motors_func)

        #THREADS
        self.motion_hor = None
        self.motion_CT = None
        self.motion_vert = None
        self.motion_hor = None

        self.set_layout()

    def set_layout(self):

        layout = QGridLayout()
        layout.addWidget(self.stop_motors_button, 0, 1, 2, 1)
        layout.addWidget(self.connect_CT_mot_button, 0, 2, 1, 1)
        layout.addWidget(self.connect_vert_mot_button, 0, 5, 1, 1)
        layout.addWidget(self.connect_hor_mot_button, 0, 8, 1, 1)
        layout.addWidget(self.connect_shutter_button, 0, 11, 1, 1)
        layout.addWidget(self.move_CT_mot_button, 0, 3, 1, 1)
        layout.addWidget(self.home_CT_mot_button, 0, 4, 1, 1)
        layout.addWidget(self.reset_CT_mot_button, 1, 4, 1, 1)
        layout.addWidget(self.move_vert_mot_button, 0, 6, 1, 1)
        layout.addWidget(self.move_hor_mot_button, 0, 9, 1, 1)
        layout.addWidget(self.open_shutter_button, 0, 12, 1, 1)
        layout.addWidget(self.close_shutter_button, 1, 12, 1, 1)
        # layout.addWidget(self.mot_pos_info_label, 1, 1)
        layout.addWidget(self.CT_mot_pos_label, 1, 2)
        layout.addWidget(self.CT_mot_pos_entry, 1, 3)
        layout.addWidget(self.vert_mot_pos_label, 1, 5)
        layout.addWidget(self.vert_mot_pos_entry, 1, 6)
        layout.addWidget(self.hor_mot_pos_label, 1, 8)
        layout.addWidget(self.hor_mot_pos_entry, 1, 9)
        layout.addWidget(self.shutter_label, 1, 11)
        # layout.addWidget(self.shutter_entry, 1, 12)

        layout.addWidget(self.hor_mot_pos_move, 1, 9)
        layout.addWidget(self.vert_mot_pos_move, 1, 6)
        layout.addWidget(self.CT_mot_pos_move, 1, 3)

        self.setLayout(layout)

    def connect_hor_motor_func(self):
        try:
            self.hor_motor = CLSLinear("SMTR1605-2-B10-11:mm", encoded=True)
        except:
            error_message("Can not connect to horizontal stage, try again")
        if self.hor_motor is not None:
            self.hor_mot_pos_label.setText("Position [mm]")
            self.connect_hor_mot_button.setEnabled(False)
            self.move_hor_mot_button.setEnabled(True)
            self.hor_mot_monitor = EpicsMonitorFloat(self.hor_motor.RBV)
            self.hor_mot_monitor.i0_state_changed_signal.connect(
                self.hor_mot_pos_label.setText)
            self.hor_mot_monitor.i0.run_callback(self.hor_mot_monitor.call_idx)

    def connect_vert_motor_func(self):
        try:
            self.vert_motor = CLSLinear("SMTR1605-2-B10-10:mm", encoded=True)
        except:
            error_message("Can not connect to vertical stage, try again")
        if self.vert_motor is not None:
            self.vert_mot_pos_label.setText("Position [mm]")
            self.connect_vert_mot_button.setEnabled(False)
            self.move_vert_mot_button.setEnabled(True)
            self.vert_mot_monitor = EpicsMonitorFloat(self.vert_motor.RBV)
            self.vert_mot_monitor.i0_state_changed_signal.connect(
                self.vert_mot_pos_label.setText)
            self.vert_mot_monitor.i0.run_callback(self.vert_mot_monitor.call_idx)

    def connect_CT_motor_func(self):
        try:
            self.CT_motor = ABRS("ABRS1605-01:deg", encoded=True)
        except:
            error_message("Could not connect to CT stage, try again")
        if self.CT_motor is not None:
            self.CT_mot_pos_label.setText("Position [deg]")
            self.connect_CT_mot_button.setEnabled(False)
            self.move_CT_mot_button.setEnabled(True)
            self.home_CT_mot_button.setEnabled(True)
            self.reset_CT_mot_button.setEnabled(True)
            self.CT_mot_monitor = EpicsMonitorFloat(self.CT_motor.RBV)
            self.CT_mot_monitor.i0_state_changed_signal.connect(
                self.CT_mot_pos_label.setText)
            self.CT_mot_monitor.i0.run_callback(self.CT_mot_monitor.call_idx)

    def connect_shutter_func(self):
        try:
            self.shutter = CLSShutter("ABRS1605-01:fis")
        except:
            error_message("Could not connect to fast imaging shutter, try again")
        if self.shutter is not None:
            self.shutter_label.setText("Connected")
            self.connect_shutter_button.setEnabled(False)
            self.open_shutter_button.setEnabled(True)
            self.close_shutter_button.setEnabled(True)
            self.shutter_monitor = EpicsMonitorFIS(self.shutter.STATE)
            self.shutter_monitor.i0_state_changed_signal.connect(
                self.shutter_label.setText)
            self.shutter_monitor.i0.run_callback(self.shutter_monitor.call_idx)

    def connect_time_motor_func(self):
        try:
            self.time_motor = SimMotor(1.0*q.mm)
        except:
            error_message("Can not connect to timer")


    def open_shutter_func(self):
        if self.shutter is None:
            return
        else:
            try:
                self.shutter.open().join()
            except TransitionNotAllowed:
                return

    def close_shutter_func(self):
        if self.shutter is None:
            return
        else:
            try:
                self.shutter.close().join()
            except TransitionNotAllowed:
                return

    def CT_home_func(self):
        '''Home the stage'''
        if self.CT_motor is None:
            return
        else:
            # if you move to x then home() you can't move to x
            # setting choice to 0 at home position seems to fix this
            self.motion_CT = HomeThread(self.CT_motor)
            self.motion_CT.start()
            # there is a behaviour that the stage will not be able to move
            # to the same position twice in a row so reset the motion
            self.CT_mot_pos_move.setValue(0.0)
            # self.CT_move_func()

    def CT_move_func(self):
        '''Move the stage'''
        if self.CT_motor is None:
            return
        else:
            self.CT_motor.stepvelocity = 5.0 * q.deg/q.sec
            self.motion_CT = MotionThread(self.CT_motor, self.CT_mot_pos_move)
            self.motion_CT.start()


    def CT_reset_func(self):
        '''Reset the stage and move to home'''
        if self.CT_motor is None:
            return
        else:
            self.CT_motor.reset()
            self.CT_mot_pos_move.setValue(0.0)
            self.CT_move_func()
            info_message("Reset finished. Please wait for state motion to stop.")

    def hor_move_func(self):
        if self.hor_motor is None:
            return
        else:
            self.motion_hor = MotionThread(self.hor_motor, self.hor_mot_pos_move)
            self.motion_hor.start()

    def vert_move_func(self):
        if self.vert_motor is None:
            return
        else:
            self.motion_vert = MotionThread(self.vert_motor, self.vert_mot_pos_move)
            self.motion_vert.start()

    def stop_motors_func(self):
        # pyqt threads
        if self.motion_CT is not None:
            self.motion_CT.abort()
        if self.motion_vert is not None:
            self.motion_vert.abort()
        if self.motion_hor is not None:
            self.motion_hor.abort()
        # concert devices
        device_abort(m for m in self.motors if m is not None)
        # if self.hor_motor is not None:
        #     device_abort([self.hor_motor])
        # if self.vert_motor is not None:
        #     device_abort([self.vert_motor])
        # if self.CT_motor is not None:
        #     device_abort([self.CT_motor])
        # if self.shutter is not None:
        #     device_abort([self.shutter])

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
            try:
                self.motor.position = self.position.value() * self.motor.UNITS
                self.thread_running = False
            except TransitionNotAllowed:
                error_message("Stage is moving. Wait until motion has stopped.")
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
            try:
                self.motor.home().join()
                self.thread_running = False
            except TransitionNotAllowed:
                error_message("Stage is moving. Wait until motion has stopped.")
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

