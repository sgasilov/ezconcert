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
        self.motor_label = QLabel()
        self.motor_label.setText("MOTOR")
        self.motor = QComboBox()
        self.motor.addItems(["Horizontal", "Vertical"])

        self.ffctravel_label = QLabel()
        self.ffctravel_label.setText("Travel to move sample out")
        self.ffctravel_entry = QLineEdit()
        self.ffctravel_unit_label = QLabel()
        self.ffctravel_unit_label.setText("[mm]")

        self.numflats_label = QLabel()
        self.numflats_label.setText("Num of flats")
        self.numflats_entry = QLineEdit()
        self.numflats_entry.setText("10")

        self.numdarks_label = QLabel()
        self.numdarks_label.setText("Num of darks")
        self.numdarks_entry = QLineEdit()
        self.numdarks_entry.setText("10")

        self.getflatsdarks_button = QPushButton("ACQUIRE FLATS AND DARKS")
        self.getflatsdarks_button.clicked.connect(self.getflatsdarks)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        layout.addWidget(self.motor_label, 0, 0)
        layout.addWidget(self.motor, 0, 1)
        layout.addWidget(self.ffctravel_label, 0, 2)
        layout.addWidget(self.ffctravel_entry, 0, 3)
        layout.addWidget(self.ffctravel_unit_label, 0, 4)
        layout.addWidget(self.numflats_label, 0, 5)
        layout.addWidget(self.numflats_entry, 0, 6)
        layout.addWidget(self.numdarks_label, 0, 7)
        layout.addWidget(self.numdarks_entry, 0, 8)
        layout.addWidget(self.getflatsdarks_button, 0, 9)

        # layout = QHBoxLayout()
        # layout.addWidget(self.motor_label)
        # layout.addWidget(self.motor)
        # layout.addWidget(self.ffctravel_label)
        # layout.addWidget(self.ffctravel_entry)
        # layout.addWidget(self.ffctravel_unit_label)
        # layout.addStretch()
        # layout.addWidget(self.numflats_label)
        # layout.addWidget(self.numflats_entry)
        # layout.addStretch()
        # layout.addWidget(self.numdarks_label)
        # layout.addWidget(self.numdarks_entry)

        self.setLayout(layout)

    def getflatsdarks(self):
        info_message("Acquiring flats and darks")
        self.getflatsdarks_button.setEnabled(False)
        self.getflatsdarks_button.setEnabled(True)