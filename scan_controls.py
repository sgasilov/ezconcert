from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, \
    QPushButton, QComboBox, QCheckBox

from message_dialog import info_message, error_message


class ScanControlsGroup(QGroupBox):
    """
    Camera controls
    """

    def __init__(self, start_button, abort_button, return_button,
                 scan_fps_entry,
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

        # "Table headers"
        self.motor_label = QLabel()
        self.motor_label.setText("MOTOR")
        self.flats0_label = QLabel()
        self.flats0_label.setText("FLATS")
        self.start_label = QLabel()
        self.start_label.setText("START")
        self.steps_label = QLabel()
        self.steps_label.setText("NUM POINTS")
        self.range_label = QLabel()
        self.range_label.setText("RANGE")
        self.endpoint_label = QLabel()
        self.endpoint_label.setText("ENDPOINT")
        self.flats1_label = QLabel()
        self.flats1_label.setText("FLATS")
        self.continuous_label = QLabel()
        self.continuous_label.setText("MOTION")

        # Outer loop
        self.outer_loop_label = QLabel()
        self.outer_loop_label.setText("Outer loop")
        self.outer_loop_motor = QComboBox()
        self.outer_loop_flats_0 = QCheckBox("Before")
        self.outer_loop_flats_0.setChecked(False)
        #self.outer_loop_flats_0.setEnabled(False)
        self.outer_loop_start_entry = QLineEdit()
        self.outer_loop_steps_entry = QLineEdit()
        #self.outer_loop_steps_entry.setText("0")
        self.outer_loop_range_entry = QLineEdit()
        self.outer_loop_endpoint = QCheckBox("Include")
        self.outer_loop_endpoint.setChecked(True)
        self.outer_loop_flats_1 = QCheckBox("After")
        self.outer_loop_flats_1.setChecked(False)
        #self.outer_loop_flats_1.setEnabled(False)
        self.outer_loop_continuous = QCheckBox("On-the-fly")
        self.outer_loop_continuous.setChecked(False)
        self.outer_loop_continuous.setEnabled(False)

        # Inner loop
        self.inner_loop_label = QLabel()
        self.inner_loop_label.setText("Inner loop")
        self.inner_loop_motor = QComboBox()
        self.inner_loop_flats_0 = QCheckBox("Before")
        self.inner_loop_start_entry = QLineEdit()
        self.inner_loop_start_entry.setText("0")
        self.inner_loop_steps_entry = QLineEdit()
        self.inner_loop_steps_entry.setText("1000")
        self.inner_loop_range_entry = QLineEdit()
        self.inner_loop_range_entry.setText("180")
        self.inner_loop_endpoint = QCheckBox("Include")
        self.inner_loop_flats_1 = QCheckBox("After")
        self.inner_loop_continuous = QCheckBox("On-the-fly")
        self.inner_loop_continuous.setChecked(True)
        self.inner_loop_continuous.setEnabled(False)

        # TTL
        self.ttl_scan = QCheckBox("TTL scan")
        self.ttl_scan.setChecked(False)

        #signals
        self.outer_loop_flats_0.stateChanged.connect(self.constrain_flats_before)
        self.outer_loop_flats_1.stateChanged.connect(self.constrain_flats_after)
        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        # Buttons on top
        layout.addWidget(self.start_button, 0, 0, 1, 2)
        layout.addWidget(self.abort_button, 0, 2, 1, 2)
        layout.addWidget(self.return_button, 0, 4, 1, 2)
        # layout.addWidget(self.scan_fps_label, 0, 6)
        # layout.addWidget(self.ffc_button, 0, 7)
        # layout.addWidget(self.p180_button, 0, 8)

        # Top labels
        layout.addWidget(self.motor_label, 1, 1)
        layout.addWidget(self.flats0_label, 1, 2)
        layout.addWidget(self.start_label, 1, 3)
        layout.addWidget(self.steps_label, 1, 4)
        layout.addWidget(self.range_label, 1, 5)
        layout.addWidget(self.endpoint_label, 1, 6)
        layout.addWidget(self.flats1_label, 1, 7)
        layout.addWidget(self.continuous_label, 1, 8)

        # Outer loop
        layout.addWidget(self.outer_loop_label, 2, 0)
        layout.addWidget(self.outer_loop_motor, 2, 1)
        layout.addWidget(self.outer_loop_flats_0, 2, 2)
        layout.addWidget(self.outer_loop_start_entry, 2, 3)
        layout.addWidget(self.outer_loop_steps_entry, 2, 4)
        layout.addWidget(self.outer_loop_range_entry, 2, 5)
        layout.addWidget(self.outer_loop_endpoint, 2, 6)
        layout.addWidget(self.outer_loop_flats_1, 2, 7)
        layout.addWidget(self.outer_loop_continuous, 2, 8)
        # layout.addWidget(self.ttl_scan, 2, 8)

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

    def constrain_flats_before(self):
        if self.outer_loop_flats_0.isChecked():
            self.inner_loop_flats_0.setChecked(False)
            self.inner_loop_flats_0.setEnabled(False)
        else:
            self.inner_loop_flats_0.setEnabled(True)

    def constrain_flats_after(self):
        if self.outer_loop_flats_1.isChecked():
            self.inner_loop_flats_1.setChecked(False)
            self.inner_loop_flats_1.setEnabled(False)
        else:
            self.inner_loop_flats_1.setEnabled(True)

    # INNER LOOP
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
            return float(self.inner_loop_range_entry.text())
        except ValueError:
            return None

    @property
    def inner_endpoint(self):
        return self.inner_loop_endpoint.isChecked()

    @property
    def inner_cont(self):
        return self.inner_loop_continuous.isChecked()

    @property
    def ttl_set(self):
        return self.ttl_scan.isChecked()

    # OUTER LOOP
    @property
    def outer_motor(self):
        try:
            return self.outer_loop_motor.currentText()
        except ValueError:
            return None

    @property
    def outer_steps(self):
        if self.outer_loop_steps_entry.text() == "":
            return 0
        try:
            return int(self.outer_loop_steps_entry.text())
        except ValueError:
            error_message("Number of steps must be positive integer number")
            return None

    @property
    def outer_start(self):
        try:
            return float(self.outer_loop_start_entry.text())
        except ValueError:
            error_message("Starting point must be floating point number")
            return None

    @property
    def outer_range(self):
        try:
            return float(self.outer_loop_range_entry.text())
        except ValueError:
            error_message("Range must be floating point number")
            return None

    @property
    def outer_endpoint(self):
        return self.outer_loop_endpoint.isChecked()

    # Flat fields controls
    @property
    def ffc_before(self):
        return self.inner_loop_flats_0.isChecked()

    @property
    def ffc_after(self):
        return self.inner_loop_flats_1.isChecked()

    @property
    def ffc_before_outer(self):
        return self.outer_loop_flats_0.isChecked()

    @property
    def ffc_after_outer(self):
        return self.outer_loop_flats_1.isChecked()


