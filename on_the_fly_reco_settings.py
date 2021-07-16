from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, \
    QPushButton, QComboBox, QCheckBox, QFileDialog
from concert.ext.ufo import (GeneralBackprojectArgs, GeneralBackprojectManager)
from concert.storage import read_tiff
import os
import numpy as np

from message_dialog import info_message, error_message


class RecoSettingsGroup(QGroupBox):
    """
    Camera controls
    """

    def __init__(self, *args, **kwargs):
        super(RecoSettingsGroup, self).__init__(*args, **kwargs)

        self.QFD = QFileDialog()

        self.setCheckable(True)
        self.setChecked(False)

        self.spacer = QLabel()
        self.spacer.setFixedWidth(150)

        self.cor_label = QLabel()
        self.cor_label.setText("Center of rotation")
        self.cor_entry = QLineEdit()
        self.cor_entry.setText('1278')
        self.cor_entry.setFixedWidth(40)

        self.row_top_label = QLabel()
        self.row_top_label.setText("Top row")
        self.row_top_entry = QLineEdit()
        self.row_top_entry.setText('100')
        self.row_top_entry.setFixedWidth(40)

        self.row_bottom_label = QLabel()
        self.row_bottom_label.setText("Bottom row")
        self.row_bottom_entry = QLineEdit()
        self.row_bottom_entry.setText('-100')
        self.row_bottom_entry.setFixedWidth(40)

        self.row_spacing_label = QLabel()
        self.row_spacing_label.setText("Row spacing")
        self.row_spacing_entry = QLineEdit()
        self.row_spacing_entry.setText('10')
        self.row_spacing_entry.setFixedWidth(40)

        self.write_slices_swi = QCheckBox("Write slices to disk")
        self.write_slices_swi.setChecked(True)

        self.ffc_files_swi = QCheckBox("Load flat/dark from disk")
        self.ffc_files_swi.setChecked(False)

        self.flat_file_label = QLabel()
        self.flat_file_label.setText("Flat-field file")
        self.flat_file_entry = QLineEdit()
        #self.flat_file_entry.setFixedWidth(150)
        self.flat_file_entry.setReadOnly(True)
        self.flat_file_select_button = QPushButton("...")

        self.dark_file_label = QLabel()
        self.dark_file_label.setText("Dark-field file")
        self.dark_file_entry = QLineEdit()
        #self.dark_file_entry.setFixedWidth(150)
        self.dark_file_entry.setReadOnly(True)
        self.dark_file_select_button = QPushButton("...")

        self.pr_swi = QCheckBox("Retrieve phase")
        self.pr_swi.setChecked(False)

        self.energy_label = QLabel()
        self.energy_label.setText("Energy [keV]")
        self.energy_entry = QLineEdit()
        self.energy_entry.setText('20')
        self.energy_entry.setFixedWidth(40)

        self.pixel_size_label = QLabel()
        self.pixel_size_label.setText("Pixel_size [micron]")
        self.pixel_size_entry = QLineEdit()
        self.pixel_size_entry.setText('3.6')
        self.pixel_size_entry.setFixedWidth(40)

        self.propagation_distance_label = QLabel()
        self.propagation_distance_label.setText("Propagation_distance [cm]")
        self.propagation_distance_entry = QLineEdit()
        self.propagation_distance_entry.setText('10')
        self.propagation_distance_entry.setFixedWidth(40)

        self.db_ratio_label = QLabel()
        self.db_ratio_label.setText("Delta/beta ratio")
        self.db_ratio_entry = QLineEdit()
        self.db_ratio_entry.setText('100')
        self.db_ratio_entry.setFixedWidth(40)

        self.all_params_correct = True
        self.args = None
        self.flat = None
        self.dark = None
        self.last_dir = '/'

        self.flat_file_select_button.clicked.connect(self.load_flat)
        self.dark_file_select_button.clicked.connect(self.load_dark)

        self.set_layout()


    def set_layout(self):
        layout = QGridLayout()
        layout.addWidget(self.cor_label, 0, 0)
        layout.addWidget(self.cor_entry, 0, 1)
        layout.addWidget(self.spacer, 0, 2)

        layout.addWidget(self.row_top_label, 0, 3)
        layout.addWidget(self.row_top_entry, 0, 4)
        layout.addWidget(self.spacer, 0, 5)

        layout.addWidget(self.row_bottom_label, 0, 6)
        layout.addWidget(self.row_bottom_entry, 0, 7)
        layout.addWidget(self.spacer, 0, 8)

        layout.addWidget(self.row_spacing_label, 0, 9)
        layout.addWidget(self.row_spacing_entry, 0, 10)
        layout.addWidget(self.spacer, 0, 11)

        layout.addWidget(self.write_slices_swi, 0, 12)
        
        # flat field correction, row 2
        layout.addWidget(self.ffc_files_swi, 1, 0)
        layout.addWidget(self.flat_file_label, 1, 1)
        layout.addWidget(self.flat_file_entry, 1, 2, 1, 3)
        layout.addWidget(self.flat_file_select_button, 1, 5)

        layout.addWidget(self.dark_file_label, 1, 6)
        layout.addWidget(self.dark_file_entry, 1, 7, 1, 4)
        layout.addWidget(self.dark_file_select_button, 1, 11)

        # phase retrieval, row 3
        layout.addWidget(self.pr_swi, 2, 0)
        
        layout.addWidget(self.energy_label, 2, 1)
        layout.addWidget(self.energy_entry, 2, 2)

        layout.addWidget(self.pixel_size_label, 2, 3)
        layout.addWidget(self.pixel_size_entry, 2, 4)

        layout.addWidget(self.propagation_distance_label, 2, 5)
        layout.addWidget(self.propagation_distance_entry, 2, 6)

        layout.addWidget(self.db_ratio_label, 2, 7)
        layout.addWidget(self.db_ratio_entry, 2, 8)

        

        self.setLayout(layout)

    def set_args(self, z_cor, nproj, angle):
        self.args = GeneralBackprojectArgs(\
            #[self.cor], [z_cor], nproj, overall_angle=np.deg2rad(angle))
            [1277.5], [260], nproj, overall_angle=np.deg2rad(angle))
        self.args.region = [self.row_start, self.row_end, self.row_step]
        #self.args.region = [-50, 50, 10]
        self.args.data_splitting_policy = 'many'
        self.args.absorptivity = True
        self.args.fix_nan_and_inf = True
        # if self.pr_swi:
        #     self.args.energy = 19
        #     self.args.pixel_size = 3.5e-6
        #     self.args.propagation_distance = 0.07, 0.07
        #     self.args.retrieval_padded_width = 4096
        #     self.args.retrieval_padded_height = 4096
        #     self.args.regularization_rate = 2.5
        #     self.args.projection_margin = 64
        # if self.ffc_files_swi.isChecked():
        #     self.args.flat = self.flat
        #     self.args.dark = self.dark
        # else:
        #     self.args.flat = None
        #     self.args.dark = None


    def load_flat(self):
        self.flat, tmp = self.load_image('flat')
        self.flat_file_entry.setText(tmp)

    def load_dark(self):
        self.dark, tmp = self.load_image('dark')
        self.dark_file_entry.setText(tmp)

    def load_image(self, typ):
        fname, fext = self.QFD.getOpenFileName(
            self, 'Select '+typ+' file', self.last_dir, "(*.tif)")
        self.last_dir = os.path.dirname(fname)
        if fname == '':
            error_message('Select file')
            self.all_params_correct = False
            return None
        try:
            im = read_tiff(fname)
        except:
            error_message('Cannot load image')
            self.all_params_correct = False
            return None
        else:
            return im, fname


    @property
    def row_start(self):
        try:
            x = int(self.row_bottom_entry.text())
        except ValueError:
            error_message("Bottom row must integer number (relative to central row)")
            self.all_params_correct = False
            return None
        return x

    @property
    def row_end(self):
        try:
            x = int(self.row_top_entry.text())
        except ValueError:
            error_message("Top row must integer number (relative to central row)")
            self.all_params_correct = False
            return None
        return x

    @property
    def row_step(self):
        try:
            x = int(self.row_spacing_entry.text())
        except ValueError:
            error_message("Row spacing must be non-negative integer number")
            self.all_params_correct = False
            return None
        if x < 0:
            error_message("Row spacing must be non-negative integer number")
            self.all_params_correct = False
            return None
        return x

    @property
    def cor(self):
        try:
            x = float(self.cor_entry.text())
        except ValueError:
            error_message("Center of rotation must be positive number")
            self.all_params_correct = False
            return None
        if x < 0:
            error_message("Center of rotation must be positive number")
            self.all_params_correct = False
            return None
        return x

    @property
    def energy(self):
        try:
            x = float(self.energy_entry.text())
        except ValueError:
            error_message("Energy must be positive number")
            self.all_params_correct = False
            return None
        if x < 0:
            error_message("Energy must be positive number")
            self.all_params_correct = False
            return None
        return x

    @property
    def pix_size(self):
        try:
            x = float(self.pixel_size_entry.text())*1e-6
        except ValueError:
            error_message("Pixel size must be positive number")
            self.all_params_correct = False
            return None
        if x < 0:
            error_message("Pixel size must be positive number")
            self.all_params_correct = False
            return None
        return x

    @property
    def prop_dist(self):
        try:
            x = float(self.propagation_distance_entry.text())*1e-2
        except ValueError:
            error_message("Propagation distance must be non-negative number")
            self.all_params_correct = False
            return None
        if x < 0:
            error_message("Propagation distance must be non-negative number")
            self.all_params_correct = False
            return None
        return x

    @property
    def db_ratio(self):
        try:
            x = np.log10(float(self.db_ratio_entry.text()))
        except ValueError:
            error_message("Delta-beta ratio must be positive number")
            self.all_params_correct = False
            return None
        if x < 0:
            error_message("Delta-beta ratio must be positive number")
            self.all_params_correct = False
            return None
        return x

    @property
    def db_ratio(self):
        try:
            x = float(self.db_ratio_entry.text())
        except ValueError:
            error_message("Delta-beta ratio must be positive number")
            self.all_params_correct = False
            return None
        if x < 0:
            error_message("Delta-beta ratio must be positive number")
            self.all_params_correct = False
            return None
        return x
