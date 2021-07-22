import atexit
from PyQt5.QtCore import pyqtSignal, QObject, QThread, Qt
from PyQt5.QtWidgets import (
    QGridLayout,
    QLabel,
    QGroupBox,
    QPushButton,
    QDoubleSpinBox,
    QFrame,
    QSizePolicy,
)
from concert.base import TransitionNotAllowed
from message_dialog import info_message, error_message

# Concert-EPICS interface
from edc.shutter import CLSShutter
from edc.motor import CLSLinear, ABRS, SimMotor
from switch import Switch
from time import sleep

from concert.devices.base import abort as device_abort
from concert.quantities import q


class QVSeparationLine(QFrame):
    """
    A vertical separation line.
    """

    def __init__(self, *args, **kwargs):
        super(QVSeparationLine, self).__init__(*args, **kwargs)
        self.setFixedWidth(10)
        self.setMinimumHeight(1)
        self.setFrameShape(QFrame.VLine)
        self.setFrameShadow(QFrame.Sunken)
        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Preferred)


class QHSeparationLine(QFrame):
    """
    A horizontal separation line.
    """

    def __init__(self, *args, **kwargs):
        super(QHSeparationLine, self).__init__(*args, **kwargs)
        self.setMinimumWidth(1)
        self.setFixedHeight(10)
        self.setFrameShape(QFrame.HLine)
        self.setFrameShadow(QFrame.Sunken)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Minimum)


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
        self.motors = [
            self.hor_motor,
            self.vert_motor,
            self.CT_motor,
            self.shutter,
            self.time_motor,
        ]

        # connect buttons
        self.connect_hor_mot_button = QPushButton("Horizontal")
        self.connect_vert_mot_button = QPushButton("Vertical")
        self.connect_CT_mot_button = QPushButton("CT stage")
        self.connect_shutter_button = QPushButton("Shutter")
        # this are to be implemented depending on low-level interface (EPICS/Tango/etc)
        self.connect_hor_mot_button.clicked.connect(self.connect_hor_motor_func)
        self.connect_vert_mot_button.clicked.connect(self.connect_vert_motor_func)
        self.connect_CT_mot_button.clicked.connect(self.connect_CT_motor_func)
        self.connect_shutter_button.clicked.connect(self.connect_shutter_func)

        # device labels
        self.CT_mot_label = QLabel()
        self.CT_mot_label.setText("<b>CT STAGE</b>")
        self.CT_mot_label.setStyleSheet("color: green")
        self.CT_mot_label.setAlignment(Qt.AlignCenter)
        self.vert_mot_label = QLabel()
        self.vert_mot_label.setText("<b>SAMPLE VERTICAL</b>")
        self.vert_mot_label.setStyleSheet("color: green")
        self.vert_mot_label.setAlignment(Qt.AlignCenter)
        self.hor_mot_label = QLabel()
        self.hor_mot_label.setText("<b>SAMPLE HORIZONTAL</b>")
        self.hor_mot_label.setStyleSheet("color: green")
        self.hor_mot_label.setAlignment(Qt.AlignCenter)
        self.shutter_label = QLabel()
        self.shutter_label.setText("<b>IMAGING SHUTTER</b>")
        self.shutter_label.setStyleSheet("color: green")
        self.shutter_label.setAlignment(Qt.AlignCenter)

        # position indicators
        self.hor_mot_value = QLabel()
        self.hor_mot_value.setText("Disconnected")
        self.hor_mot_low_lim = QLabel()
        self.hor_mot_high_lim = QLabel()
        # self.hor_mot_pos_entry = QLabel()
        self.vert_mot_value = QLabel()
        self.vert_mot_value.setText("Disconnected")
        self.vert_mot_low_lim = QLabel()
        self.vert_mot_high_lim = QLabel()
        # self.vert_mot_pos_entry = QLabel()
        self.CT_mot_value = QLabel()
        self.CT_mot_value.setText("Disconnected")
        self.CT_mot_low_lim = QLabel()
        self.CT_mot_high_lim = QLabel()
        # self.CT_mot_pos_entry = QLabel()
        self.shutter_status = QLabel()
        self.shutter_status.setText("Disconnected")
        # self.shutter_entry = QLabel()

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
        self.hor_mot_rel_move = QDoubleSpinBox()
        self.hor_mot_rel_move.setDecimals(3)
        self.hor_mot_rel_move.setRange(-100, 100)
        self.vert_mot_rel_move = QDoubleSpinBox()
        self.vert_mot_rel_move.setDecimals(3)
        self.vert_mot_rel_move.setRange(-100, 100)
        self.CT_mot_rel_move = QDoubleSpinBox()
        self.CT_mot_rel_move.setDecimals(3)
        self.CT_mot_rel_move.setRange(-720, 720)
        self.CT_mot_jog_move = QDoubleSpinBox()
        self.CT_mot_jog_move.setDecimals(3)
        self.CT_mot_jog_move.setRange(0, 390)
        self.CT_mot_jog_move.setValue(5.00)

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
        self.move_hor_rel_plus = QPushButton("+")
        self.move_hor_rel_plus.setStyleSheet("font: bold")
        self.move_hor_rel_plus.setEnabled(False)
        self.move_vert_rel_plus = QPushButton("+")
        self.move_vert_rel_plus.setStyleSheet("font: bold")
        self.move_vert_rel_plus.setEnabled(False)
        self.move_CT_rel_plus = QPushButton("+")
        self.move_CT_rel_plus.setStyleSheet("font: bold")
        self.move_CT_rel_plus.setEnabled(False)
        self.move_CT_rel_minus = QPushButton("-")
        self.move_CT_rel_minus.setStyleSheet("font: bold")
        self.move_CT_rel_minus.setEnabled(False)
        self.move_CT_jog_plus = QPushButton("JOG +")
        self.move_CT_jog_plus.setEnabled(False)
        self.move_CT_jog_minus = QPushButton("JOG -")
        self.move_CT_jog_minus.setEnabled(False)
        self.move_hor_rel_minus = QPushButton("-")
        self.move_hor_rel_minus.setStyleSheet("font: bold")
        self.move_hor_rel_minus.setEnabled(False)
        self.move_vert_rel_minus = QPushButton("-")
        self.move_vert_rel_minus.setStyleSheet("font: bold")
        self.move_vert_rel_minus.setEnabled(False)
        self.stop_CT_button = QPushButton("Stop")
        self.stop_CT_button.setEnabled(False)

        # signals
        self.move_hor_mot_button.clicked.connect(self.hor_move_func)
        self.move_vert_mot_button.clicked.connect(self.vert_move_func)
        self.home_CT_mot_button.clicked.connect(self.CT_home_func)
        self.reset_CT_mot_button.clicked.connect(self.CT_reset_func)
        self.move_CT_mot_button.clicked.connect(self.CT_move_func)
        self.open_shutter_button.clicked.connect(self.open_shutter_func)
        self.close_shutter_button.clicked.connect(self.close_shutter_func)
        self.stop_motors_button.clicked.connect(self.stop_motors_func)
        self.move_hor_rel_plus.clicked.connect(self.hor_rel_plus_func)
        self.move_vert_rel_plus.clicked.connect(self.vert_rel_plus_func)
        self.move_CT_rel_plus.clicked.connect(self.CT_rel_plus_func)
        self.move_hor_rel_minus.clicked.connect(self.hor_rel_minus_func)
        self.move_vert_rel_minus.clicked.connect(self.vert_rel_minus_func)
        self.move_CT_rel_minus.clicked.connect(self.CT_rel_minus_func)
        self.move_CT_jog_plus.clicked.connect(self.CT_jog_plus_func)
        self.move_CT_jog_minus.clicked.connect(self.CT_jog_minus_func)
        self.CT_mot_jog_move.valueChanged.connect(self.CT_jog_vel_func)
        self.stop_CT_button.clicked.connect(self.stop_CT_func)

        # decoration
        self.line_vertical = QVSeparationLine()
        self.line_vertical2 = QVSeparationLine()
        self.line_vertical3 = QVSeparationLine()
        self.line_vertical4 = QVSeparationLine()

        # switch
        self.CT_vel_select = Switch()
        self.CT_vel_select.clicked.connect(self.CT_vel_func)
        self.CT_vel_select.setEnabled(False)
        self.CT_vel_low_label = QLabel()
        self.CT_vel_low_label.setText("5 deg/s")
        self.CT_vel_low_label.setAlignment(Qt.AlignCenter)
        self.CT_vel_high_label = QLabel()
        self.CT_vel_high_label.setText("20 deg/s")
        self.CT_vel_high_label.setAlignment(Qt.AlignCenter)

        # THREADS
        self.motion_hor = None
        self.motion_CT = None
        self.motion_vert = None
        self.motion_hor = None

        self.set_layout()

    def set_layout(self):
        """
        Layout of widgets. Using a grid to layout the items.
        The layout of the devices are by columns in sections.
        device: columns
        stop: 0 -1
        CT: 3 -6
        vertical: 8 - 10
        horizontal: 12 - 14
        shutter: 16 - 18
        vertical lines: 2, 7, 11, 15
        """
        layout = QGridLayout()
        # stop
        layout.addWidget(self.stop_motors_button, 2, 0, 1, 1)
        # CT
        layout.addWidget(self.connect_CT_mot_button, 2, 3)
        layout.addWidget(self.move_CT_mot_button, 2, 5)
        layout.addWidget(self.CT_mot_label, 0, 3, 1, 4)
        layout.addWidget(self.CT_mot_pos_move, 2, 4)
        layout.addWidget(self.CT_mot_rel_move, 3, 4)
        layout.addWidget(self.home_CT_mot_button, 2, 6)
        layout.addWidget(self.reset_CT_mot_button, 3, 6)
        layout.addWidget(self.CT_mot_value, 1, 4)
        layout.addWidget(self.move_CT_rel_plus, 3, 5)
        layout.addWidget(self.move_CT_rel_minus, 3, 3)
        # layout.addWidget(self.CT_vel_select, 4, 4)
        # layout.addWidget(self.CT_vel_low_label, 4, 3)
        # layout.addWidget(self.CT_vel_high_label, 4, 5)
        layout.addWidget(self.move_CT_jog_minus, 4, 3)
        layout.addWidget(self.CT_mot_jog_move, 4, 4)
        layout.addWidget(self.move_CT_jog_plus, 4, 5)
        layout.addWidget(self.stop_CT_button, 4, 6)

        # vertical
        layout.addWidget(self.vert_mot_label, 0, 8, 1, 3)
        layout.addWidget(self.connect_vert_mot_button, 2, 8)
        layout.addWidget(self.move_vert_mot_button, 2, 10)
        layout.addWidget(self.move_vert_rel_plus, 3, 10)
        layout.addWidget(self.move_vert_rel_minus, 3, 8)
        layout.addWidget(self.vert_mot_low_lim, 1, 8)
        layout.addWidget(self.vert_mot_value, 1, 9)
        layout.addWidget(self.vert_mot_high_lim, 1, 10)
        layout.addWidget(self.vert_mot_pos_move, 2, 9)
        layout.addWidget(self.vert_mot_rel_move, 3, 9)
        # horizontal
        layout.addWidget(self.hor_mot_label, 0, 12, 1, 3)
        layout.addWidget(self.connect_hor_mot_button, 2, 12)
        layout.addWidget(self.move_hor_mot_button, 2, 14)
        layout.addWidget(self.move_hor_rel_plus, 3, 14)
        layout.addWidget(self.move_hor_rel_minus, 3, 12)
        layout.addWidget(self.hor_mot_low_lim, 1, 12)
        layout.addWidget(self.hor_mot_value, 1, 13)
        layout.addWidget(self.hor_mot_high_lim, 1, 14)
        layout.addWidget(self.hor_mot_pos_move, 2, 13)
        layout.addWidget(self.hor_mot_rel_move, 3, 13)
        # shutter
        layout.addWidget(self.shutter_label, 0, 16, 1, 3)
        layout.addWidget(self.connect_shutter_button, 2, 16)
        layout.addWidget(self.open_shutter_button, 2, 18)
        layout.addWidget(self.close_shutter_button, 3, 18)
        layout.addWidget(self.shutter_status, 2, 17)
        # lines
        layout.addWidget(self.line_vertical, 0, 2, 5, 1)
        layout.addWidget(self.line_vertical2, 0, 7, 5, 1)
        layout.addWidget(self.line_vertical3, 0, 11, 5, 1)
        layout.addWidget(self.line_vertical4, 0, 15, 5, 1)
        # layout
        self.setLayout(layout)

    def connect_hor_motor_func(self):
        """Connect to horizontal stage motor."""
        try:
            self.hor_motor = CLSLinear("SMTR1605-2-B10-11:mm", encoded=True)
        except:
            error_message("Can not connect to horizontal stage, try again")
        if self.hor_motor is not None:
            self.hor_mot_value.setText("Position [mm]")
            self.connect_hor_mot_button.setEnabled(False)
            self.move_hor_mot_button.setEnabled(True)
            self.move_hor_rel_plus.setEnabled(True)
            self.move_hor_rel_minus.setEnabled(True)
            self.hor_mot_monitor = EpicsMonitorFloat(self.hor_motor.RBV)
            self.hor_mot_monitor.i0_state_changed_signal.connect(
                self.hor_mot_value.setText
            )
            self.hor_mot_monitor.i0.run_callback(self.hor_mot_monitor.call_idx)
            self.hor_mot_low_lim.setText("Min {}".format(0))
            self.hor_mot_high_lim.setText("Max {}".format(100))

    def connect_vert_motor_func(self):
        """Connect to vertical stage motor."""
        try:
            self.vert_motor = CLSLinear("SMTR1605-2-B10-10:mm", encoded=True)
        except:
            error_message("Can not connect to vertical stage, try again")
        if self.vert_motor is not None:
            self.vert_mot_value.setText("Position [mm]")
            self.connect_vert_mot_button.setEnabled(False)
            self.move_vert_mot_button.setEnabled(True)
            self.move_vert_rel_plus.setEnabled(True)
            self.move_vert_rel_minus.setEnabled(True)
            self.vert_mot_monitor = EpicsMonitorFloat(self.vert_motor.RBV)
            self.vert_mot_monitor.i0_state_changed_signal.connect(
                self.vert_mot_value.setText
            )
            self.vert_mot_monitor.i0.run_callback(self.vert_mot_monitor.call_idx)
            self.vert_mot_low_lim.setText("Min {} ".format(0))
            self.vert_mot_high_lim.setText("Max {}".format(40))

    def connect_CT_motor_func(self):
        """Connect to CT stage.
        In this case, ABRS is an air-bearing rotation stage."""
        try:
            self.CT_motor = ABRS("ABRS1605-01:deg", encoded=True)
        except:
            error_message("Could not connect to CT stage, try again")
        if self.CT_motor is not None:
            self.CT_mot_value.setText("Position [deg]")
            self.connect_CT_mot_button.setEnabled(False)
            self.move_CT_mot_button.setEnabled(True)
            self.move_CT_rel_plus.setEnabled(True)
            self.move_CT_rel_minus.setEnabled(True)
            self.home_CT_mot_button.setEnabled(True)
            self.reset_CT_mot_button.setEnabled(True)
            self.CT_vel_select.setEnabled(True)
            self.move_CT_jog_plus.setEnabled(True)
            self.move_CT_jog_minus.setEnabled(True)
            self.stop_CT_button.setEnabled(True)
            self.CT_motor.base_vel = 10.0 * q.deg / q.sec
            self.CT_mot_monitor = EpicsMonitorFloat(self.CT_motor.RBV)
            self.CT_mot_monitor.i0_state_changed_signal.connect(
                self.CT_mot_value.setText
            )
            self.CT_mot_monitor.i0.run_callback(self.CT_mot_monitor.call_idx)

    def connect_shutter_func(self):
        """Connect the shutter."""
        try:
            self.shutter = CLSShutter("ABRS1605-01:fis")
        except:
            error_message("Could not connect to fast imaging shutter, try again")
        if self.shutter is not None:
            self.shutter_status.setText("Connected")
            self.connect_shutter_button.setEnabled(False)
            self.open_shutter_button.setEnabled(True)
            self.close_shutter_button.setEnabled(True)
            self.shutter_monitor = EpicsMonitorFIS(
                self.shutter.STATE, self.shutter_status
            )
            self.shutter_monitor.i0_state_changed_signal.connect(
                self.shutter_status.setText
            )
            self.shutter_monitor.i0.run_callback(self.shutter_monitor.call_idx)

    def connect_time_motor_func(self):
        """Connect to a SimMotor."""
        try:
            self.time_motor = SimMotor(1.0 * q.mm)
        except:
            error_message("Can not connect to timer")

    def open_shutter_func(self):
        """Open shutter."""
        if self.shutter is None:
            return
        else:
            try:
                self.shutter.open().join()
            except TransitionNotAllowed:
                return

    def close_shutter_func(self):
        """Close shutter."""
        if self.shutter is None:
            return
        else:
            try:
                self.shutter.close().join()
            except TransitionNotAllowed:
                return

    def CT_home_func(self):
        """Home the stage."""
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
        """Move the stage to a selected position."""
        if self.CT_motor is None:
            return
        else:
            # self.CT_motor.stepvelocity = 5.0 * q.deg/q.sec
            self.CT_motor.stepvelocity = self.CT_motor.base_vel
            self.motion_CT = MotionThread(self.CT_motor, self.CT_mot_pos_move.value())
            self.motion_CT.start()

    def CT_rel_plus_func(self):
        """Move the stage a relative amount in positive direction."""
        if self.CT_motor is None:
            return
        else:
            # self.CT_motor.stepvelocity = 5.0 * q.deg/q.sec
            self.CT_motor.stepvelocity = self.CT_motor.base_vel
            self.motion_CT = MotionThread(
                self.CT_motor, self.CT_mot_pos_move.value(), self.CT_mot_rel_move.value(), 1
            )
            self.motion_CT.start()

    def CT_rel_minus_func(self):
        """Move the stage a relative amount in negative direction"""
        if self.CT_motor is None:
            return
        else:
            # self.CT_motor.stepvelocity = 5.0 * q.deg/q.sec
            self.CT_motor.stepvelocity = self.CT_motor.base_vel
            self.motion_CT = MotionThread(
                self.CT_motor, self.CT_mot_pos_move.value(), self.CT_mot_rel_move.value(), -1
            )
            self.motion_CT.start()

    def CT_jog_plus_func(self):
        """Start CT stage motion in the plus direction."""
        if self.CT_motor is None:
            return
        else:
            self.CT_motor.velocity = self.CT_motor.base_vel

    def CT_jog_minus_func(self):
        """Start CT stage motion in the minus direction."""
        if self.CT_motor is None:
            return
        else:
            self.CT_motor.velocity = self.CT_motor.base_vel * -1.0

    def CT_reset_func(self):
        """Reset the stage and move to home."""
        if self.CT_motor is None:
            return
        else:
            self.CT_motor.reset()
            self.CT_mot_pos_move.setValue(0.0)
            self.CT_move_func()
            info_message("Reset finished. Please wait for state motion to stop.")

    def CT_vel_func(self):
        """Select base velocity."""
        if self.CT_motor is None:
            return
        else:
            if self.CT_vel_select.isChecked():
                self.CT_motor.base_vel = 20 * q.deg / q.sec
            else:
                self.CT_motor.base_vel = 5 * q.deg / q.sec

    def CT_jog_vel_func(self):
        """Set base velocity"""
        if self.CT_motor is None:
            return
        else:
            self.CT_motor.base_vel = self.CT_mot_jog_move.value() * q.deg / q.sec

    def hor_move_func(self):
        """Move the horizontal motor to a selected position."""
        if self.hor_motor is None:
            return
        else:
            self.motion_hor = MotionThread(self.hor_motor, self.hor_mot_pos_move.value())
            self.motion_hor.start()

    def hor_rel_plus_func(self):
        """Move the horizontal motor a relative amount in positive direction."""
        if self.hor_motor is None:
            return
        else:
            self.motion_hor = MotionThread(
                self.hor_motor, self.hor_mot_pos_move.value(), self.hor_mot_rel_move.value(), 1
            )
            self.motion_hor.start()

    def hor_rel_minus_func(self):
        """Move the horizontal motor a relative amount in negative direction."""
        if self.hor_motor is None:
            return
        else:
            self.motion_hor = MotionThread(
                self.hor_motor, self.hor_mot_pos_move.value(), self.hor_mot_rel_move.value(), -1
            )
            self.motion_hor.start()

    def vert_move_func(self):
        """Move the vertical motor to a selected position."""
        if self.vert_motor is None:
            return
        else:
            self.motion_vert = MotionThread(self.vert_motor, self.vert_mot_pos_move.value())
            self.motion_vert.start()

    def vert_rel_plus_func(self):
        """Move the vertical motor a relative amount in positive direction."""
        if self.vert_motor is None:
            return
        else:
            self.motion_vert = MotionThread(
                self.vert_motor, self.vert_mot_pos_move.value(), self.vert_mot_rel_move.value(), 1
            )
            self.motion_vert.start()

    def vert_rel_minus_func(self):
        """Move the vertical motor a relative amount in negative direction."""
        if self.vert_motor is None:
            return
        else:
            self.motion_vert = MotionThread(
                self.vert_motor, self.vert_mot_pos_move.value(), self.vert_mot_rel_move.value(), -1
            )
            self.motion_vert.start()

    def stop_motors_func(self):
        # pyqt threads
        if self.motion_CT is not None:
            self.motion_CT.abort()
            self.motion_CT.stop()
        if self.CT_motor is not None:
            if self.CT_motor.state in ["hard-limit", "moving"]:
                self.CT_motor.stop().join()
        if self.motion_vert is not None:
            self.motion_vert.abort()
            self.motion_CT.stop()
        if self.motion_hor is not None:
            self.motion_hor.abort()
            self.motion_CT.stop()
        # concert devices
        device_abort(m for m in self.motors if m is not None)

    def stop_CT_func(self):
        if self.motion_CT is not None:
            self.motion_CT.abort()
            self.motion_CT.stop()
        if self.CT_motor is not None:
            if self.CT_motor.state in ["hard-limit", "moving"]:
                self.CT_motor.stop().join()


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

    def __init__(self, PV, label):
        super(EpicsMonitorFIS, self).__init__()
        self.i0 = PV
        self.call_idx = PV.add_callback(self.on_i0_state_changed)
        self.value = None
        self.label = label

    def on_i0_state_changed(self, value, **kwargs):
        """
        :param value: the latest value from the PV
        :param kwargs: the rest of arguments
        :return: None
        """
        self.value = value
        if value == 1:
            value_str = "Open"
            self.label.setStyleSheet("color: green")
        elif value == 2:
            value_str = "Between"
            self.label.setStyleSheet("color: yellow")
        elif value == 4:
            value_str = "Closed"
            self.label.setStyleSheet("color: red")
        else:
            value_str = "Error"
            self.label.setStyleSheet("color: red")
        self.i0_state_changed_signal.emit(value_str)


class MotionThread(QThread):
    motion_over_signal = pyqtSignal(bool)
    def __init__(self, motor, position, rel_position=None, direction=1):
        super(MotionThread, self).__init__()
        self.motor = motor
        self.thread_running = True
        atexit.register(self.stop)
        self.position = position # just number not qspinbox
        self.rel_position = rel_position
        self.direction = direction
        self.is_moving = False

    def stop(self):
        self.thread_running = False
        self.wait()

    def run(self):  # .start() calls this function
        while self.thread_running:
            final_pos = self.motor.position
            self.is_moving = True
            try:
                if not hasattr(self.motor, 'timer'):
                    if self.rel_position is None:
                        final_pos = self.position * self.motor.UNITS
                    else:
                        final_pos += (
                            self.rel_position * self.direction * self.motor.UNITS
                        )
                    self.motor.position = final_pos
                else:
                    sleep(self.position)
                self.is_moving = False
                self.motion_over_signal.emit(True)
                self.thread_running = False
            except TransitionNotAllowed:
                error_message("Stage is moving. Wait until motion has stopped.")
                self.is_moving = False
                self.thread_running = False

    def abort(self):
        self.is_moving = False
        try:
            self.motor.abort()
            self.thread_running = False
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
