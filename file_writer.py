from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, QPushButton, QFileDialog, QCheckBox
import os
from message_dialog import info_message, error_message

class FileWriterGroup(QGroupBox):
    """
    Write to file settings
    """

    def __init__(self, *args, **kwargs):
        super(FileWriterGroup, self).__init__(*args, **kwargs)
        self.setCheckable(True)
        self.setChecked(True)

        self.root_dir_label = QLabel()
        self.root_dir_label.setText("Root dir:")
        self.root_dir_entry = QLineEdit()
        self.root_dir_entry.setText("/data/gui-test")
        self.root_dir_entry.setReadOnly(True)
        self.root_dir_select_button = QPushButton("...")
        self.root_dir_select_button.clicked.connect(self.select_root_directory)

        self.dsetname_label = QLabel()
        self.dsetname_label.setText("Filename pattern")
        self.dsetname_entry = QLineEdit()
        self.dsetname_entry.setText("frame_{:>05}.tif")
        self.dsetname_entry.setFixedWidth(200)
        self.blank_label = QLabel()

        self.ctset_fmt_label = QLabel()
        self.ctset_fmt_label.setText("CT scans' name pattern")
        self.ctset_fmt_entry = QLineEdit()
        self.ctset_fmt_entry.setText("scan_{:>03}")
        self.ctset_fmt_entry.setFixedWidth(200)

        self.separate_scans_checkbox = QCheckBox("Separate scans")
        self.separate_scans_checkbox.setChecked(True)

        self.bigtiff_checkbox = QCheckBox("Use bigtiff containers")
        self.bigtiff_checkbox.setChecked(False)
        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        layout.addWidget(self.root_dir_label, 0, 0)
        layout.addWidget(self.root_dir_entry, 0, 1, 1, 5)
        layout.addWidget(self.root_dir_select_button, 0, 6)

        layout.addWidget(self.ctset_fmt_label, 1, 0)
        layout.addWidget(self.ctset_fmt_entry, 1, 1)
        layout.addWidget(self.bigtiff_checkbox, 1, 2)
        layout.addWidget(self.separate_scans_checkbox, 1, 3)
        layout.addWidget(self.blank_label, 1, 4)
        layout.addWidget(self.dsetname_label, 1, 5)
        layout.addWidget(self.dsetname_entry, 1, 6)
        #layout.addWidget(self.blank_label, 1, 7)

        # Make directory entry 10x wider
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 10)
        for column in range(2, 5):
            layout.setColumnStretch(column, 1)
        self.setLayout(layout)

    def select_root_directory(self):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        root_dir = QFileDialog.getExistingDirectory(self, "Select root directory", "",
                                                    options=options)
        if root_dir:
            self.root_dir_entry.setText(root_dir)

    # getters
    @property
    def root_dir(self):
        try:
            tmp = self.root_dir_entry.text()
        except ValueError:
            error_message("Incorrect path to root directory")
        if os.access(tmp, os.W_OK):
            return tmp
        else:
            error_message("Cannot write into root dir. Check filewriter params")
            return None

    @property
    def dsetname(self):
        try:
            return self.dsetname_entry.text()
        except ValueError:
            return None

    @property
    def ctsetname(self):
        try:
            return self.ctset_fmt_entry.text()
        except ValueError:
            return None

    @property
    def separate_scans(self):
        return self.separate_scans_checkbox.isChecked()

    @property
    def bigtiff(self):
        return self.bigtiff_checkbox.isChecked()
