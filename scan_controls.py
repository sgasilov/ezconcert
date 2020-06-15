from random import choice
from time import sleep

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, QPushButton, QComboBox, QCheckBox

from message_dialog import info_message, error_message


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

    def __init__(self, *args, **kwargs):
        super(ScanControlsGroup, self).__init__(*args, **kwargs)
        # Timer - just as example
        self.timer = QTimer()

        # Buttons
        self.start_button = QPushButton("START")
        self.start_button.clicked.connect(self.start)

        self.abort_button = QPushButton("ABORT")
        self.abort_button.setEnabled(False)
        self.abort_button.clicked.connect(self.abort)

        self.return_button = QPushButton("RETURN")
        self.return_button.clicked.connect(self.return_to_position)

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
        self.outer_loop_motor.addItems(["Vertical [mm]", "Time [sec]"])
        self.outer_loop_start_entry = QLineEdit()
        self.outer_loop_steps_entry = QLineEdit()
        self.outer_loop_range_entry = QLineEdit()
        self.outer_loop_endpoint = QCheckBox("Include")
        self.outer_loop_continuous = QCheckBox("CONTINUOUS")

        # Inner loop
        self.inner_loop_label = QLabel()
        self.inner_loop_label.setText("Inner loop")
        self.inner_loop_motor = QComboBox()
        self.inner_loop_motor.addItems(["CT [deg]", "Time [sec]", "ACry [urad]", "Horizontal [mm]"])
        self.inner_loop_flats_0 = QCheckBox("FLATS BEFORE")
        self.inner_loop_start_entry = QLineEdit()
        self.inner_loop_start_entry.setText("0")
        self.inner_loop_steps_entry = QLineEdit()
        self.inner_loop_steps_entry.setText("2000")
        self.inner_loop_range_entry = QLineEdit()
        self.inner_loop_range_entry.setText("180")
        self.inner_loop_endpoint = QCheckBox("Include")
        self.inner_loop_flats_1 = QCheckBox("FLATS AFTER")
        self.inner_loop_continuous = QCheckBox("CONTINUOUS")
        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        # Buttons on top
        layout.addWidget(self.start_button, 0, 0, 1, 2)
        layout.addWidget(self.abort_button, 0, 2, 1, 2)
        layout.addWidget(self.return_button, 0, 4, 1, 2)

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
        layout.addWidget(self.inner_loop_endpoint,3, 6)
        layout.addWidget(self.inner_loop_flats_1, 3, 7)
        layout.addWidget(self.inner_loop_continuous, 3, 8)

        for column in range(8):
            layout.setColumnStretch(column, 1)

        self.setLayout(layout)

    def inner_loop_steps(self):
        return int(self.inner_loop_steps_entry.text())

    def outer_loop_steps(self):
        return int(self.outer_loop_steps_entry.text())

    def check_parameters(self):
        # Just checking type conversion here
        try:
            self.inner_loop_steps()
            self.outer_loop_steps()
        except ValueError:
            return False
        return True

    def start(self):
        if not self.check_parameters():
            error_message("Parameters check failed")
            return

        self.start_button.setEnabled(False)
        self.abort_button.setEnabled(True)
        self.return_button.setEnabled(False)
        info_message("Scan ON")
        # call scan command instead
        result = scan_dummy()
        info_message(result)

    def abort(self):
        # call abort command instead
        abort_dummy()
        info_message("Scan OFF")
        self.start_button.setEnabled(True)
        self.abort_button.setEnabled(False)
        self.return_button.setEnabled(True)

    def return_to_position(self):
        info_message("Returning to position...")
        result = return_to_position_dummy()
        info_message(result)
