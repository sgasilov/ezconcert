from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, \
    QPushButton, QComboBox, QCheckBox

from message_dialog import info_message, error_message


class RecoSettingsGroup(QGroupBox):
    """
    Camera controls
    """

    def __init__(self, *args, **kwargs):
        super(RecoSettingsGroup, self).__init__(*args, **kwargs)

        self.setCheckable(True)
        self.setChecked(False)

        self.COR_label = QLabel()
        self.COR_label.setText("Center of rotation")
        self.COR_entry = QLineEdit()

        self.set_layout()


    def set_layout(self):
        layout = QGridLayout()
        layout.addWidget(self.COR_label, 0, 0)
        layout.addWidget(self.COR_entry, 0, 1)

        self.setLayout(layout)
