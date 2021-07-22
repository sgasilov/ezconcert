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
        self.start_label.setText("START POSITION")
        self.steps_label = QLabel()
        self.steps_label.setText("NUMBER OF POINTS")
        self.range_label = QLabel()
        self.range_label.setText("RANGE")
        self.step_size_label = QLabel()
        self.step_size_label.setText("OR STEP SIZE")
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
        self.outer_loop_start_entry = QLineEdit()
        self.outer_loop_steps_entry = QLineEdit()
        self.outer_loop_steps_entry.setText('0')
        self.outer_loop_range_entry = QLineEdit()
        self.outer_loop_range_entry.setText('0')
        self.outer_loop_step_size_entry = QLineEdit()
        self.outer_loop_step_size_entry.setText('0')
        self.outer_loop_endpoint = QCheckBox("Include")
        self.outer_loop_endpoint.setChecked(True)
        self.outer_loop_flats_1 = QCheckBox("After")
        self.outer_loop_flats_1.setChecked(False)
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
        self.inner_loop_step_size_entry = QLineEdit()
        self.inner_loop_step_size_entry.setText("0.18")
        self.inner_loop_endpoint = QCheckBox("Include")
        self.inner_loop_flats_1 = QCheckBox("After")
        self.inner_loop_continuous = QCheckBox("On-the-fly")
        self.inner_loop_continuous.setChecked(True)
        self.inner_loop_continuous.setEnabled(False)

        # OPTIONAL, BOTTOM LINE
        #TTL with Dimax
        self.DimaxAccuTTLsLabel = QLabel()
        self.DimaxAccuTTLsLabel.setText("For Dimax only")
        self.readout_intheend = QCheckBox("Readout in the end")
        self.readout_intheend.setEnabled(False)

        # delayed start
        self.delay_start_label = QLabel()
        self.delay_start_label.setText("Delay exp. start by [min]")
        self.delay_start_entry = QLineEdit()
        self.delay_start_entry.setText('0')
        self.delay_start_entry.setFixedWidth(50)

        #signals
        self.outer_loop_flats_0.stateChanged.connect(self.constrain_flats_before)
        self.outer_loop_flats_1.stateChanged.connect(self.constrain_flats_after)
        self.inner_loop_step_size_entry.editingFinished.connect(self.get_inner_range)
        self.inner_loop_range_entry.editingFinished.connect(self.get_inner_step_size)
        self.outer_loop_range_entry.editingFinished.connect(self.get_outer_step_size)
        self.outer_loop_step_size_entry.editingFinished.connect(self.get_outer_range)
        self.set_layout()

        #check input
        self.input_correct = True

    def set_layout(self):
        layout = QGridLayout()
        # Buttons on top
        layout.addWidget(self.start_button, 0, 0, 1, 2)
        layout.addWidget(self.abort_button, 0, 2, 1, 2)
        layout.addWidget(self.return_button, 0, 4, 1, 2)
        layout.addWidget(self.delay_start_label, 0, 6)
        layout.addWidget(self.delay_start_entry, 0, 7)
        layout.addWidget(self.readout_intheend, 0, 9)

        # Top labels
        layout.addWidget(self.motor_label, 1, 1)
        layout.addWidget(self.flats0_label, 1, 2)
        layout.addWidget(self.start_label, 1, 3)
        layout.addWidget(self.steps_label, 1, 4)
        layout.addWidget(self.range_label, 1, 5)
        layout.addWidget(self.step_size_label, 1, 6)
        layout.addWidget(self.endpoint_label, 1, 7)
        layout.addWidget(self.flats1_label, 1, 8)
        layout.addWidget(self.continuous_label, 1, 9)

        # Outer loop
        layout.addWidget(self.outer_loop_label, 2, 0)
        layout.addWidget(self.outer_loop_motor, 2, 1)
        layout.addWidget(self.outer_loop_flats_0, 2, 2)
        layout.addWidget(self.outer_loop_start_entry, 2, 3)
        layout.addWidget(self.outer_loop_steps_entry, 2, 4)
        layout.addWidget(self.outer_loop_range_entry, 2, 5)
        layout.addWidget(self.outer_loop_step_size_entry, 2, 6)
        layout.addWidget(self.outer_loop_endpoint, 2, 7)
        layout.addWidget(self.outer_loop_flats_1, 2, 8)
        layout.addWidget(self.outer_loop_continuous, 2, 9)
        # layout.addWidget(self.ttl_scan, 2, 8)

        # Inner loop
        layout.addWidget(self.inner_loop_label, 3, 0)
        layout.addWidget(self.inner_loop_motor, 3, 1)
        layout.addWidget(self.inner_loop_flats_0, 3, 2)
        layout.addWidget(self.inner_loop_start_entry, 3, 3)
        layout.addWidget(self.inner_loop_steps_entry, 3, 4)
        layout.addWidget(self.inner_loop_range_entry, 3, 5)
        layout.addWidget(self.inner_loop_step_size_entry, 3, 6)
        layout.addWidget(self.inner_loop_endpoint, 3, 7)
        layout.addWidget(self.inner_loop_flats_1, 3, 8)
        layout.addWidget(self.inner_loop_continuous, 3, 9)

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

    @property
    def delay_time(self):
        try:
            x = int(self.delay_start_entry.text())
        except ValueError:
            error_message("Delay start time must be non-negative integer number")
            self.input_correct = False
            return -1
        if x < 0:
            error_message("Delay start time must be non-negative integer number.")
            self.input_correct = False
            return -1
        return x

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

    def get_inner_range(self):
        x = self.inner_step_size
        try:
            if self.inner_endpoint:
                self.inner_loop_range_entry.setText(str(x*(self.inner_steps-1)))
            else:
                self.inner_loop_range_entry.setText(str(x * self.inner_steps))
        except:
            pass


    @property
    def inner_step_size(self):
        try:
            x = float(self.inner_loop_step_size_entry.text())
        except ValueError:
            error_message("Step size must be a number")
            self.input_correct = False
        return x

    def get_inner_step_size(self):
        if self.inner_endpoint:
            try:
                self.inner_loop_step_size_entry.setText(
                    str(self.inner_range/(self.inner_steps-1)))
            except:
                pass
        else:
            try:
                self.inner_loop_step_size_entry.setText(
                    str(self.inner_range/self.inner_steps))
            except:
                pass

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

    def get_outer_range(self):
        x = self.outer_step_size
        try:
            if self.outer_endpoint:
                self.outer_loop_range_entry.setText(str(x*(self.outer_steps-1)))
            else:
                self.outer_loop_range_entry.setText(str(x * self.outer_steps))
        except:
            pass

    @property
    def outer_step_size(self):
        try:
            x = float(self.outer_loop_step_size_entry.text())
        except ValueError:
            error_message("Step size must be a number")
            self.input_correct = False
        return x

    def get_outer_step_size(self):
        if self.outer_endpoint:
            try:
                self.outer_loop_step_size_entry.setText(
                    str(self.outer_range/(self.outer_steps-1)))
            except:
                pass
        else:
            try:
                self.outer_loop_step_size_entry.setText(
                    str(self.outer_range/self.outer_steps))
            except:
                pass

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

    def ena_disa_all_entries(self, v=True):
        self.readout_intheend.setEnabled(v)
        self.outer_loop_motor.setEnabled(v)
        self.outer_loop_flats_0.setEnabled(v)
        self.outer_loop_start_entry.setEnabled(v)
        self.outer_loop_steps_entry.setEnabled(v)
        self.outer_loop_range_entry.setEnabled(v)
        self.outer_loop_step_size_entry.setEnabled(v)
        self.outer_loop_endpoint.setEnabled(v)
        self.outer_loop_flats_1.setEnabled(v)
        #self.outer_loop_continuous.setEnabled(v)
        self.inner_loop_motor.setEnabled(v)
        self.inner_loop_flats_0.setEnabled(v)
        self.inner_loop_start_entry.setEnabled(v)
        self.inner_loop_steps_entry.setEnabled(v)
        self.inner_loop_range_entry.setEnabled(v)
        self.inner_loop_step_size_entry.setEnabled(v)
        self.inner_loop_endpoint.setEnabled(v)
        self.inner_loop_flats_1.setEnabled(v)
        self.delay_start_entry.setEnabled(v)
        #self.inner_loop_continuous.setEnabled(v)
        
        

