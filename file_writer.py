from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, QPushButton, QFileDialog, QCheckBox


class FileWriterGroup(QGroupBox):
    """
    Write to file settings
    """

    def __init__(self, *args, **kwargs):
        super(FileWriterGroup, self).__init__(*args, **kwargs)
        self.setCheckable(True)
        self.setChecked(False)

        self.root_dir_label = QLabel()
        self.root_dir_label.setText("root dir:")
        self.root_dir_entry = QLineEdit()
        self.root_dir_entry.setReadOnly(True)
        self.root_dir_select_button = QPushButton("...")
        self.root_dir_select_button.clicked.connect(self.select_root_directory)

        self.separate_scans_checkbox = QCheckBox("Separate scans")
        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        layout.addWidget(self.root_dir_label, 0, 0)
        layout.addWidget(self.root_dir_entry, 0, 1)
        layout.addWidget(self.root_dir_select_button, 0, 2)
        layout.addWidget(self.separate_scans_checkbox, 0, 4)

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