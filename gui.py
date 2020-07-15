import sys

from PyQt5.QtWidgets import  QGroupBox, QDialog, QApplication, QGridLayout
from PyQt5.QtWidgets import QLabel, QLineEdit, QPushButton, QComboBox, QCheckBox
from PyQt5.QtCore import QTimer, QEventLoop

from camera_controls import CameraControlsGroup
from file_writer import FileWriterGroup
from ffc_settings import FFCSettingsGroup
from ring_status import RingStatusGroup
from scan_controls import ScanControlsGroup
from message_dialog import info_message, error_message


import logging
import concert
concert.require("0.11.0")

from concert.quantities import q
from concert.session.utils import ddoc, dstate, pdoc, code_of, abort

LOG = logging.getLogger(__name__)

from concert.ext.viewers import PyplotImageViewer
from concert.experiments.imaging import frames
from concert.storage import DirectoryWalker
from concert.experiments.addons import ImageWriter
from concert.experiments.addons import Consumer
from concert.experiments.base import Acquisition, Experiment
from concert.session.utils import abort
from concert.coroutines.base import coroutine, inject

#import asyncio
from scans_concert import ConcertScanThread

# Adam's interface EPICS-Concert interface
from edc.motor import CLSLinear, ABRS, CLSAngle, SimMotor
from edc.shutter import CLSShutter

import numpy as np
from time import sleep

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

        # CAMERA
        self.camera = None

        # CONCERT OBJECTS
        self.viewer = PyplotImageViewer()
        # class which manipulates flat-field motor and shutters
        self.setup = None
        self.walker = None
        self.writer = None
        # class derived from concert.experiment. It has .run() method
        self.scan = None
        # future objects returned by the scan
        self.f = None
        # timer which checks state of the self. objects
        self.scan_status_update_timer = QTimer()
        self.scan_status_update_timer.setInterval(1000)
        self.scan_status_update_timer.timeout.connect(self.check_scan_status)

        # EXECUTION CONTROL BUTTONS
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




        # PHYSICAL DEVICES
        self.motor_control_group = QGroupBox(title="Motor controls and indicators")
        # physical devices
        self.hor_motor = None
        self.vert_motor = None
        self.CT_motor = None
        self.shutter = None
        self.time_motor = None
        # dictionary which holds all connected devices and their labels
        self.motors = {}
        # logical devices
        self.motor_inner = None
        self.motor_outer = None
        self.motor_flat = None
        # connect buttons
        self.connect_hor_mot_button = QPushButton("Connect to horizontal stage")
        self.connect_vert_mot_button = QPushButton("Connect to vertical stage")
        self.connect_CT_mot_button = QPushButton("Connect to CT stage")
        # this are to be implemeted depending on low-level interface (EPICS/Tango/etc)
        self.connect_hor_mot_button.clicked.connect(self.connect_hor_motor_func)
        self.connect_vert_mot_button.clicked.connect(self.connect_vert_motor_func)
        self.connect_CT_mot_button.clicked.connect(self.connect_CT_motor_func)

        # position indicators
        self.mot_pos_info_label = QLabel()
        self.mot_pos_info_label.setText("Status")

        self.hor_mot_pos_label = QLabel()
        self.hor_mot_pos_label.setText("Not connected")
        self.hor_mot_pos_entry = QLabel()

        self.vert_mot_pos_label = QLabel()
        self.vert_mot_pos_label.setText("Not connected")
        self.vert_mot_pos_entry = QLabel()

        self.CT_mot_pos_label = QLabel()
        self.CT_mot_pos_label.setText("Not connected")
        self.CT_mot_pos_entry = QLabel()

        # external subgroups to set parameters
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
        self.concert_scan = None
        #self.scan_thread = ConcertScanThread(viewer=self.viewer, camera=self.camera)
        #self.scan_thread.scan_finished_signal.connect(self.end_of_scan)
        #self.scan_thread.start()



        self.set_layout_motor_control_group()
        self.set_layout()

        # connect to timer and shutter and populate lists of motors
        self.connect_time_motor_func()
        #self.connect_shutter_func()

        self.tmp = 0
        self.show()

    def set_layout_motor_control_group(self):
        layout = QGridLayout()
        layout.addWidget(self.connect_CT_mot_button, 0, 2, 1, 2)
        layout.addWidget(self.connect_vert_mot_button, 0, 4, 1, 2)
        layout.addWidget(self.connect_hor_mot_button, 0, 6, 1, 2)
        layout.addWidget(self.mot_pos_info_label, 1, 1)
        layout.addWidget(self.CT_mot_pos_label, 1, 2)
        layout.addWidget(self.CT_mot_pos_entry, 1, 3)
        layout.addWidget(self.vert_mot_pos_label, 1, 4)
        layout.addWidget(self.vert_mot_pos_entry, 1, 5)
        layout.addWidget(self.hor_mot_pos_label, 1, 6)
        layout.addWidget(self.hor_mot_pos_entry, 1, 7)
        self.motor_control_group.setLayout(layout)

    def set_layout(self):
        main_layout = QGridLayout()
        main_layout.addWidget(self.camera_controls_group)
        main_layout.addWidget(self.motor_control_group)
        main_layout.addWidget(self.scan_controls_group)
        main_layout.addWidget(self.ffc_controls_group)
        main_layout.addWidget(self.file_writer_group)
        main_layout.addWidget(self.ring_status_group)
        self.setLayout(main_layout)

    def connect_hor_motor_func(self):
        try:
            self.hor_motor = CLSLinear("SMTR1605-2-B10-11:mm", encoded=True)
        except:
            error_message("Can not connect to horizontal stage, try again")
        if self.hor_motor is not None:
            self.hor_mot_pos_label.setText("Connected, position [mm]")
            tmp = "Horizontal [mm]"
            self.motors[tmp] = self.hor_motor
            self.connect_hor_mot_button.setEnabled(False)
            self.scan_controls_group.inner_loop_motor.addItem(tmp)
            self.scan_controls_group.outer_loop_motor.addItem(tmp)
            self.ffc_controls_group.motor_options_entry.addItem(tmp)

    def connect_vert_motor_func(self):
        try:
            self.vert_motor = CLSLinear("SMTR1605-2-B10-10:mm", encoded=True)
        except:
            error_message("Can not connect to vertical stage, try again")
        if self.vert_motor is not None:
            self.vert_mot_pos_label.setText("Connected, position [mm]")
            tmp = "Vertical [mm]"
            self.motors[tmp] = self.hor_motor
            self.connect_vert_mot_button.setEnabled(False)
            self.scan_controls_group.outer_loop_motor.addItem(tmp)
            self.ffc_controls_group.motor_options_entry.addItem(tmp)

    def connect_CT_motor_func(self):
        try:
            self.CT_motor = ABRS("SMTR1605-2-B10-10:mm", encoded=True)
        except:
            error_message("Could not connect to CT stage, try again")
        if self.CT_motor is not None:
            self.CT_mot_pos_label.setText("Connected, position [deg]")
            tmp = "CT stage [deg]"
            self.motors[tmp] = self.hor_motor
            self.connect_vert_mot_button.setEnabled(False)
            self.scan_controls_group.inner_loop_motor.addItem(tmp)

    def connect_time_motor_func(self):
        try:
            self.time_motor = SimMotor()
        except:
            error_message("Can not connect to timer")
        tmp = "Timer [sec]"
        self.motors[tmp] = self.time_motor
        #self.motors[tmp] = self.motor_time
        self.scan_controls_group.inner_loop_motor.addItem(tmp)
        self.scan_controls_group.outer_loop_motor.addItem(tmp)

    def connect_shutter_func(self):
        error_message("Not implemented")

    def on_camera_connected(self, camera):
        self.concert_scan = ConcertScanThread(self.viewer, camera)
        self.concert_scan.data_changed_signal.connect(self.camera_controls_group.test_entry.setText)
        self.concert_scan.scan_finished_signal.connect(self.end_of_scan)
        self.concert_scan.start()
        #self.camera = camera
        self.scan_controls_group.setEnabled(True)
        self.ffc_controls_group.setEnabled(True)
        self.file_writer_group.setEnabled(True)

    def start(self):
        self.start_button.setEnabled(False)
        self.abort_button.setEnabled(True)
        self.return_button.setEnabled(False)
        self.concert_scan.start_scan()

    # def start(self):
    #     #info_message("Scan started")
    #     self.walker = DirectoryWalker(root=self.file_writer_group.root_dir, \
    #                                   dsetname=self.file_writer_group.dsetname)
    #
    #     # self.setup = FFC(self.shutter, self.motor_flat, \
    #     #                    self.ffc_controls_group.flat_position, self.ffc_controls_group.radio_position)
    #     #
    #     # self.scan = Radiography(self.camera, self.setup, \
    #     #                         num_darks=self.ffc_controls_group.num_darks,
    #     #                         num_flats=self.ffc_controls_group.num_flats)
    #
    #     #flats = Acquisition('flats', self.take_images(5))
    #     flats = Acquisition('flats', self.take_flats())
    #     acquisitions = [flats]
    #     self.scan = Experiment([flats])
    #     #live = Consumer(acquisitions, self.viewer())
    #
    #
    #     # yield self.camera.grab()
    #
    #     # Connecting writer and live-preview
    #     #self.writer = ImageWriter(self.scan.acquisitions, self.walker, async=True)
    #     #live = Consumer(self.scan.acquisitions, self.viewer())
    #
    #     #info_message("Image std {:0.2f}".format(np.std(self.camera.grab())))
    #     #test(self.camera)
    #
    #     self.start_button.setEnabled(False)
    #     self.abort_button.setEnabled(True)
    #     self.return_button.setEnabled(False)
    #     #info_message("Scan ON")
    #     self.scan_status_update_timer.start()
    #     self.f = self.scan.run()
    #     #inject((self.camera.grab() for i in range(100)), self.viewer())
    #     #inject((self.camera.grab() for i in range(100)), self.writer())
    #     #sleep(5)
    #     self.end_of_scan()
    #
    #     #self.scan_thread.scan_running = True
    #     #info_message("Scan finished")

    def abort(self):
        self.concert_scan.abort_scan()
        self.start_button.setEnabled(True)
        self.abort_button.setEnabled(False)
        self.return_button.setEnabled(True)
        # calls global Concert abort() command
        # aborst concert experiemnt not necesserely stops motor
        self.scan_status_update_timer.stop()

        #global concert abort to stop motors
        #abort()
        info_message("Scan aborted")
        #self.scan_thread.scan_running = False

    def end_of_scan(self):
        # call abort command instead
        # self.scan_status_update_timer.stop()

        #### This section runs only if scan was finished normally, but not aborted ###
        if not self.return_button.isEnabled():
            info_message("Scan finished")
        #### End of section

        # info_message("Scan finished, future state{}, yielded {} times".format(self.f.done(), self.tmp))
        self.start_button.setEnabled(True)
        self.abort_button.setEnabled(False)

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

    def move(self,motor):
        """Move to the next step."""
        step = 1
        motor.x += step
        motor.param.set(motor.x).join()

    def take_images(self, nframes, cback=None):
        #info_message("I'm inside acqusition")
        if self.camera.state == 'recording':
            self.camera.stop_recording()

        self.camera['trigger_source'].stash().join()
        self.camera.trigger_source = self.camera.trigger_sources.SOFTWARE

        self.tmp = 0
        try:
            with self.camera.recording():
                for i in range(nframes):
                    self.camera.trigger()
                    yield self.camera.grab()
                    self.tmp += 1
                    #if cback:
                    #    cback()
        finally:
            self.camera['trigger_source'].restore().join()

        #return frames(nframes, self.camera, callback=cback)

    @coroutine
    def mystd(self):
        while True:
            im = yield
            info_message("Image std {:0.2f}".format(np.std(im)))
            # print "STD {:0.2f}".format(np.std(im))



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
    loop = QEventLoop(app)
    ex = GUI()
    sys.exit(app.exec_())
