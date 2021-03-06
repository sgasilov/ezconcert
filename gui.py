from edc.shutter import CLSShutter
from edc.motor import CLSLinear, ABRS, SimMotor
from scans_concert import ConcertScanThread
from concert.devices.base import abort as device_abort
from concert.storage import DirectoryWalker
from concert.ext.viewers import PyplotImageViewer
from concert.base import TransitionNotAllowed
# from concert.session.utils import ddoc, dstate, pdoc, code_of, abort
from concert.quantities import q
import sys
from PyQt5.QtWidgets import QGroupBox, QDialog, QApplication, QGridLayout
from PyQt5.QtWidgets import QLabel, QPushButton, QDoubleSpinBox
# from PyQt5.QtWidgets import QLineEdit, QComboBox, QCheckBox
from PyQt5.QtCore import QTimer, QEventLoop
from camera_controls import CameraControlsGroup
from file_writer import FileWriterGroup
from ffc_settings import FFCSettingsGroup
from ring_status import RingStatusGroup
from scan_controls import ScanControlsGroup
from message_dialog import info_message, error_message
from motor_controls import EpicsMonitorFloat, EpicsMonitorFIS, MotionThread, HomeThread
# from time import sleep
import logging
import concert
from numpy import linspace
import time
concert.require("0.11.0")


LOG = logging.getLogger("ezconcert")
LOG.setLevel(logging.DEBUG)
# create handlers
# ch = logging.StreamHandler()
fh = logging.FileHandler('ezconcert.log')
# formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
# ch.setFormatter(formatter)
fh.setFormatter(formatter)
# add handlers
# LOG.addHandler(ch)
LOG.addHandler(fh)


# Adam's interface EPICS-Concert interface


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
        self.connect_hor_mot_button = QPushButton("horizontal stage")
        self.connect_vert_mot_button = QPushButton("vertical stage")
        self.connect_CT_mot_button = QPushButton("CT stage")
        self.connect_shutter_button = QPushButton("Imaging shutter")
        # this are to be implemeted depending on low-level interface (EPICS/Tango/etc)
        self.connect_hor_mot_button.clicked.connect(self.connect_hor_motor_func)
        self.connect_vert_mot_button.clicked.connect(self.connect_vert_motor_func)
        self.connect_CT_mot_button.clicked.connect(self.connect_CT_motor_func)
        self.connect_shutter_button.clicked.connect(self.connect_shutter_func)

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
        self.shutter_label = QLabel()
        self.shutter_label.setText("Not connected")
        self.shutter_entry = QLabel()

        # position entry
        self.hor_mot_pos_move = QDoubleSpinBox()
        self.hor_mot_pos_move.setDecimals(3)
        self.hor_mot_pos_move.setRange(-100, 100)
        self.vert_mot_pos_move = QDoubleSpinBox()
        self.vert_mot_pos_move.setDecimals(3)
        self.vert_mot_pos_move.setRange(-100, 100)
        self.CT_mot_pos_move = QDoubleSpinBox()
        self.CT_mot_pos_move.setDecimals(3)
        self.CT_mot_pos_move.setRange(-720, 720)

        # Move Buttons
        self.stop_motors_button = QPushButton("STOP ALL")
        self.move_hor_mot_button = QPushButton("Move To")
        self.move_hor_mot_button.setEnabled(False)
        self.move_vert_mot_button = QPushButton("Move To")
        self.move_vert_mot_button.setEnabled(False)
        self.move_CT_mot_button = QPushButton("Move To")
        self.move_CT_mot_button.setEnabled(False)
        self.home_CT_mot_button = QPushButton("Home")
        self.home_CT_mot_button.setEnabled(False)
        self.reset_CT_mot_button = QPushButton("Reset")
        self.reset_CT_mot_button.setEnabled(False)
        self.open_shutter_button = QPushButton("Open")
        self.open_shutter_button.setEnabled(False)
        self.close_shutter_button = QPushButton("Close")
        self.close_shutter_button.setEnabled(False)

        self.move_hor_mot_button.clicked.connect(self.hor_move_func)
        self.move_vert_mot_button.clicked.connect(self.vert_move_func)
        self.home_CT_mot_button.clicked.connect(self.CT_home_func)
        self.reset_CT_mot_button.clicked.connect(self.CT_reset_func)
        self.move_CT_mot_button.clicked.connect(self.CT_move_func)
        self.open_shutter_button.clicked.connect(self.open_shutter_func)
        self.close_shutter_button.clicked.connect(self.close_shutter_func)
        self.stop_motors_button.clicked.connect(self.stop_motors_func)

        # external subgroups to set parameters
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

        self.set_layout_motor_control_group()
        self.set_layout()

        # THREADS AND SIGNALS/CONNECTIONS
        self.concert_scan = None
        self.motion_CT = None
        self.motion_vert = None
        self.motion_hor = None

        # connect to timer and shutter and populate lists of motors
        self.connect_time_motor_func()
        # self.connect_shutter_func()

        # self.scan_controls_group.inner_loop_flats_0.clicked.connect(self.add_buff)

        self.tmp = 0
        self.nbuf = 0
        self.camera_controls_group.viewer_lowlim_entry.editingFinished.connect(
            self.set_viewer_limits)
        self.camera_controls_group.viewer_highlim_entry.editingFinished.connect(
            self.set_viewer_limits)
        self.camera_controls_group.trigger_entry.currentIndexChanged.connect(self.restrict_step_and_shoot_to_soft_trig)
        self.scan_controls_group.inner_loop_steps_entry.editingFinished.connect(
            self.relate_nbuf_to_nproj)


        # Outer loop counter
        self.number_of_scans = 1
        self.outer_region = []
        self.outer_step = 0.0
        self.outer_unit = q.mm

        self.take_flats_darks_only = False

        self.show()
        LOG.info("Start gui.py")

    def restrict_step_and_shoot_to_soft_trig(self):
        if self.camera_controls_group.trigger_entry.currentText() != 'SOFTWARE':
            self.scan_controls_group.inner_loop_continuous.setChecked(True)
            self.camera_controls_group.n_buffers_entry.setText( \
                "{:}".format(self.scan_controls_group.inner_loop_steps_entry.text()))
            if self.camera_controls_group.trigger_entry.currentText() == 'EXTERNAL':
                tmp = self.camera_controls_group.buffered_entry.findText("YES")
                self.camera_controls_group.buffered_entry.setCurrentIndex(tmp)
        else:
            self.scan_controls_group.inner_loop_continuous.setChecked(False)
            tmp = self.camera_controls_group.buffered_entry.findText("NO")
            self.camera_controls_group.buffered_entry.setCurrentIndex(tmp)


    def enable_sync_daq_ring(self):
        self.concert_scan.acq_setup.top_up_veto_enabled = self.ring_status_group.sync_daq_inj.isChecked()

    def send_inj_info_to_acqsetup(self, value):
        # info_message("{}".format(value))
        self.concert_scan.acq_setup.top_up_veto_state = value


    def set_layout_motor_control_group(self):
        layout = QGridLayout()
        layout.addWidget(self.stop_motors_button, 0, 1, 2, 1)
        layout.addWidget(self.connect_CT_mot_button, 0, 2, 1, 1)
        layout.addWidget(self.connect_vert_mot_button, 0, 5, 1, 1)
        layout.addWidget(self.connect_hor_mot_button, 0, 8, 1, 1)
        layout.addWidget(self.connect_shutter_button, 0, 11, 1, 1)
        layout.addWidget(self.move_CT_mot_button, 0, 3, 1, 1)
        layout.addWidget(self.home_CT_mot_button, 0, 4, 1, 1)
        layout.addWidget(self.reset_CT_mot_button, 1, 4, 1, 1)
        layout.addWidget(self.move_vert_mot_button, 0, 6, 1, 1)
        layout.addWidget(self.move_hor_mot_button, 0, 9, 1, 1)
        layout.addWidget(self.open_shutter_button, 0, 12, 1, 1)
        layout.addWidget(self.close_shutter_button, 1, 12, 1, 1)
        # layout.addWidget(self.mot_pos_info_label, 1, 1)
        layout.addWidget(self.CT_mot_pos_label, 1, 2)
        layout.addWidget(self.CT_mot_pos_entry, 1, 3)
        layout.addWidget(self.vert_mot_pos_label, 1, 5)
        layout.addWidget(self.vert_mot_pos_entry, 1, 6)
        layout.addWidget(self.hor_mot_pos_label, 1, 8)
        layout.addWidget(self.hor_mot_pos_entry, 1, 9)
        layout.addWidget(self.shutter_label, 1, 11)
        # layout.addWidget(self.shutter_entry, 1, 12)
        self.motor_control_group.setLayout(layout)
        layout.addWidget(self.hor_mot_pos_move, 1, 9)
        layout.addWidget(self.vert_mot_pos_move, 1, 6)
        layout.addWidget(self.CT_mot_pos_move, 1, 3)

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
            self.hor_mot_pos_label.setText("Position [mm]")
            tmp = "Horizontal [mm]"
            self.motors[tmp] = self.hor_motor
            self.connect_hor_mot_button.setEnabled(False)
            self.move_hor_mot_button.setEnabled(True)
            self.scan_controls_group.inner_loop_motor.addItem(tmp)
            self.scan_controls_group.outer_loop_motor.addItem(tmp)
            self.ffc_controls_group.motor_options_entry.addItem(tmp)
            self.hor_mot_monitor = EpicsMonitorFloat(self.hor_motor.RBV)
            self.hor_mot_monitor.i0_state_changed_signal.connect(
                self.hor_mot_pos_label.setText)
            self.hor_mot_monitor.i0.run_callback(self.hor_mot_monitor.call_idx)

    def connect_vert_motor_func(self):
        try:
            self.vert_motor = CLSLinear("SMTR1605-2-B10-10:mm", encoded=True)
        except:
            error_message("Can not connect to vertical stage, try again")
        if self.vert_motor is not None:
            self.vert_mot_pos_label.setText("Position [mm]")
            tmp = "Vertical [mm]"
            self.motors[tmp] = self.vert_motor
            self.connect_vert_mot_button.setEnabled(False)
            self.move_vert_mot_button.setEnabled(True)
            self.scan_controls_group.inner_loop_motor.addItem(tmp)
            self.scan_controls_group.outer_loop_motor.addItem(tmp)
            self.ffc_controls_group.motor_options_entry.addItem(tmp)
            self.vert_mot_monitor = EpicsMonitorFloat(self.vert_motor.RBV)
            self.vert_mot_monitor.i0_state_changed_signal.connect(
                self.vert_mot_pos_label.setText)
            self.vert_mot_monitor.i0.run_callback(self.vert_mot_monitor.call_idx)

    def connect_CT_motor_func(self):
        try:
            self.CT_motor = ABRS("ABRS1605-01:deg", encoded=True)
        except:
            error_message("Could not connect to CT stage, try again")
        if self.CT_motor is not None:
            self.CT_mot_pos_label.setText("Position [deg]")
            tmp = "CT stage [deg]"
            self.motors[tmp] = self.CT_motor
            self.connect_CT_mot_button.setEnabled(False)
            self.move_CT_mot_button.setEnabled(True)
            self.home_CT_mot_button.setEnabled(True)
            self.reset_CT_mot_button.setEnabled(True)
            self.scan_controls_group.inner_loop_motor.addItem(tmp)
            self.CT_mot_monitor = EpicsMonitorFloat(self.CT_motor.RBV)
            self.CT_mot_monitor.i0_state_changed_signal.connect(
                self.CT_mot_pos_label.setText)
            self.CT_mot_monitor.i0.run_callback(self.CT_mot_monitor.call_idx)
            # self.scan_controls_group.inner_loop_motor.

    def connect_time_motor_func(self):
        try:
            self.time_motor = SimMotor(1.0*q.mm)
        except:
            error_message("Can not connect to timer")
        if self.time_motor is not None:
            tmp = "Timer [sec]"
            self.motors[tmp] = self.time_motor
            self.scan_controls_group.inner_loop_motor.addItem(tmp)
            self.scan_controls_group.outer_loop_motor.addItem(tmp)

    def connect_shutter_func(self):
        try:
            self.shutter = CLSShutter("ABRS1605-01:fis")
        except:
            error_message("Could not connect to fast imaging shutter, try again")
        if self.shutter is not None:
            self.shutter_label.setText("Connected")
            tmp = "Shutter []"
            self.motors[tmp] = self.shutter
            self.connect_shutter_button.setEnabled(False)
            self.open_shutter_button.setEnabled(True)
            self.close_shutter_button.setEnabled(True)
            self.shutter_monitor = EpicsMonitorFIS(self.shutter.STATE)
            self.shutter_monitor.i0_state_changed_signal.connect(
                self.shutter_label.setText)
            self.shutter_monitor.i0.run_callback(self.shutter_monitor.call_idx)

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
                time.sleep(self.outer_region[0])
            else:
                if self.scan_controls_group.outer_motor == 'CT stage [deg]':
                    self.outer_unit = q.deg # change unit to degrees if outer motor rotates sample
                self.motors[self.scan_controls_group.outer_motor]['position'].\
                    set(self.outer_region[0]*self.outer_unit).join()
            self.number_of_scans = self.scan_controls_group.outer_steps
        self.total_experiment_time = time.time()
        self.doscan()


    def doscan(self):
        # before starting scan we have to create new experiment and update parameters
        # of acquisitions, flat-field correction, camera, consumers, etc based on the user input
        self.set_scan_params()
        # start actual Concert experiment in concert scan thread
        self.concert_scan.start_scan()

    def end_of_scan(self):
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
            Total acquisition time {:.2f} seconds".format(time.time() - self.total_experiment_time))
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
        self.concert_scan.set_camera_params(self.camera_controls_group.trig_mode,
                                            self.camera_controls_group.acq_mode,
                                            self.camera_controls_group.buffered,
                                            self.camera_controls_group.buffnum,
                                            self.camera_controls_group.exp_time,
                                            self.camera_controls_group.roi_x0,
                                            self.camera_controls_group.roi_width,
                                            self.camera_controls_group.roi_y0,
                                            self.camera_controls_group.roi_height)

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
        # info_message("{:}".format(self.concert_scan.acq_setup.step))
        # Outer motor and scan intervals
        # the outer motor scan be setup in the concert_scan to repeat exp multiple times
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
        # acquisitions.append(self.concert_scan.acq_setup.rec_seq_with_inj_sync)
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
        device_abort(m for m in self.motors.values() if m is not None)
        self.close_shutter_func()
        self.scan_controls_group.setTitle(
            "Scan controls. Status: scan was aborted by user")

    def return_to_position(self):
        info_message("Returning to position...")
        # info_message(result)

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

    # motor functions #MUST BE MOVED TO MOTOR CONTROLS!!!

    def open_shutter_func(self):
        if self.shutter is None:
            return
        else:
            try:
                self.shutter.open().join()
            except TransitionNotAllowed:
                return

    def close_shutter_func(self):
        if self.shutter is None:
            return
        else:
            try:
                self.shutter.close().join()
            except TransitionNotAllowed:
                return

    def CT_home_func(self):
        '''Home the stage'''
        if self.CT_motor is None:
            return
        else:
            # if you move to x then home() you can't move to x
            # setting choice to 0 at home position seems to fix this
            self.motion_CT = HomeThread(self.CT_motor)
            self.motion_CT.start()
            # there is a behaviour that the stage will not be able to move
            # to the same position twice in a row so reset the motion
            self.CT_mot_pos_move.setValue(0.0)
            # self.CT_move_func()

    def CT_move_func(self):
        '''Move the stage'''
        if self.CT_motor is None:
            return
        else:
            self.CT_motor.stepvelocity = 5.0 * q.deg/q.sec
            self.motion_CT = MotionThread(self.CT_motor, self.CT_mot_pos_move)
            self.motion_CT.start()


    def CT_reset_func(self):
        '''Reset the stage and move to home'''
        if self.CT_motor is None:
            return
        else:
            self.CT_motor.reset()
            self.CT_mot_pos_move.setValue(0.0)
            self.CT_move_func()
            info_message("Reset finished. Please wait for state motion to stop.")

    def hor_move_func(self):
        if self.hor_motor is None:
            return
        else:
            self.motion_hor = MotionThread(self.hor_motor, self.hor_mot_pos_move)
            self.motion_hor.start()

    def vert_move_func(self):
        if self.vert_motor is None:
            return
        else:
            self.motion_vert = MotionThread(self.vert_motor, self.vert_mot_pos_move)
            self.motion_vert.start()

    def stop_motors_func(self):
        if self.motion_CT is not None:
            self.motion_CT.abort()
        if self.motion_vert is not None:
            self.motion_vert.abort()
        if self.motion_hor is not None:
            self.motion_hor.abort()
        device_abort(m for m in self.motors.values() if m is not None)


if __name__ == '__main__':
    app = QApplication(sys.argv)
    loop = QEventLoop(app)
    ex = GUI()
    sys.exit(app.exec_())
