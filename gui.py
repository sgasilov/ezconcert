# Adam's Concert-EPICS interface
import os

from edc.shutter import CLSShutter
from edc.motor import CLSLinear, ABRS, SimMotor
# PyQT imports
from PyQt5.QtWidgets import QGroupBox, QDialog, QApplication, QGridLayout
from PyQt5.QtWidgets import QLabel, QPushButton, QDoubleSpinBox
# from PyQt5.QtWidgets import QLineEdit, QComboBox, QCheckBox
from PyQt5.QtCore import QTimer, QEventLoop, QFile, QTextStream
# GUI groups and objects
from camera_controls import CameraControlsGroup
from motor_controls import MotorsControlsGroup
from file_writer import FileWriterGroup
from ffc_settings import FFCSettingsGroup
from ring_status import RingStatusGroup
from scan_controls import ScanControlsGroup
from message_dialog import info_message, error_message, warning_message
from motor_controls import EpicsMonitorFloat, EpicsMonitorFIS, MotionThread, HomeThread
from scans_concert import ConcertScanThread
from on_the_fly_reco_settings import RecoSettingsGroup
# Concert imports
from concert.storage import DirectoryWalker
from concert.ext.viewers import PyplotImageViewer
from concert.experiments.imaging import (tomo_projections_number, tomo_max_speed, frames)
from concert.base import TransitionNotAllowed
# from concert.session.utils import ddoc, dstate, pdoc, code_of, abort
from concert.quantities import q
import sys
# from time import sleep
import logging
import concert
# Miscellaneous imports
from numpy import linspace
import time
# Dark style
# noinspection PyUnresolvedReferences
from styles.breeze import styles_breeze

concert.require("0.11.0")
LOG = logging.getLogger("ezconcert")
LOG.setLevel(logging.DEBUG)
# create handlers
ch = logging.StreamHandler()
fh = logging.FileHandler('ezconcert.log')
# formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)
fh.setFormatter(formatter)
# add handlers
# LOG.addHandler(ch)
LOG.addHandler(fh)



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

        self.total_experiment_time = QTimer()
        self.last_inner_loop_scan_time = QTimer()

        # EXECUTION CONTROL BUTTONS
        self.start_button = QPushButton("START")
        self.start_button.clicked.connect(self.start)
        self.abort_button = QPushButton("ABORT")
        self.abort_button.setEnabled(False)
        self.abort_button.clicked.connect(self.abort)
        self.return_button = QPushButton("RETURN")
        self.return_button.clicked.connect(self.return_to_start)
        self.scan_fps_entry = QLabel()

        # PHYSICAL DEVICES
         # dictionary which holds all connected devices and their labels
        self.motors = {}
        # logical devices
        self.motor_inner = None
        self.motor_outer = None
        self.motor_flat = None


        # external subgroups to set parameters
        self.motor_control_group = MotorsControlsGroup(
            title="Motor controls and indicators")
        self.camera_controls_group = CameraControlsGroup(
            self.viewer, title="Camera controls")
        self.camera_controls_group.camera_connected_signal.connect(
            self.on_camera_connected)
        self.ffc_controls_group = FFCSettingsGroup(
            self.motor_flat, title="Flat-field correction settings")
        self.ffc_controls_group.setEnabled(False)
        self.file_writer_group = FileWriterGroup(title="File-writer settings")
        self.file_writer_group.setEnabled(False)
        self.ring_status_group = RingStatusGroup(title="Ring status")
        self.scan_controls_group = ScanControlsGroup(self.start_button, self.abort_button, self.return_button,
                                                     self.scan_fps_entry,
                                                     self.motor_inner, self.motor_outer, title="Scan controls")
        self.scan_controls_group.setEnabled(False)
        self.reco_settings_group = RecoSettingsGroup(title="On-the-fly reconstruction")
        self.reco_settings_group.setEnabled(False)

        # THREADS (scan and motors)
        self.concert_scan = None
        # timer is created automatically in motorscontrolgroup constructor
        self.motors["Timer [sec]"] = self.motor_control_group.time_motor
        self.scan_controls_group.inner_loop_motor.addItem("Timer [sec]")
        self.scan_controls_group.outer_loop_motor.addItem("Timer [sec]")

        # Variable for outer loop
        self.number_of_scans = 1
        self.outer_region = []
        self.outer_step = 0.0
        self.outer_unit = q.mm

        # SIGNALS/CONNECTIONS
        self.camera_controls_group.viewer_lowlim_entry.editingFinished.connect(
            self.set_viewer_limits)
        self.camera_controls_group.viewer_highlim_entry.editingFinished.connect(
            self.set_viewer_limits)
        self.camera_controls_group.trigger_entry.currentIndexChanged.connect(self.restrict_params_depending_on_trigger)
        self.scan_controls_group.inner_loop_steps_entry.editingFinished.connect(
            self.relate_nbuf_to_nproj)
        # populate motors dictionary when physical device is connected
        # self.motor_control_group.connect_hor_mot_button.clicked.connect(self.add_mot_hor)
        # self.motor_control_group.connect_vert_mot_button.clicked.connect(self.add_mot_vert)
        # self.motor_control_group.connect_CT_mot_button.clicked.connect(self.add_mot_CT)
        # self.motor_control_group.connect_shutter_button.clicked.connect(self.add_mot_sh)
        # add motors automatically on start
        self.motor_control_group.connect_hor_motor_func()
        self.motor_control_group.connect_CT_motor_func()
        self.motor_control_group.connect_vert_motor_func()
        self.motor_control_group.connect_shutter_func()

        # finally
        self.set_layout()
        self.show()
        LOG.info("Start gui.py")

    def set_layout(self):
        main_layout = QGridLayout()
        main_layout.addWidget(self.camera_controls_group)
        main_layout.addWidget(self.motor_control_group)
        main_layout.addWidget(self.scan_controls_group)
        main_layout.addWidget(self.ffc_controls_group)
        main_layout.addWidget(self.file_writer_group)
        main_layout.addWidget(self.reco_settings_group)
        main_layout.addWidget(self.ring_status_group)
        self.setLayout(main_layout)

    def add_mot_hor(self):
        tmp = "Horizontal [mm]"
        self.motors[tmp] = self.motor_control_group.hor_motor
        self.scan_controls_group.inner_loop_motor.addItem(tmp)
        self.scan_controls_group.outer_loop_motor.addItem(tmp)
        self.ffc_controls_group.motor_options_entry.addItem(tmp)

    def add_mot_vert(self):
        tmp = "Vertical [mm]"
        self.motors[tmp] = self.motor_control_group.vert_motor
        self.scan_controls_group.inner_loop_motor.addItem(tmp)
        self.scan_controls_group.outer_loop_motor.addItem(tmp)
        self.ffc_controls_group.motor_options_entry.addItem(tmp)
        tmp = self.scan_controls_group.outer_loop_motor.findText("Vertical [mm]")
        self.scan_controls_group.outer_loop_motor.setCurrentIndex(tmp)

    def add_mot_CT(self):
        tmp = "CT stage [deg]"
        self.motors[tmp] = self.motor_control_group.CT_motor
        self.scan_controls_group.inner_loop_motor.addItem(tmp)
        tmp = self.scan_controls_group.inner_loop_motor.findText("CT stage [deg]")
        self.scan_controls_group.inner_loop_motor.setCurrentIndex(tmp)

    def add_mot_sh(self):
        self.shutter = self.motor_control_group.shutter

    def restrict_params_depending_on_trigger(self):
        # select continious or step and shoot scans and
        # enable/disable buffer.
        tmp = self.camera_controls_group.buffered_entry.findText("NO")
        self.camera_controls_group.buffered_entry.setCurrentIndex(tmp)
        self.camera_controls_group.delay_entry.setEnabled(True)
        self.scan_controls_group.inner_loop_continuous.setChecked(True)
        # options:
        if self.camera_controls_group.trigger_entry.currentText() == 'SOFTWARE':
            self.scan_controls_group.inner_loop_continuous.setChecked(False)
        if self.camera_controls_group.trigger_entry.currentText() == 'EXTERNAL'\
            and self.camera_controls_group.camera_model_label == 'PCO Edge':
                tmp = self.camera_controls_group.buffered_entry.findText("YES")
                self.camera_controls_group.buffered_entry.setCurrentIndex(tmp)
                self.camera_controls_group.n_buffers_entry.setText( \
                    "{:}".format(self.scan_controls_group.inner_loop_steps_entry.text()))
        # delays can be used in ext and soft trig in case of slow read-out/data transfer
        # and to let motor stabilize but they are not used in AUTO scans
        if self.camera_controls_group.trigger_entry.currentText() == 'AUTO':
            self.camera_controls_group.delay_entry.setEnabled(False)


    def enable_sync_daq_ring(self):
        self.concert_scan.acq_setup.top_up_veto_enabled = self.ring_status_group.sync_daq_inj.isChecked()

    def send_inj_info_to_acqsetup(self, value):
        # info_message("{}".format(value))
        self.concert_scan.acq_setup.top_up_veto_state = value

    def on_camera_connected(self, camera):
        self.concert_scan = ConcertScanThread(self.viewer, camera)
        self.concert_scan.scan_finished_signal.connect(self.end_of_scan)
        self.concert_scan.start()
        # self.camera = camera
        self.scan_controls_group.setEnabled(True)
        self.ffc_controls_group.setEnabled(True)
        self.file_writer_group.setEnabled(True)
        self.ring_status_group.status_monitor.i0_state_changed_signal2.connect(
            self.send_inj_info_to_acqsetup)
        self.ring_status_group.sync_daq_inj.stateChanged.connect(self.enable_sync_daq_ring)


    def start(self):
        self.number_of_scans = 1 # we expect to make at least one scan
        self.start_button.setEnabled(False)
        self.abort_button.setEnabled(True)
        self.return_button.setEnabled(False)
        self.scan_controls_group.setTitle("Scan controls. Status: Experiment is running")
        if self.scan_controls_group.outer_steps > 0:
            # if outer scan parameters are set compute positions of the outer motor
            if self.scan_controls_group.outer_loop_endpoint:
                self.outer_region = linspace(self.scan_controls_group.outer_start,
                                             self.scan_controls_group.outer_start+self.scan_controls_group.outer_range,
                                             self.scan_controls_group.outer_steps)
            else:
                self.outer_region = linspace(self.scan_controls_group.outer_start,
                                             self.scan_controls_group.outer_start+self.scan_controls_group.outer_range,
                                             self.scan_controls_group.outer_steps, False)
            # and make the first move
            if self.scan_controls_group.outer_motor == 'Timer [sec]':
                #time.sleep(self.outer_region[0])
                QTimer.singleShot(self.outer_region[0] * 1000, self.continue_outer_scan)
            else:
                if self.scan_controls_group.outer_motor == 'CT stage [deg]':
                    self.outer_unit = q.deg # change unit to degrees if outer motor rotates sample
                self.motors[self.scan_controls_group.outer_motor]['position'].\
                    set(self.outer_region[0]*self.outer_unit).join()
                self.continue_outer_scan()
            # self.number_of_scans = self.scan_controls_group.outer_steps
        else:
            self.total_experiment_time = time.time()
            self.doscan()

    def continue_outer_scan(self):
        self.number_of_scans = self.scan_controls_group.outer_steps
        self.total_experiment_time = time.time()
        self.doscan()

    def doscan(self):
        self.camera_controls_group.live_off_func()
        # before starting scan we have to create new experiment and update parameters
        # of acquisitions, flat-field correction, camera, consumers, etc based on the user input
        self.set_scan_params()
        # start actual Concert experiment in concert scan thread
        self.concert_scan.start_scan()

    def end_of_scan(self):
        # in the end of scan one outer loop step is made if necessary
        self.number_of_scans -= 1
        if self.number_of_scans:
            if self.scan_controls_group.outer_motor == 'Timer [sec]':
                self.scan_controls_group.setTitle("Experiment is running; next scan will start soon")
                time.sleep(self.outer_region[1] - self.outer_region[0])
                self.scan_controls_group.setTitle("Scan is running")
            else:
                #get index of the next step
                tmp = self.scan_controls_group.outer_steps - self.number_of_scans
                #move motor to the next absolute position in the scan region
                self.motors[self.scan_controls_group.outer_motor]['position'].\
                    set(self.outer_region[tmp]*self.outer_unit).join()
            self.doscan()
        # This section runs only if scan was finished normally, but not aborted
        self.scan_controls_group.setTitle(
            "Scan controls. Status: scans were finished without errors. \
            Total acquisition time {:} seconds".format(int(time.time() - self.total_experiment_time)))
        # End of section
        self.start_button.setEnabled(True)
        self.abort_button.setEnabled(False)

    def set_scan_params(self):
        '''To be called before Experiment.run
           We create new instance of Concert Experiment and set all
           parameters required for correct data acquisition'''

        # SET CAMERA PARAMETER
        # since reference to libuca object was getting lost and camera is passed
        # though a signal, its parameters are changed by means of a function rather
        # then directly setting them from GUI
        if not self.camera_controls_group.ttl_scan.isChecked():
            self.concert_scan.set_camera_params(self.camera_controls_group.buffered,
                                                self.camera_controls_group.buffnum,
                                                self.camera_controls_group.exp_time,
                                                self.camera_controls_group.fps,
                                                self.camera_controls_group.roi_x0,
                                                self.camera_controls_group.roi_width,
                                                self.camera_controls_group.roi_y0,
                                                self.camera_controls_group.roi_height)
        else:
            self.concert_scan.acq_setup.ttl_exp_time = self.camera_controls_group.exp_time
            self.concert_scan.acq_setup.ttl_dead_time = self.camera_controls_group.dead_time


        # SET ACQUISION PARAMETERS
        # Times as floating point numbers [msec] to compute the CT stage motion
        self.concert_scan.acq_setup.dead_time = self.camera_controls_group.dead_time
        self.concert_scan.acq_setup.exp_time = self.camera_controls_group.exp_time
        # Inner motor and scan intervals
        self.concert_scan.acq_setup.motor = self.motors[self.scan_controls_group.inner_motor]
        if self.scan_controls_group.inner_motor == 'CT stage [deg]':
            self.concert_scan.acq_setup.units = q.deg
        self.concert_scan.acq_setup.cont = self.scan_controls_group.inner_cont
        self.concert_scan.acq_setup.start = self.scan_controls_group.inner_start
        self.concert_scan.acq_setup.nsteps = self.scan_controls_group.inner_steps
        self.concert_scan.acq_setup.range = self.scan_controls_group.inner_range
        self.concert_scan.acq_setup.endp = self.scan_controls_group.inner_endpoint
        self.concert_scan.acq_setup.calc_step()
        # SET shutter
        self.concert_scan.ffc_setup.shutter = self.shutter
        # SET FFC parameters
        if self.scan_controls_group.ffc_before or self.scan_controls_group.ffc_after:
            try:
                self.concert_scan.ffc_setup.flat_motor = self.motors[self.ffc_controls_group.flat_motor]
            except:
                info_message("Select flat field motor to acquire flats")
            self.concert_scan.ffc_setup.radio_position = self.ffc_controls_group.radio_position * q.mm
            self.concert_scan.ffc_setup.flat_position = self.ffc_controls_group.flat_position * q.mm
            self.concert_scan.acq_setup.num_flats = self.ffc_controls_group.num_flats
            self.concert_scan.acq_setup.num_darks = self.ffc_controls_group.num_darks

        # POPULATE THE LIST OF ACQUISITIONS
        acquisitions = []
        # ffc before
        if self.scan_controls_group.ffc_before:
            acquisitions.append(self.concert_scan.acq_setup.flats_softr)
            if self.ffc_controls_group.num_darks > 0:
                acquisitions.append(self.concert_scan.acq_setup.darks_softr)
        # projections
        if self.camera_controls_group.trig_mode == "EXTERNAL":
            if self.camera_controls_group.buffered:
                acquisitions.append(self.concert_scan.acq_setup.tomo_pso_acq_buf)
            else:
                acquisitions.append(self.concert_scan.acq_setup.tomo_pso_acq)
        elif self.camera_controls_group.trig_mode == "AUTO": #make option avaliable only when connected to DIMAX
            # velocitymax = tomo_max_speed(self.setup.camera.roi_width,
            #                           self.setup.camera.frame_rate)
            # velocity = self.scan_controls_group.inner_range * q.deg / (self.scan_controls_group.inner_loop_steps_entry
            #                           / self.camera_controls_group.fps)
            # if velocity > velocitymax:
            #     warning_message("Rotation speed is too large for this sensor width. \
            #                     Reduce fps or increase exposure time \
            #                     to avoid blurring.")
            acquisitions.append(self.concert_scan.acq_setup.tomo_dimax_acq)
        else: #trig_mode is SOFTWARE and rotation is step-wise
            acquisitions.append(self.concert_scan.acq_setup.tomo_softr)
        # ffc after
        if self.scan_controls_group.ffc_after:
            acquisitions.append(self.concert_scan.acq_setup.flats2_softr)

        # special case when ttl scan is used
        if self.camera_controls_group.ttl_scan.isChecked():
            acquisitions = []
            acquisitions.append(self.concert_scan.acq_setup.ttl_acq)

        # CREATE NEW WALKER
        if self.file_writer_group.isChecked():
            self.concert_scan.walker = DirectoryWalker(root=self.file_writer_group.root_dir,
                                                       dsetname=self.file_writer_group.dsetname)
        else:
            # if writer is disabled we do not need walker as well
            self.concert_scan.walker = None

        # WE MUST DETACH OLD WRITER IF IT EXISTS
        try:
            self.concert_scan.cons_writer.detach()
            self.concert_scan.cons_viewer.detach()
        except:
            pass

        # CREATE NEW INSTANCE OF CONCERT EXPERIMENT
        self.concert_scan.create_experiment(acquisitions,
                                            self.file_writer_group.ctsetname,
                                            self.file_writer_group.separate_scans)

        # FINALLY ATTACH CONSUMERS
        if self.file_writer_group.isChecked():
            self.concert_scan.attach_writer()
        self.concert_scan.attach_viewer()


    def abort(self):
        self.number_of_scans = 0
        self.concert_scan.abort_scan()
        self.start_button.setEnabled(True)
        self.abort_button.setEnabled(False)
        self.return_button.setEnabled(True)
        # calls global Concert abort() command
        # abort concert experiment not necessarily stops motor
        self.scan_status_update_timer.stop()
        if self.camera_controls_group.camera.state == 'recording':
            self.camera_controls_group.camera.stop_recording()
        # use motor list to abort
        # device_abort(m for m in self.motors.values() if m is not None)
        self.motor_control_group.stop_motors_func()
        self.motor_control_group.close_shutter_func()
        self.scan_controls_group.setTitle(
            "Scan controls. Status: scan was aborted by user")

    def return_to_start(self):
        self.motors[self.scan_controls_group.inner_motor]['position']. \
            set(self.scan_controls_group.inner_start * self.concert_scan.acq_setup.units)
        if self.scan_controls_group.outer_steps > 1 and \
                self.scan_controls_group.outer_motor != 'Timer [sec]':
            self.motors[self.scan_controls_group.outer_motor]['position']. \
                set(self.outer_region[0] * self.outer_unit).join()
        info_message("Returned to start position")

    # EXECUTION CONTROL
    def check_scan_status(self):
        if self.f.done():
            self.end_of_scan()

    def set_viewer_limits(self):
        self.camera_controls_group.viewer.limits = \
            [int(self.camera_controls_group.viewer_lowlim_entry.text()),
             int(self.camera_controls_group.viewer_highlim_entry.text())]

    def relate_nbuf_to_nproj(self):
        if self.camera_controls_group.trigger_entry.currentText() == 'EXTERNAL' or \
                (self.camera_controls_group.trigger_entry.currentText() == 'AUTO' and\
                 self.camera_controls_group.buffered):
            self.camera_controls_group.n_buffers_entry.setText(\
                "{:}".format(self.scan_controls_group.inner_loop_steps_entry.text()))


if __name__ == '__main__':
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    root_dir = os.path.dirname(os.path.abspath(__file__))
    style_file = QFile(os.path.join(root_dir, "styles/breeze/dark.qss"))
    style_file.open(QFile.ReadOnly | QFile.Text)
    stream = QTextStream(style_file)
    # Set application style to dark; Comment following line to unset
    # app.setStyleSheet(stream.readAll())
    ex = GUI()
    sys.exit(app.exec_())
