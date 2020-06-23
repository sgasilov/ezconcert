import sys

from PyQt5.QtWidgets import QDialog, QApplication, QGridLayout

from camera_controls import CameraControlsGroup
from file_writer import FileWriterGroup
from scan_controls import ScanControlsGroup
from ffc_settings import FFCSettingsGroup
from ring_status import RingStatusGroup

from concert.ext.viewers import PyplotImageViewer

class GUI(QDialog):
    def __init__(self, *args, **kwargs):
        super(GUI, self).__init__(*args, **kwargs)
        self.setWindowTitle('BMIT GUI')

        self.camera = None
        self.viewer = PyplotImageViewer()
        self.motor_inner = None
        self.motor_outer = None
        self.motor_ffc = None

        self.camera_controls_group = CameraControlsGroup(self.camera, self.viewer, title="Camera controls")
        self.scan_controls_group = ScanControlsGroup(self.get_all_params, title="Scan controls")
        self.ffc_controls_group = FFCSettingsGroup(self.motor_ffc, title="Flat-field correction settings")
        self.file_writer_group = FileWriterGroup(title="File-writer settings")
        self.ring_status_group = RingStatusGroup(title="Ring status")
        self.set_layout()

        self.show()

    def set_layout(self):
        main_layout = QGridLayout()
        main_layout.addWidget(self.camera_controls_group)
        main_layout.addWidget(self.scan_controls_group)
        main_layout.addWidget(self.ffc_controls_group)
        main_layout.addWidget(self.file_writer_group)
        main_layout.addWidget(self.ring_status_group)
        self.setLayout(main_layout)

    def get_all_params(self):
        exp_time = self.camera_controls_group.exp_time
        self.camera.exposure_time = exp_time
        root_dir = self.file_writer_group.root_dir_entry.text()
        return exp_time, root_dir



if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = GUI()
    sys.exit(app.exec_())
