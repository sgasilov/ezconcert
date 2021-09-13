import atexit
from random import choice
from time import sleep

from PyQt5.QtCore import pyqtSignal, QObject
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QCheckBox

from epics import PV
from message_dialog import info_message


class RingStatusGroup(QGroupBox):
    """
    Camera controls
    """

    def __init__(self, *args, **kwargs):
        # Timer - just as example
        super(RingStatusGroup, self).__init__(*args, **kwargs)

        # Ring current
        self.ringcurrent_label = QLabel()
        self.ringcurrent_label.setText("Ring current [mA]")
        #self.ringcurrent_entry = QLineEdit()
        self.ringcurrent_entry = QLabel()
        self.ringcurrent_entry.setFixedWidth(50)
        self.epics_monitor = EpicsMonitor()
        self.epics_monitor.i0_state_changed_signal.connect(
            self.ringcurrent_entry.setText)

        # expected injection in
        self.inj_countdown_spacer = QLabel()
        self.inj_countdown_label = QLabel()
        self.inj_countdown_label.setText("Injection expected in [sec]")
        self.inj_countdown_entry = QLabel()
        self.inj_countdown_entry.setFixedWidth(50)
        self.countdown_monitor = CountdownMonitor()
        self.countdown_monitor.i0_state_changed_signal.connect(
            self.inj_countdown_entry.setText)

        # confirmed injection in
        self.inj_leadtime_label = QLabel()
        self.inj_leadtime_label.setText("Pre-Injection Lead [sec]")
        self.inj_leadtime_entry = QLabel()
        self.inj_leadtime_entry.setFixedWidth(50)
        self.lead_monitor = LeadMonitor()
        self.lead_monitor.i0_state_changed_signal.connect(
            self.inj_leadtime_entry.setText)

        # Ring status - DAQ veto
        self.ringstatus_spacer = QLabel()
        self.ringstatus_label = QLabel()
        self.ringstatus_label.setText("Veto state")
        self.ringstatus_entry = QLabel()
        self.ringstatus_entry.setFixedWidth(50)
        self.status_monitor = StatusMonitor()
        self.status_monitor.i0_state_changed_signal.connect(
            self.ringstatus_entry.setText)

        self.sync_daq_inj = QCheckBox("Sync. DAQ with injections")
        self.sync_daq_inj.setChecked(False)

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        # Buttons on top
        layout.addWidget(self.ringcurrent_label, 0, 0)
        layout.addWidget(self.ringcurrent_entry, 0, 1)

        layout.addWidget(self.inj_countdown_label, 0, 2)
        layout.addWidget(self.inj_countdown_entry, 0, 3)

        #layout.addWidget(self.ringstatus_spacer, 0, 2)
        layout.addWidget(self.ringstatus_label, 0, 4)
        layout.addWidget(self.ringstatus_entry, 0, 5)

        #layout.addWidget(self.inj_countdown_spacer, 0, 5)
        layout.addWidget(self.inj_leadtime_label, 0, 6)
        layout.addWidget(self.inj_leadtime_entry, 0, 7)

        layout.addWidget(self.sync_daq_inj, 0, 8)

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


TOPUP_TIMER_PV = "TRG2400:topup:timer"

class CountdownMonitor(QObject):
    i0_state_changed_signal = pyqtSignal(str)

    def __init__(self):
        super(CountdownMonitor, self).__init__()
        self.i0 = PV(TOPUP_TIMER_PV, callback=self.on_state_changed)

    def on_state_changed(self, value, **kwargs):
        self.i0_state_changed_signal.emit("{}".format(value))


ID_VETO_PV = "TRG1605-1-I20-01:topup:veto"
BM_VETO_PV = "TRG1605-1-B10-01:topup:veto"

class StatusMonitor(QObject):
    i0_state_changed_signal = pyqtSignal(str)
    i0_state_changed_signal2 = pyqtSignal(bool)

    def __init__(self):
        super(StatusMonitor, self).__init__()
        self.i0 = PV(BM_VETO_PV, callback=self.on_state_changed)
        self.value = None

    def on_state_changed(self, value, **kwargs):
        """
        :param value: the latest value from the PV
        :param kwargs: the rest of arguments
        :return: None
        """
        self.value = value
        self.i0_state_changed_signal2.emit(value)
        if value:
            value = "Veto"
        else:
            value = "Clear"
        self.i0_state_changed_signal.emit("{}".format(value))


ID_LEAD_PV = "TRG1605-1-I20-01:topup:veto:lead"
BM_LEAD_PV = "TRG1605-1-B10-01:topup:veto:lead"


class LeadMonitor(QObject):
    i0_state_changed_signal = pyqtSignal(str)
    i0_state_changed_signal2 = pyqtSignal(float)

    def __init__(self):
        super(LeadMonitor, self).__init__()
        self.i0 = PV(BM_LEAD_PV, callback=self.on_state_changed)
        self.value = None

    def on_state_changed(self, value, **kwargs):
        """
        :param value: the latest value from the PV
        :param kwargs: the rest of arguments
        :return: None
        """
        self.value = value
        self.i0_state_changed_signal.emit("{:.1f}".format(value))
        self.i0_state_changed_signal2.emit(value)
