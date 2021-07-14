from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, \
    QPushButton, QComboBox, QCheckBox
from concert.ext.ufo import (GeneralBackprojectArgs, GeneralBackprojectManager)
import numpy as np

from message_dialog import info_message, error_message


class RecoSettingsGroup(QGroupBox):
    """
    Camera controls
    """

    def __init__(self, *args, **kwargs):
        super(RecoSettingsGroup, self).__init__(*args, **kwargs)

        self.setCheckable(True)
        self.setChecked(False)

        self.cor_label = QLabel()
        self.cor_label.setText("Center of rotation")
        self.cor_entry = QLineEdit()
        self.cor_entry.setText('1280')

        self.row_top_label = QLabel()
        self.row_top_label.setText("Top row")
        self.row_top_entry = QLineEdit()
        self.row_top_entry.setText('100')

        self.row_bottom_label = QLabel()
        self.row_bottom_label.setText("Bottom row")
        self.row_bottom_entry = QLineEdit()
        self.row_bottom_entry.setText('-100')

        self.row_spacing_label = QLabel()
        self.row_spacing_label.setText("Row spacing")
        self.row_spacing_entry = QLineEdit()
        self.row_spacing_entry.setText('10')

        self.write_slices_swi = QCheckBox("Write slices to disk")
        self.write_slices_swi.setChecked(False)

        # ufo-concert
        self.args = None
        self.set_layout()


    def set_layout(self):
        layout = QGridLayout()
        layout.addWidget(self.cor_label, 0, 0)
        layout.addWidget(self.cor_entry, 0, 1)

        layout.addWidget(self.row_top_label, 0, 2)
        layout.addWidget(self.row_top_entry, 0, 3)
        layout.addWidget(self.row_bottom_label, 0, 4)
        layout.addWidget(self.row_bottom_entry, 0, 5)
        layout.addWidget(self.row_spacing_label, 0, 6)
        layout.addWidget(self.row_spacing_entry, 0, 7)

        layout.addWidget(self.write_slices_swi, 0, 8)

        self.setLayout(layout)

    def set_args(self, z_cor, nproj, angle):
        self.args = GeneralBackprojectArgs(\
            [self.cor], [z_cor], nproj, overall_angle=np.deg2rad(angle))
            #[1277.5], [250], nproj, overall_angle=np.deg2rad(angle))
        self.args.region = [self.row_start, self.row_end, self.row_step]
        #self.args.region = [-50, 50, 10]
        self.args.data_splitting_policy = 'many'
        self.args.absorptivity = True
        self.args.fix_nan_and_inf = True
        # self.args.energy = 19
        # self.args.pixel_size = 3.5e-6
        # self.args.propagation_distance = 0.07, 0.07
        # self.args.retrieval_padded_width = 4096
        # self.args.retrieval_padded_height = 4096
        # self.args.regularization_rate = 2.5
        # self.args.delta = 1e-7
        # # Even if we reconstruct just one slice, read +/- 32 adjacent projection rows in order to avoid
        # # convolution artifacts by the phase retrieval
        # self.args.projection_margin = 64


    @property
    def row_start(self):
        try:
            x = int(self.row_bottom_entry.text())
        except ValueError:
            error_message("Bottom row must integer number (relative to central row)")
            return None
        return x

    @property
    def row_end(self):
        try:
            x = int(self.row_top_entry.text())
        except ValueError:
            error_message("Top row must integer number (relative to central row)")
            return None
        return x

    @property
    def row_step(self):
        try:
            x = int(self.row_spacing_entry.text())
        except ValueError:
            error_message("Row spacing must be non-negative integer number")
            return None
        if x < 0:
            error_message("Row spacing must be non-negative integer number")
            return None
        return x

    @property
    def cor(self):
        try:
            x = float(self.cor_entry.text())
        except ValueError:
            error_message("Center of rotation must be non-negative number")
            return None
        if x < 0:
            error_message("Center of rotation must be non-negative number")
            return None
        return x