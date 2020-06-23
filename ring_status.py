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

        self.ringcurrent_label = QLabel()
        self.ringcurrent_label.setText("Ring current [mA]")
        self.ringcurrent_entry = QLineEdit()
        self.ringcurrent_entry.setFixedWidth(50)

        self.epics_monitor = EpicsMonitor()
        self.epics_monitor.i0_state_changed_signal.connect(self.ringcurrent_entry.setText)

        self.set_layout()


    def set_layout(self):
        layout = QGridLayout()
        # Buttons on top
        layout.addWidget(self.ringcurrent_label, 0, 0)
        layout.addWidget(self.ringcurrent_entry, 0, 1)
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
        self.i0_state_changed_signal.emit("{:.3f}".format(value))
