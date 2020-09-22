from random import choice
from time import sleep

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, QPushButton, QComboBox, QCheckBox

from message_dialog import info_message, error_message
from scans_concert import ConcertScanThread
import epics


def scan_dummy():
    sleep(10)
    return choice(["Scan completed", "Scan failed"])


def abort_dummy():
    sleep(1)


def return_to_position_dummy():
    sleep(5)
    return choice(["Returned to position!", "Failed to complete motor move"])


class ScanControlsGroup(QGroupBox):
    """
    Camera controls
    """

    def __init__(self, start_button, abort_button, return_button,
                 scan_fps_entry, ffc_button, p180_button,
                 motor_inner, motor_outer, *args, **kwargs):
        super(ScanControlsGroup, self).__init__(*args, **kwargs)
        # Timer - just as example
        self.timer = QTimer()

        # physical devices
        self.motor_inner = motor_inner
        self.motor_outer = motor_outer

        # Buttons
        self.start_button = start_button
        self.abort_button = abort_button
        self.return_button = return_button
        self.ffc_button = ffc_button
        self.p180_button = p180_button
        # FPS indicator
        self.scan_fps_label = QLabel()
        self.scan_fps_label.setText("Average fps")
        self.scan_fps_entry = scan_fps_entry

        # "Table headers"
        self.motor_label = QLabel()
        self.motor_label.setText("MOTOR")
        self.start_label = QLabel()
        self.start_label.setText("START")
        self.steps_label = QLabel()
        self.steps_label.setText("STEPS")
        self.range_label = QLabel()
        self.range_label.setText("RANGE")
        self.endpoint_label = QLabel()
        self.endpoint_label.setText("Endpoint")
        self.continuous_label = QLabel()
        self.continuous_label.setText("Motion")

        # Outer loop
        self.outer_loop_label = QLabel()
        self.outer_loop_label.setText("Outer loop")
        self.outer_loop_motor = QComboBox()
        #self.outer_loop_motor.addItems(["Vertical [mm]", "Time [sec]"])
        self.outer_loop_start_entry = QLineEdit()
        self.outer_loop_steps_entry = QLineEdit()
        self.outer_loop_range_entry = QLineEdit()
        self.outer_loop_endpoint = QCheckBox("Include")
        self.outer_loop_continuous = QCheckBox("CONTINUOUS")
        self.outer_loop_continuous.setChecked(False)
        self.outer_loop_continuous.setCheckable(False)

        # Inner loop
        self.inner_loop_label = QLabel()
        self.inner_loop_label.setText("Inner loop")
        self.inner_loop_motor = QComboBox()
        #self.inner_loop_motor.addItems(["CT [deg]", "Time [sec]", "ACry [urad]", "Horizontal [mm]"])
        self.inner_loop_flats_0 = QCheckBox("FLATS BEFORE")
        self.inner_loop_start_entry = QLineEdit()
        self.inner_loop_start_entry.setText("0")
        self.inner_loop_steps_entry = QLineEdit()
        self.inner_loop_steps_entry.setText("5")
        self.inner_loop_range_entry = QLineEdit()
        self.inner_loop_range_entry.setText("10")
        self.inner_loop_endpoint = QCheckBox("Include")
        self.inner_loop_flats_1 = QCheckBox("FLATS AFTER")
        self.inner_loop_continuous = QCheckBox("ON-THE-FLY")
        self.inner_loop_continuous.setChecked(False)
        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        # Buttons on top
        layout.addWidget(self.start_button, 0, 0, 1, 2)
        layout.addWidget(self.abort_button, 0, 2, 1, 2)
        layout.addWidget(self.return_button, 0, 4, 1, 2)
        layout.addWidget(self.scan_fps_label, 0, 6)
        layout.addWidget(self.ffc_button, 0, 7)
        layout.addWidget(self.p180_button, 0, 8)

        # Top labels
        layout.addWidget(self.motor_label, 1, 1)
        layout.addWidget(self.start_label, 1, 3)
        layout.addWidget(self.steps_label, 1, 4)
        layout.addWidget(self.range_label, 1, 5)
        layout.addWidget(self.endpoint_label, 1, 6)
        layout.addWidget(self.continuous_label, 1, 8)

        # Outer loop
        layout.addWidget(self.outer_loop_label, 2, 0)
        layout.addWidget(self.outer_loop_motor, 2, 1)
        layout.addWidget(self.outer_loop_start_entry, 2, 3)
        layout.addWidget(self.outer_loop_steps_entry, 2, 4)
        layout.addWidget(self.outer_loop_range_entry, 2, 5)
        layout.addWidget(self.outer_loop_endpoint, 2, 6)
        layout.addWidget(self.outer_loop_continuous, 2, 8)

        # Inner loop
        layout.addWidget(self.inner_loop_label, 3, 0)
        layout.addWidget(self.inner_loop_motor, 3, 1)
        layout.addWidget(self.inner_loop_flats_0, 3, 2)
        layout.addWidget(self.inner_loop_start_entry, 3, 3)
        layout.addWidget(self.inner_loop_steps_entry, 3, 4)
        layout.addWidget(self.inner_loop_range_entry, 3, 5)
        layout.addWidget(self.inner_loop_endpoint, 3, 6)
        layout.addWidget(self.inner_loop_flats_1, 3, 7)
        layout.addWidget(self.inner_loop_continuous, 3, 8)

        for column in range(8):
            layout.setColumnStretch(column, 1)

        self.setLayout(layout)

    @property
    def inner_motor(self):
        try:
            return self.inner_loop_motor.currentText()
        except ValueError:
            return None

    @property
    def inner_steps(self):
        try:
            return int(self.inner_loop_steps_entry.text())
        except ValueError:
            return None

    @property
    def inner_start(self):
        try:
            return float(self.inner_loop_start_entry.text())
        except ValueError:
            return None

    @property
    def inner_range(self):
        try:
            return int(self.inner_loop_range_entry.text())
        except ValueError:
            return None

    @property
    def inner_endpoint(self):
        return self.inner_loop_endpoint.isChecked()

    @property
    def ffc_before(self):
        return self.inner_loop_flats_0.isChecked()

    @property
    def ffc_after(self):
        return self.inner_loop_flats_1.isChecked()

    @property
    def inner_cont(self):
        return self.inner_loop_continuous.isChecked()
