from PyQt5.QtWidgets import QGridLayout, QHBoxLayout
from PyQt5.QtWidgets import QLabel, QGroupBox, QLineEdit, QPushButton, QComboBox, QCheckBox

from message_dialog import info_message


class FFCSettingsGroup(QGroupBox):
    """
    Flat-field correction settings
    """

    def __init__(self, motor, *args, **kwargs):
        super(FFCSettingsGroup, self).__init__(*args, **kwargs)

        self.motor = motor
        self.motor_options_label = QLabel()
        self.motor_options_label.setText("MOTOR")
        self.motor_options_entry = QComboBox()
        #self.motor_options_entry.addItems(["Horizontal [mm]", "Vertical [mm]"])

        # motor positions
        self.flat_position_label = QLabel()
        self.flat_position_label.setText("Flat position [mm]")
        self.flat_position_entry = QLineEdit()
        self.radio_position_label = QLabel()
        self.radio_position_label.setText("Radio position [mm]")
        self.radio_position_entry = QLineEdit()

        # number of flats and darks
        self.numflats_label = QLabel()
        self.numflats_label.setText("Num of flats")
        self.numflats_entry = QLineEdit()
        self.numflats_entry.setText("10")
        self.numdarks_label = QLabel()
        self.numdarks_label.setText("Num of darks")
        self.numdarks_entry = QLineEdit()
        self.numdarks_entry.setText("10")

        # acquire button and motor position indicators
        # self.getflatsdarks_button = guibutton

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        layout.addWidget(self.motor_options_label, 0, 0)
        layout.addWidget(self.motor_options_entry, 0, 1)
        layout.addWidget(self.radio_position_label, 0, 2)
        layout.addWidget(self.radio_position_entry, 0, 3)
        layout.addWidget(self.flat_position_label, 0, 4)
        layout.addWidget(self.flat_position_entry, 0, 5)
        layout.addWidget(self.numflats_label, 0, 6)
        layout.addWidget(self.numflats_entry, 0, 7)
        layout.addWidget(self.numdarks_label, 0, 8)
        layout.addWidget(self.numdarks_entry, 0, 9)

        # layout.addWidget(self.getflatsdarks_button, 1, 0)

        self.setLayout(layout)

    @property
    def flat_motor(self):
        try:
            return self.motor_options_entry.currentText()
        except ValueError:
            return None

    @property
    def flat_position(self):
        try:
            return float(self.flat_position_entry.text())
        except ValueError:
            return None

    @property
    def radio_position(self):
        try:
            return float(self.radio_position_entry.text())
        except ValueError:
            return None

    @property
    def num_flats(self):
        try:
            return int(self.numflats_entry.text())
        except ValueError:
            return None

    @property
    def num_darks(self):
        try:
            return int(self.numdarks_entry.text())
        except ValueError:
            return None
