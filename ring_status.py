import atexit
from random import choice
from time import sleep

from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, QPushButton, QComboBox

from epics import PV
from message_dialog import info_message

class RingStatusGroup(QGroupBox):
    """
    Camera controls
    """

    def __init__(self, *args, **kwargs):
        # Timer - just as example
        super(RingStatusGroup, self).__init__(*args, **kwargs)
        self.timer = QTimer()

        # Ring current
        self.ringcurrent_label = QLabel()
        self.ringcurrent_label.setText("Ring current [mA]")
        #self.ringcurrent_entry = QLineEdit()
        self.ringcurrent_entry = QLabel()
        self.ringcurrent_entry.setFixedWidth(50)
        self.epics_monitor = EpicsMonitor()
        self.epics_monitor.i0_state_changed_signal.connect(self.ringcurrent_entry.setText)

        # Ring status
        self.ringstatus_spacer = QLabel()
        self.ringstatus_label = QLabel()
        self.ringstatus_label.setText("Ring state")
        self.ringstatus_entry = QLabel()
        self.ringstatus_entry.setFixedWidth(50)

        # injection in
        self.inj_countdown_spacer = QLabel()
        self.inj_countdown_label = QLabel()
        self.inj_countdown_label.setText("Injection in [sec]")
        self.inj_countdown_entry = QLabel()
        self.inj_countdown_entry.setFixedWidth(50)

        self.set_layout()


    def set_layout(self):
        layout = QGridLayout()
        # Buttons on top
        layout.addWidget(self.ringcurrent_label, 0, 0)
        layout.addWidget(self.ringcurrent_entry, 0, 1)

        layout.addWidget(self.ringstatus_spacer, 0, 2)
        layout.addWidget(self.ringstatus_label, 0, 3)
        layout.addWidget(self.ringstatus_entry, 0, 4)

        layout.addWidget(self.inj_countdown_spacer, 0, 5)
        layout.addWidget(self.inj_countdown_label, 0, 6)
        layout.addWidget(self.inj_countdown_entry, 0, 7)

        self.setLayout(layout)


I0_PV = "PCT1402-01:mA:fbk"
class EpicsMonitor(QObject):
    i0_state_changed_signal = pyqtSignal(str)

    def __init__(self):
        super(EpicsMonitor, self).__init__()
        self.i0 = PV(I0_PV, callback=self.on_i0_state_changed)

    def on_i0_state_changed(self, value, **kwargs):
        """
        :param value: the latest value from the PV
        :param kwargs: the rest of arguments
        :return: None
        """
        self.i0_state_changed_signal.emit("{:.1f}".format(value))