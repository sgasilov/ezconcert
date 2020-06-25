import sys

from PyQt5.QtWidgets import  QGroupBox, QDialog, QApplication, QGridLayout
from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox
from PyQt5.QtCore import QTimer

from camera_controls import CameraControlsGroup
from file_writer import FileWriterGroup
from ffc_settings import FFCSettingsGroup
from ring_status import RingStatusGroup
from scan_controls import ScanControlsGroup

from concert.ext.viewers import PyplotImageViewer
from concert.experiments.imaging import frames
from concert.storage import DirectoryWalker
from concert.experiments.addons import ImageWriter
from concert.experiments.addons import Consumer
from message_dialog import info_message, error_message
from scans_concert import ConcertScanThread, Radiography, FFC, test
# Adam's interface EPICS-Concert interface
from edc.motor import CLSLinear, ABRS, CLSAngle
from edc.shutter import CLSShutter

import numpy as np

class GUI(QDialog):
    '''
    Creates main GUI, holds references to physical devices, and
    provides start/abort controls for Concert scans, and holds
    4 groups where parameters can be entered
    Also has some helper functions such as
    setter which updates all camera parameters
    '''
    def __init__(self, *args, **kwargs):
        super(GUI, self).__init__(*args, **kwargs)
        self.setWindowTitle('BMIT GUI')

        # (1) Physical devices
        self.camera = None
        self.motor_inner = None
        self.motor_outer = None
        self.motor_flat = None
        self.shutter = None
        # (2) Concert objects
        self.viewer = PyplotImageViewer()
        # class which manipulates flat-field motor and shutters
        self.setup = None
        # class derived from concert.experiment. It has .run() method
        self.scan = None
        self.walker = None
        self.writer = None
        # helper variables
        self.f = None
        self.scan_status_update_timer = QTimer()
        self.scan_status_update_timer.setInterval(1000)
        self.scan_status_update_timer.timeout.connect(self.check_scan_status)

        # (3) Execution control buttons
        self.getflatsdarks_button = QPushButton("ACQUIRE FLATS AND DARKS")
        self.getflatsdarks_button.clicked.connect(self.getflatsdarks)
        self.start_button = QPushButton("START")
        self.start_button.clicked.connect(self.start)
        self.abort_button = QPushButton("ABORT")
        self.abort_button.setEnabled(False)
        self.abort_button.clicked.connect(self.abort)
        self.return_button = QPushButton("RETURN")
        self.return_button.clicked.connect(self.return_to_position)
        self.scan_fps_entry = QLabel()

        # subgroups
        self.camera_controls_group = CameraControlsGroup(self.viewer, title="Camera controls")
        self.camera_controls_group.camera_connected_signal.connect(self.on_camera_connected)
        self.ffc_controls_group = FFCSettingsGroup(self.motor_flat, self.getflatsdarks_button, title="Flat-field correction settings")
        self.ffc_controls_group.setEnabled(False)
        self.file_writer_group = FileWriterGroup(title="File-writer settings")
        self.file_writer_group.setEnabled(False)
        self.ring_status_group = RingStatusGroup(title="Ring status")
        self.scan_controls_group = ScanControlsGroup(self.start_button, self.abort_button, self.return_button, self.scan_fps_entry,
                                                     self.motor_inner, self.motor_outer, title="Scan controls")
        self.scan_controls_group.setEnabled(False)
        # Thread for concert scan
        #self.scan_thread = ConcertScanThread(viewer=self.viewer, camera=self.camera)
        #self.scan_thread.scan_finished_signal.connect(self.end_of_scan)
        #self.scan_thread.start()

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

    def on_camera_connected(self, camera):
        self.camera = camera
        self.scan_controls_group.setEnabled(True)
        self.ffc_controls_group.setEnabled(True)
        self.file_writer_group.setEnabled(True)

    def update_all_cam_params(self):
        ''' updates camera parameter with value in GUI entries'''
        self.camera.exposure_time = self.camera_controls_group.exp_time
        #root_dir = self.file_writer_group.root_dir_entry.text()
        #return exp_time, root_dir

    def check_parameters(self):
        # Just checking type conversion here
        try:
            self.inner_loop_steps()
            self.outer_loop_steps()
        except ValueError:
            return False
        return True

    # EXECUTION CONTROL
    def check_scan_status(self):
        if self.f.done():
            self.end_of_scan()

    def start(self):
        info_message("Scan started")
        self.setup = FFC(self.shutter, self.motor_flat, \
                           self.ffc_controls_group.flat_position, self.ffc_controls_group.radio_position)

        #self.walker = DirectoryWalker(root=exp_root_dir, dsetname=frame_fmt)
        #self.writer = ImageWriter(ex.acquisitions, walker, async=True)
        self.scan = Radiography(self.camera, self.setup, self.walker, \
                                self.ffc_controls_group.num_flats, self.ffc_controls_group.num_darks)
        #live = Consumer(self.scan.acquisitions, self.viewer)

        info_message("Image std {:0.2f}".format(np.std(self.camera.grab())))
        #test(self.camera)

        self.start_button.setEnabled(False)
        self.abort_button.setEnabled(True)
        self.return_button.setEnabled(False)
        #info_message("Scan ON")
        #self.f = self.scan.run()
        #self.scan_status_update_timer.start()

        #self.scan_thread.scan_running = True
        #info_message("Scan finished")



    def abort(self):
        # calls global Concert abort() command
        # aborst concert experiemnt not necesserely stops motor
        self.scan_status_update_timer.stop()
        self.scan.abort()
        #global concert abort to stop motors
        #abort()
        info_message("Scan aborted")
        #self.scan_thread.scan_running = False
        self.start_button.setEnabled(True)
        self.abort_button.setEnabled(False)
        self.return_button.setEnabled(True)

    def end_of_scan(self):
        # call abort command instead
        self.scan_status_update_timer.stop()
        info_message("Scan finished")
        self.start_button.setEnabled(True)
        self.abort_button.setEnabled(False)
        self.return_button.setEnabled(False)

    def return_to_position(self):
        info_message("Returning to position...")
        result = return_to_position_dummy()
        info_message(result)

    def getflatsdarks(self):
        info_message("Acquiring flats and darks")
        self.getflatsdarks_button.setEnabled(False)
        self.getflatsdarks_button.setEnabled(True)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    ex = GUI()
    sys.exit(app.exec_())
