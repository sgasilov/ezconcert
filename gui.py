
# PyQT imports
from PyQt5.QtWidgets import QGroupBox, QDialog, QApplication, QGridLayout
from PyQt5.QtWidgets import QLabel, QPushButton, QFileDialog, QHBoxLayout
from PyQt5.QtWidgets import QLineEdit, QComboBox, QCheckBox
from PyQt5.QtCore import QTimer, QEventLoop, QFile, QTextStream
# GUI groups and objects
from camera_controls import CameraControlsGroup
from login_dialog import Login
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
from concert.devices.shutters.dummy import Shutter as DummyShutter
from concert.quantities import q
import sys
# from time import sleep
import logging
import concert
# Miscellaneous imports
from numpy import linspace
import yaml
import time
import argparse
import os
import numpy as np
from datetime import date
# Dark style
# noinspection PyUnresolvedReferences
from styles.breeze import styles_breeze
from edc import log
concert.require("0.11.0")




def process_cl_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('-d', '--debug', action='store_const', const=True)  # optional flags
    parsed_args, unparsed_args = parser.parse_known_args()
    return parsed_args, unparsed_args


class GUI(QDialog):
    '''
    Creates main GUI, holds references to physical devices, and
    provides start/abort controls for Concert scans, and holds
    4 groups where parameters can be entered
    '''

    def __init__(self, *args, **kwargs):
        super(GUI, self).__init__(*args, **kwargs)
        self.setWindowTitle('BMIT GUI')

        self.show()

        # call login dialog
        # use QTimer to make sure the main loop is initialized
        self.login_parameters = {}
        QTimer.singleShot(0, self.login)

        self._log = None
        self.log = None

        # CAMERA
        self.camera = None
        self.viewer = PyplotImageViewer()

        # Thread in which concert.experiment will be started
        self.concert_scan = None

        # logical devices
        self.motor_inner = None
        self.motor_outer = None
        self.motor_flat = None

        # EXECUTION CONTROL BUTTONS
        self.start_button = QPushButton("START")
        self.start_button.clicked.connect(self.start)
        self.abort_button = QPushButton("ABORT")
        self.abort_button.setEnabled(False)
        self.abort_button.clicked.connect(self.abort)
        self.return_button = QPushButton("RETURN")
        self.return_button.clicked.connect(self.return_to_start)
        self.scan_fps_entry = QLabel()

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
        self.reco_enabled = False

        # MOTORS
        # dictionary with references to all connected physical devices and their labels
        self.motors = {}
        self.shutter = None
        # timer is created automatically in motorscontrolgroup constructor
        self.motors["Timer [sec]"] = self.motor_control_group.time_motor
        self.scan_controls_group.inner_loop_motor.addItem("Timer [sec]")
        self.scan_controls_group.outer_loop_motor.addItem("Timer [sec]")
        # populate motors dictionary when physical device is connected
        self.motor_control_group.connect_hor_mot_button.clicked.connect(self.add_mot_hor)
        self.motor_control_group.connect_vert_mot_button.clicked.connect(self.add_mot_vert)
        self.motor_control_group.connect_CT_mot_button.clicked.connect(self.add_mot_CT)
        self.motor_control_group.connect_shutter_button.clicked.connect(self.add_mot_sh)

        # Variables for outer loop
        self.number_of_scans = 1
        self.outer_region = []
        self.outer_step = 0.0
        self.outer_unit = q.mm

        # various timers
        self.scan_timer = QTimer()
        # timer to show total exp time so far
        self.time_elapsed = QTimer()
        self.time_elapsed.timeout.connect(self.update_elapsed_time)
        self.start_time_elapsed = 0
        self.total_experiment_time = 0

        # SIGNALS/CONNECTIONS
        self.camera_controls_group.viewer_lowlim_entry.editingFinished.connect(
            self.set_viewer_limits)
        self.camera_controls_group.viewer_highlim_entry.editingFinished.connect(
            self.set_viewer_limits)
        self.scan_controls_group.inner_loop_steps_entry.editingFinished.connect(
            self.autoset_n_buffers)
        self.scan_controls_group.inner_loop_motor.currentIndexChanged.connect(
            self.autoset_some_params_for_CTstage_motor)
        self.camera_controls_group.trigger_entry.currentIndexChanged.connect(
            self.enable_TTL_scan_if_Dimax_and_Ext_trig)
        self.camera_controls_group.live_on_button.clicked.connect(
            self.lv_timer_func)
        self.camera_controls_group.live_off_button.clicked.connect(
            self.lv_timer_stop_func)
        #self.reco_settings_group.toggled.connect(self.change_reco_enabled_flag)


        # SAVE/LOAD params group
        self.QFD = QFileDialog()
        self.exp_imp_button_grp = QGroupBox(title='Various')
        self.button_save_params = QPushButton("Export settings and params to file")
        self.button_load_params = QPushButton("Read settings and params from file")
        self.button_log_file = QPushButton("Select log file")
        self.button_save_params.clicked.connect(self.dump2yaml)
        self.button_load_params.clicked.connect(self.load_from_yaml)
        self.button_log_file.clicked.connect(self.select_log_file_func)
        self.spacer = QLabel()
        self.spacer.setFixedWidth(100)

        self.time_elapsed_label = QLabel()
        self.time_elapsed_label.setText("Time elapsed [sec]")
        self.time_elapsed_entry = QLabel()
        self.viewer_lowlim_label = QLabel()
        self.viewer_lowlim_label.setText("Viewer low limit")
        self.viewer_lowlim_entry = QLineEdit()
        self.viewer_highlim_label = QLabel()
        self.viewer_highlim_label.setText("Viewer high limit")
        self.viewer_highlim_entry = QLineEdit()
        button_grp_layout = QHBoxLayout()
        button_grp_layout.addWidget(self.time_elapsed_label)
        button_grp_layout.addWidget(self.time_elapsed_entry)
        button_grp_layout.addWidget(self.spacer)
        button_grp_layout.addWidget(self.viewer_lowlim_label)
        button_grp_layout.addWidget(self.viewer_lowlim_entry)
        button_grp_layout.addWidget(self.viewer_highlim_label)
        button_grp_layout.addWidget(self.viewer_highlim_entry)
        button_grp_layout.addWidget(self.spacer)
        button_grp_layout.addWidget(self.button_save_params)
        button_grp_layout.addWidget(self.button_load_params)
        #button_grp_layout.addWidget(self.select_log_file_func)
        self.exp_imp_button_grp.setLayout(button_grp_layout)
        self.exp_imp_button_grp.setEnabled(False)
        self.viewer_lowlim_entry.editingFinished.connect(
            self.set_viewer_limits_alt)
        self.viewer_highlim_entry.editingFinished.connect(
            self.set_viewer_limits_alt)

        # finally
        self.set_layout()

    def lv_timer_func(self):
        self.time_elapsed_entry.setText('0.0')
        self.start_time_elapsed = time.time()
        self.time_elapsed.start(500)

    def lv_timer_stop_func(self):
        self.time_elapsed.stop()

    def closeEvent(self, event):
        if self.camera_controls_group.camera is not None and \
                self.camera_controls_group.camera_model != "Dummy camera":
            if self.camera_controls_group.camera.state == 'recording':
                self.camera_controls_group.camera.stop_recording()
            self.camera_controls_group.camera.uca._unref()
            del self.camera

    def login(self):
        login_dialog = Login(self.login_parameters)
        if login_dialog.exec_() != QDialog.Accepted:
            self.exit()
        else:
            self.file_writer_group.root_dir_entry.setText(self.login_parameters['expdir'])
            self.camera_controls_group.last_dir = self.login_parameters['expdir']
            td = date.today()
            tdstr = "{}.{}.{}".format(td.year, td.month, td.day)
            logfname = os.path.join(self.login_parameters['expdir'],'exp-log-'+tdstr+'.log')
            if self.login_parameters.has_key('project'):
                logfname = os.path.join(self.login_parameters['expdir'],'{}-log-{}-{}.log'.
                    format(self.login_parameters['project'], self.login_parameters['bl'], tdstr))
            try:
                open(logfname, 'a').close()
            except:
                warning_message('Cannot create log file in the selected directory. \n'
                            'Check permissions and restart.')
                self.exit()
            self._log = log
            self._log.log_to_file(logfname, logging.DEBUG)
            self.log = self._log.get_module_logger(__name__)
            self.log.info("Start gui.py")
            # add motors automatically on start
            self.motor_control_group.connect_hor_mot_button.animateClick()
            self.motor_control_group.connect_vert_mot_button.animateClick()
            self.motor_control_group.connect_CT_mot_button.animateClick()
            self.motor_control_group.connect_shutter_button.animateClick()
            self.camera_controls_group.log = self.log

    def exit(self):
        self.close()

    def set_layout(self):
        main_layout = QGridLayout()
        main_layout.addWidget(self.camera_controls_group)
        main_layout.addWidget(self.exp_imp_button_grp)
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

    def on_camera_connected(self, camera):
        self.concert_scan = ConcertScanThread(self.viewer, camera)
        self.concert_scan.scan_finished_signal.connect(self.end_of_scan)
        self.concert_scan.start()
        self.scan_controls_group.setEnabled(True)
        self.ffc_controls_group.setEnabled(True)
        self.file_writer_group.setEnabled(True)
        self.exp_imp_button_grp.setEnabled(True)
        self.reco_settings_group.setEnabled(True)
        self.ring_status_group.status_monitor.i0_state_changed_signal2.connect(
            self.send_inj_info_to_acqsetup)
        self.ring_status_group.sync_daq_inj.stateChanged.connect(self.enable_sync_daq_ring)
        self.concert_scan.acq_setup.log = self.log
        self.concert_scan.log = self.log

    def ena_disa_all(self, val=True):
        self.motor_control_group.setEnabled(val)
        self.camera_controls_group.setEnabled(val)
        self.camera_controls_group.viewer_lowlim_entry.setEnabled(True)
        self.camera_controls_group.viewer_highlim_entry.setEnabled(True)
        self.ffc_controls_group.setEnabled(val)
        self.file_writer_group.setEnabled(val)
        self.ring_status_group.setEnabled(val)
        self.button_load_params.setEnabled(val)
        self.button_save_params.setEnabled(val)
        self.scan_controls_group.ena_disa_all_entries(val)
        self.reco_settings_group.setEnabled(val)

    def get_outer_motor_grid(self):
        self.scan_controls_group.get_outer_range()
        self.scan_controls_group.get_inner_range()
        if self.scan_controls_group.outer_steps > 0:
            self.number_of_scans = self.scan_controls_group.outer_steps
            if self.scan_controls_group.outer_loop_endpoint:
                return linspace(self.scan_controls_group.outer_start,
                                 self.scan_controls_group.outer_start + self.scan_controls_group.outer_range,
                                 self.scan_controls_group.outer_steps)
            else:
                return linspace(self.scan_controls_group.outer_start,
                                 self.scan_controls_group.outer_start + self.scan_controls_group.outer_range,
                                 self.scan_controls_group.outer_steps, False)
        elif self.scan_controls_group.outer_steps == 0:
            self.number_of_scans = 1
            if self.scan_controls_group.outer_motor != 'Timer [sec]':
                return [self.motors[self.scan_controls_group.outer_motor].position.magnitude]
            else:
                return [0]
        else:
            error_message("Outer motor start/steps/range entered incorrectly ")
            self.abort()
            return None

    def check_data_overwrite(self):
        if self.file_writer_group.isChecked():
            if os.path.exists(os.path.join( \
                    self.file_writer_group.root_dir, \
                    self.file_writer_group.ctsetname.format(1))):
                warning_message("Output directory exists. \n"
                                "Change root dir or name pattern"
                                "and start again")
                self.abort()
                return None

    def start(self):
        self.ena_disa_all(False)
        self.start_button.setEnabled(False)
        self.abort_button.setEnabled(True)
        self.return_button.setEnabled(False)
        self.log.info("** {:}, {:}".format(self.camera_controls_group.live_on,self.camera_controls_group.lv_stream2disk_on ))
        if self.camera_controls_group.live_on or \
                self.camera_controls_group.lv_stream2disk_on:
            self.camera_controls_group.live_off_func()
        self.lv_timer_func()
        if self.scan_controls_group.delay_time == 0:
            self.start_real()
        elif self.scan_controls_group.delay_time > 0:
            self.log.info("*** Delayed start")
            self.scan_controls_group.setTitle("Scan controls. Status: waiting for delayed start")
            self.scan_timer.singleShot(self.scan_controls_group.delay_time*60000, self.start_real)
        else:
            self.abort()

    def update_elapsed_time(self):
        self.time_elapsed_entry.setText("{:0.1f}".format(time.time() - self.start_time_elapsed))

    def start_real(self):
        #self.check_data_overwrite()
        self.auto_set_buffers_ext_edge()
        if self.check_discrepancy_starting_point():
            return
        #if self.scan_controls_group.inner_loop_continuous:
        #    self.validate_velocity()
        self.log.info("***** EXPERIMENT STARTED *****")
        time.sleep(0.5)
        self.number_of_scans = 1 # we expect to make at least one scan
        self.scan_controls_group.setTitle("Scan controls. Status: Experiment is running")
        self.set_scan_params()
        self.create_exp()
        if self.scan_controls_group.readout_intheend.isChecked():
            self.camera_controls_group.live_on_func_ext_trig()
        self.outer_region = self.get_outer_motor_grid()
        if self.outer_region is not None:
            self.move_to_start(begin_exp=True)

    def move_to_start(self, begin_exp=True):
        # insert check large discrepancy between present position and start position
        self.log.info("Moving inner motor to starting point")

        # workaround for EDC/Soloist problem -  won't move sometime after abort
        # if position hasn't been change a tiny amount
        if abs(self.motors[self.scan_controls_group.inner_motor].position.magnitude - \
                self.scan_controls_group.inner_start) > 0.01:
            self.log.debug("Tiny move to avoid bug with CT stage not moving")
            self.motor_control_group.motion_CT = MotionThread(
                self.motors[self.scan_controls_group.inner_motor],
                self.motors[self.scan_controls_group.inner_motor].position.magnitude+2)
            self.motor_control_group.motion_CT.start()
            while self.motor_control_group.motion_CT.is_moving:
                time.sleep(1)
        # end of workaround for CT stage

        self.motor_control_group.motion_CT = MotionThread(
                    self.motors[self.scan_controls_group.inner_motor],
                    self.scan_controls_group.inner_start)
        # outer motor - name of the thread doesn't matter,
        # used one of the fixed internal names which can be aborted if necessary
        self.motor_control_group.motion_vert = MotionThread(
                            self.motors[self.scan_controls_group.outer_motor],
                            self.outer_region[0])
        if begin_exp:
            self.motor_control_group.motion_CT.motion_over_signal.connect(self.begin_scans)
            self.motor_control_group.motion_vert.motion_over_signal.connect(self.begin_scans)

        self.motor_control_group.motion_CT.start()
        self.motor_control_group.motion_vert.start()

    def check_discrepancy_starting_point(self):
        # required to make sure that stage doesn't make many revolutions
        # in case if some cable/tubes are connected to sample
        # also PSO is not stable beyond > 360
        if self.scan_controls_group.inner_motor == 'CT stage [deg]':
            if (self.camera_controls_group.trig_mode == "EXTERNAL" and \
                    abs(self.motors[self.scan_controls_group.inner_motor].position.magnitude)>180) \
                    or (abs(self.motors[self.scan_controls_group.inner_motor].position.magnitude - \
                           self.scan_controls_group.inner_start)>180):
                warning_message("CT stage needs to make more than half turn to go to start position \n"
                                "Move it back to 0 (minus will move counter-clockwise) or home it (clockwise) \n"
                                "Be extra careful if there are cables/pipes connected to sample! \n"
                                )
                self.log.info("Stage must be returned closer to start. Experiment aborted")
                self.abort()
                return True

    def begin_scans(self):
        if self.motor_control_group.motion_CT.is_moving or \
                    self.motor_control_group.motion_vert.is_moving:
            return
        self.total_experiment_time = time.time()
        self.doscan()

    def doscan(self):
        tmp = self.scan_controls_group.outer_steps - self.number_of_scans + 1
        self.scan_controls_group.setTitle("Experiment is running; doing scan {}".format(tmp))
        self.log.info("STARTING SCAN {:}".format(tmp))
        # before starting scan we have to create new experiment and update parameters
        # of acquisitions, flat-field correction, camera, consumers, etc based on the user input
        self.add_acquisitions_to_exp()
        self.concert_scan.start_scan()

    def end_of_scan(self):
        # in the end of scan next outer loop step is made if applicable
        self.number_of_scans -= 1
        if self.number_of_scans > 0:
            if self.scan_controls_group.outer_motor == 'Timer [sec]':
                self.log.info("DELAYING THE NEXT SCAN")
                self.scan_controls_group.setTitle("Experiment is running; delaying the next scan")
                self.scan_timer.singleShot((self.outer_region[1] - self.outer_region[0]) * 1000,
                                  self.doscan)
            else:
                self.log.info("MOVING TO THE NEXT OUTER MOTOR POINT")
                #get index of the next step
                tmp = self.scan_controls_group.outer_steps - self.number_of_scans
                #move motor to the next absolute position in the scan region
                self.motor_control_group.motion_vert = MotionThread(
                    self.motors[self.scan_controls_group.outer_motor],
                    self.outer_region[tmp])
                self.motor_control_group.motion_vert.start()
                self.motor_control_group.motion_vert.motion_over_signal.connect(self.doscan)
        else: # all scans done, finish the experiment
            # This section runs only if scan was finished normally, not aborted
            self.lv_timer_stop_func()
            self.log.info("***** EXPERIMENT finished without errors ****")
            # End of section
            self.scan_controls_group.setTitle(
                "Scan controls. Status: scans were finished without errors. \
                Total acquisition time {:} seconds".format(int(time.time() - self.total_experiment_time)))
            self.start_button.setEnabled(True)
            self.abort_button.setEnabled(False)
            self.ena_disa_all(True)
            self.concert_scan.delete_exp()
            if self.scan_controls_group.readout_intheend.isChecked():
                self.camera_controls_group.live_off_func()
            # return motors to starting position
            self.move_to_start(begin_exp=False)


    def return_to_start(self):
        self.move_to_start(begin_exp=False)

    def set_scan_params(self):
        self.log.info("Setting scan parameters")
        '''To be called before Experiment.run
           to set all parameters required for correct data acquisition'''
        problem_with_params = False
        # SET CAMERA PARAMETER
        if not self.camera_controls_group.ttl_scan.isChecked():
            problem_with_params = self.camera_controls_group.set_camera_params()
        # SET ACQUISITION PARAMETERS
        try:
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
            self.concert_scan.acq_setup.flats_before = self.scan_controls_group.ffc_before
            self.concert_scan.acq_setup.flats_after = self.scan_controls_group.ffc_after
            # SET shutter
            if self.shutter is None:
                self.concert_scan.ffc_setup.shutter = DummyShutter()
            else:
                self.concert_scan.ffc_setup.shutter = self.shutter
        except:
            self.log.error("Scan params defined incorrectly. Aborting")
            info_message("Select flat field motor and define parameters correctly")
            problem_with_params = True
        # SET FFC parameters
        if self.scan_controls_group.ffc_before or self.scan_controls_group.ffc_after or \
                self.scan_controls_group.ffc_before_outer or self.scan_controls_group.ffc_after_outer:
            try:
                self.concert_scan.ffc_setup.flat_motor = self.motors[self.ffc_controls_group.flat_motor]
                self.concert_scan.ffc_setup.radio_position = self.ffc_controls_group.radio_position * q.mm
                self.concert_scan.ffc_setup.flat_position = self.ffc_controls_group.flat_position * q.mm
                self.concert_scan.acq_setup.num_flats = self.ffc_controls_group.num_flats
                self.concert_scan.acq_setup.num_darks = self.ffc_controls_group.num_darks
            except:
                self.log.error("Flat-field params defined incorrectly. Aborting")
                error_message("Select flat field motor and define parameters correctly")
                problem_with_params = True
        if problem_with_params:
            self.abort()

    def create_exp(self):
        self.log.info("creating concert experiment")
        acquisitions = []
        #**********CREATE EXPERIMENT AND ATTACH CONSUMERS
        # CREATE NEW WALKER
        if self.file_writer_group.isChecked() and \
                not (self.camera_controls_group.ttl_scan.isChecked() or \
                    self.scan_controls_group.readout_intheend.isChecked()):
            bpf = 0
            if self.file_writer_group.bigtiff:
                bpf = 2**37
            self.concert_scan.walker = DirectoryWalker(root=self.file_writer_group.root_dir,
                                                       dsetname=self.file_writer_group.dsetname,
                                                       bytes_per_file=bpf)
        else:
            # if writer is disabled we do not need walker as well
            self.concert_scan.walker = None
        # create experiment
        self.concert_scan.create_experiment(acquisitions,
                                            self.file_writer_group.ctsetname,
                                            self.file_writer_group.separate_scans)
        if self.reco_settings_group.isChecked():
            try:
                self.reco_settings_group.set_args(
                    self.camera_controls_group.roi_height//2,
                    self.scan_controls_group.inner_steps,
                    self.scan_controls_group.inner_range
                )
            except:
                self.abort()
            self.concert_scan.args = self.reco_settings_group.args


    def add_acquisitions_to_exp(self):
        self.log.info("adding acqusitions to concert experiment")
        self.concert_scan.remove_all_acqs()
        # ttl scan - no consumers, only trigger to camera controlled externally
        if self.camera_controls_group.ttl_scan.isChecked() or \
                    self.scan_controls_group.readout_intheend.isChecked():
            if (self.scan_controls_group.outer_steps > 0 and \
                        self.number_of_scans == self.scan_controls_group.outer_steps and \
                            self.scan_controls_group.ffc_before_outer) or \
                                self.scan_controls_group.ffc_before:
                self.concert_scan.acq_setup.ttl_ffc_swi = 1
                self.concert_scan.exp.add(self.concert_scan.acq_setup.ttl_acq)
            elif (self.scan_controls_group.outer_steps > 0 and \
                    self.number_of_scans == 1 and \
                        self.scan_controls_group.ffc_after_outer) or \
                                self.scan_controls_group.ffc_after:
                self.concert_scan.acq_setup.ttl_ffc_swi = 2
                self.concert_scan.exp.add(self.concert_scan.acq_setup.ttl_acq)
            else:
                self.concert_scan.acq_setup.ttl_ffc_swi = 0
                self.concert_scan.exp.add(self.concert_scan.acq_setup.ttl_acq)
            return
        # ordinary concert experiments with yielding acquisitions and consumers
        # ffc before
        if self.scan_controls_group.ffc_before or \
                (self.scan_controls_group.ffc_before_outer and \
                    self.number_of_scans == self.scan_controls_group.outer_steps):
            self.concert_scan.exp.add(self.concert_scan.acq_setup.flats_softr)
            if self.ffc_controls_group.num_darks > 0:
                self.concert_scan.exp.add(self.concert_scan.acq_setup.darks_softr)
        # projections
        if self.camera_controls_group.trig_mode == "EXTERNAL":
            if self.camera_controls_group.camera_model_label.text() == "PCO Dimax":
                self.concert_scan.exp.add(self.concert_scan.acq_setup.tomo_ext_dimax)
            elif self.camera_controls_group.camera_model_label.text() == "PCO Edge":
                self.concert_scan.exp.add(self.concert_scan.acq_setup.tomo_ext)
        elif self.camera_controls_group.trig_mode == "AUTO": #make option avaliable only when connected to DIMAX
            if self.camera_controls_group.camera_model_label.text() == "PCO Dimax":
                self.concert_scan.exp.add(self.concert_scan.acq_setup.tomo_auto_dimax)
            elif self.camera_controls_group.camera_model_label.text() == "PCO Edge":
                self.concert_scan.exp.add(self.concert_scan.acq_setup.tomo_auto)
        else: #trig_mode is SOFTWARE and motion is always step-wise
            if self.scan_controls_group.inner_motor == "Timer [sec]":
                self.concert_scan.exp.add(self.concert_scan.acq_setup.radio_timelaps)
            else:
                self.concert_scan.exp.add(self.concert_scan.acq_setup.tomo_softr)
        # ffc after
        if self.scan_controls_group.ffc_after or \
                (self.scan_controls_group.ffc_after_outer and \
                    self.number_of_scans == 1):
            self.concert_scan.exp.add(self.concert_scan.acq_setup.flats2_softr)

        # ATTACH CONSUMERS
        if self.file_writer_group.isChecked():
            self.concert_scan.attach_writer()
        #if not self.reco_enabled:
        #    self.concert_scan.attach_viewer()
        #else:
        self.concert_scan.attach_viewer()
        if self.reco_settings_group.isChecked():
            self.log.info("Attaching online reco add on")
            self.concert_scan.attach_online_reco()

    def abort(self):
        self.number_of_scans = 0
        self.scan_timer.stop()
        self.lv_timer_stop_func()
        self.concert_scan.abort_scan()
        self.motor_control_group.stop_motors_func()
        self.motor_control_group.close_shutter_func()
        time.sleep(1)
        if self.camera_controls_group.camera.state == 'recording':
            self.camera_controls_group.camera.stop_recording()
        # to stop libuca errors in case if pcoclhs + ext trig + buff
        if self.camera_controls_group.trig_mode == 'EXTERNAL' and \
                self.camera_controls_group.camera_model_label.text() == 'PCO Edge':
            self.log.debug("Workaround for libuca problem")
            try:
                self.concert_scan.acq_setup.motor.PSO_ttl(10, 0.05).join()
            except:
                pass
            self.camera_controls_group.live_on_func()
            self.camera_controls_group.live_off_func()
        # finished workaround for libuca error spam
        # plus to clear all possible fault states on CT stage
        try:
            self.concert_scan.acq_setup.motor.clear()
        except:
            pass
        self.start_button.setEnabled(True)
        self.abort_button.setEnabled(False)
        self.return_button.setEnabled(True)
        self.scan_controls_group.setTitle(
            "Scan controls. Status: scan was aborted")
        self.ena_disa_all(True)

    # EXECUTION CONTROL
    def check_scan_status(self):
        if self.f.done():
            self.end_of_scan()

    def set_viewer_limits(self):
        self.camera_controls_group.viewer.limits = \
            [self.camera_controls_group.view_low,
             self.camera_controls_group.view_high]
        self.viewer_lowlim_entry.setText(str(self.camera_controls_group.view_low))
        self.viewer_highlim_entry.setText(str(self.camera_controls_group.view_high))

    @property
    def view_low(self):
        try:
            return float(self.viewer_lowlim_entry.text())
        except:
            self.viewer_lowlim_entry.setText('0')
            error_message('Viewer limits must be numbers')
            return 0

    @property
    def view_high(self):
        try:
            return float(self.viewer_highlim_entry.text())
        except:
            self.viewer_highlim_entry.setText('150')
            error_message('Viewer limits must be numbers')
            return 150

    def set_viewer_limits_alt(self):
        self.camera_controls_group.viewer.limits = \
            [self.view_low, self.view_high]
        self.camera_controls_group.viewer_lowlim_entry.setText(str(self.view_low))
        self.camera_controls_group.viewer_highlim_entry.setText(str(self.view_high))

    def autoset_n_buffers(self):
        if self.camera_controls_group.buffered_entry.currentText() == "YES" and \
                (self.camera_controls_group.trigger_entry.currentText() == 'EXTERNAL' or \
                self.camera_controls_group.trigger_entry.currentText() == 'AUTO'):
            self.camera_controls_group.n_buffers_entry.setText(\
                "{:}".format(self.scan_controls_group.inner_loop_steps_entry.text()))

    def autoset_some_params_for_CTstage_motor(self):
        if self.scan_controls_group.inner_loop_motor.currentText() != 'CT stage [deg]':
            self.scan_controls_group.inner_loop_continuous.setChecked(False)
            self.scan_controls_group.inner_loop_start_entry.setDisabled(False)
        else:
            self.scan_controls_group.inner_loop_continuous.setChecked(True)
            if self.camera_controls_group.trig_mode == "EXTERNAL":
                self.scan_controls_group.inner_loop_start_entry.setText('0.0')
                self.scan_controls_group.inner_loop_start_entry.setDisabled(True)

    def enable_TTL_scan_if_Dimax_and_Ext_trig(self):
        if self.camera_controls_group.trig_mode == "EXTERNAL" and \
                self.camera_controls_group.camera_model_label.text() == "PCO Dimax":
            self.scan_controls_group.readout_intheend.setEnabled(True)
        else:
            self.scan_controls_group.readout_intheend.setEnabled(False)
            self.scan_controls_group.readout_intheend.setChecked(False)


    def validate_velocity(self):
        #taken from concert/imaging.py by T. Farago
        # every pixel of the frame rotates no more than one pixel per rotation step
        tomo_ang_step = np.arctan(2.0 / self.camera_controls_group.roi_width)
        #minimum number of projections in order to provide enough
        #data points for every distance from the axis of rotation
        tomo_proj_num = int(np.ceil(np.pi / tomo_ang_step))
        # speed at which motion blur will exceed one pixel
        tomo_max_rot_velo = tomo_ang_step * self.camera_controls_group.fps
        velocity = self.scan_controls_group.inner_range / \
            (self.scan_controls_group.inner_steps / self.camera_controls_group.fps)
        if velocity > tomo_max_rot_velo:
            warning_message("Rotation speed is too large for this ROI width.\n"
                            "Consider increasing exposure time or num of projections to avoid blurring.\n"
                            "Experiment will continue.")

    def enable_sync_daq_ring(self):
        self.concert_scan.acq_setup.top_up_veto_enabled = self.ring_status_group.sync_daq_inj.isChecked()

    def send_inj_info_to_acqsetup(self, value):
        self.concert_scan.acq_setup.top_up_veto_state = value

    def select_log_file_func(self):
        f, fext = self.QFD.getSaveFileName(
            self, 'Select file', self.file_writer_group.root_dir, "log files (*.log)")
        if f == '':
            warning_message('Select file')
            return

        # use logging from EDC
        self._log.log_to_file(f+'.log', logging.DEBUG)
        self.log = self._log.get_module_logger(__name__)

        return

    def auto_set_buffers_ext_edge(self):
        if self.camera_controls_group.trig_mode == "EXTERNAL" and \
                self.camera_controls_group.camera_model == "PCO Edge":
            self.camera_controls_group.n_buffers_entry.setText(
                str(self.scan_controls_group.inner_steps))

    def dump2yaml(self):

        f, fext = self.QFD.getSaveFileName(
            self, 'Select file', self.file_writer_group.root_dir, "YAML files (*.yaml)")
        if f == '':
            warning_message('Select file')
            return
        params ={"Camera":
                    {'Model': self.camera_controls_group.camera_model_label.text(),
                     'External camera': self.camera_controls_group.ttl_scan.isChecked(),
                     'Exposure time': self.camera_controls_group.exp_time,
                     'Dead time': self.camera_controls_group.dead_time,
                     'FPS': self.camera_controls_group.fps,
                     'ROI first row': self.camera_controls_group.roi_x0,
                     'ROI width': self.camera_controls_group.roi_width,
                     'ROI first column': self.camera_controls_group.roi_y0,
                     'ROI height': self.camera_controls_group.roi_height,
                     'Buffered': self.camera_controls_group.buffered_entry.currentText(),
                     'Number of buffers': self.camera_controls_group.buffnum,
                     'Trigger': self.camera_controls_group.trig_mode,
                     'Sensor clocking': self.camera_controls_group.sensor_pix_rate_entry.currentText(),
                     'Time stamp': self.camera_controls_group.time_stamp.isChecked()},
                 "Positions":
                     {'CT stage': self.motor_control_group.CT_mot_pos_move.value(),
                      'Vertical': self.motor_control_group.vert_mot_pos_move.value(),
                      'Horizontal': self.motor_control_group.hor_mot_pos_move.value()},
                 "Outer loop":
                  {'Motor': self.scan_controls_group.outer_loop_motor.currentText(),
                   'Start': self.scan_controls_group.outer_loop_start_entry.text(),
                   'Steps': self.scan_controls_group.outer_loop_steps_entry.text(),
                   'Range': self.scan_controls_group.outer_loop_range_entry.text(),
                   'Flats before': self.scan_controls_group.ffc_before_outer,
                   'Flats after': self.scan_controls_group.ffc_after_outer},
                 "Inner loop":
                     {'Motor': self.scan_controls_group.inner_loop_motor.currentText(),
                      'Start': self.scan_controls_group.inner_loop_start_entry.text(),
                      'Steps': self.scan_controls_group.inner_loop_steps_entry.text(),
                      'Range': self.scan_controls_group.inner_loop_range_entry.text(),
                      'Flats before': self.scan_controls_group.ffc_before,
                      'Flats after': self.scan_controls_group.ffc_after},
                 "Readout in the end":
                     {'Readout in the end': self.scan_controls_group.readout_intheend.isChecked()},
                 "FFC":
                     {'Motor': self.ffc_controls_group.flat_motor,
                      'Radio position': self.ffc_controls_group.radio_position_entry.text(),
                      'Flat position': self.ffc_controls_group.flat_position_entry.text(),
                      'Num flats': self.ffc_controls_group.num_flats,
                      'Num darks': self.ffc_controls_group.num_darks},
                 "Writer":
                  {'Enabled': self.file_writer_group.isChecked(),
                   'Data dir': self.file_writer_group.root_dir,
                   'CT scan name': self.file_writer_group.ctsetname,
                   'Filename': self.file_writer_group.dsetname,
                   'Big tiffs': self.file_writer_group.bigtiff,
                   'Separate scans': self.file_writer_group.separate_scans}
            }

        def my_unicode_repr(data):
            return self.represent_str(data.encode('utf-8'))

        yaml.representer.Representer.add_representer(unicode, my_unicode_repr)

        with open(f+'.yaml', 'w') as f:
            yaml.safe_dump(params, f, allow_unicode=True, default_flow_style=False)

    def load_from_yaml(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select yaml file with BMITgui params",
                                               self.file_writer_group.root_dir,
                                               "Yaml Files (*.yaml)")

        if fname == '':
            warning_message('Select the file')
            return

        with open(fname) as f:
            p = yaml.load(f, Loader=yaml.FullLoader)

        if p['Camera']['Model'] != self.camera_controls_group.camera_model_label.text():
            error_message('Selected params file is for different camera')
            return

        try: ####### CAMERA  #######
            self.camera_controls_group.ttl_scan.setChecked(p['Camera']['External camera'])
            self.camera_controls_group.exposure_entry.setText(str(p['Camera']['Exposure time']))
            self.camera_controls_group.fps_entry.setText(str(p['Camera']['FPS']))
            self.camera_controls_group.roi_y0_entry.setText(str(p['Camera']['ROI first column']))
            self.camera_controls_group.roi_width_entry.setText(str(p['Camera']['ROI width']))
            self.camera_controls_group.roi_x0_entry.setText(str(p['Camera']['ROI first row']))
            self.camera_controls_group.roi_height_entry.setText(str(p['Camera']['ROI height']))
            tmp = self.camera_controls_group.buffered_entry.findText(str(p['Camera']['Buffered']))
            self.camera_controls_group.buffered_entry.setCurrentIndex(tmp)
            self.camera_controls_group.n_buffers_entry.setText(str(p['Camera']['Number of buffers']))
            tmp = self.camera_controls_group.trigger_entry.findText(p['Camera']['Trigger'])
            self.camera_controls_group.delay_entry.setText(str(p['Camera']['Dead time']))
            self.camera_controls_group.trigger_entry.setCurrentIndex(tmp)
            tmp = self.camera_controls_group.sensor_pix_rate_entry.\
                findText(p['Camera']['Sensor clocking'])
            self.camera_controls_group.sensor_pix_rate_entry.setCurrentIndex(tmp)
            self.camera_controls_group.time_stamp.setChecked(p['Camera']['Time stamp'])
        except:
            warning_message('Cannot enter all camera parameters correctly')
        try: ####### Scans' settings #######
            tmp = self.scan_controls_group.outer_loop_motor.\
                findText(p['Outer loop']['Motor'])
            self.scan_controls_group.outer_loop_motor.setCurrentIndex(tmp)
            self.scan_controls_group.outer_loop_start_entry.setText(str(p['Outer loop']['Start']))
            self.scan_controls_group.outer_loop_steps_entry.setText(str(p['Outer loop']['Steps']))
            self.scan_controls_group.outer_loop_range_entry.setText(str(p['Outer loop']['Range']))
            self.scan_controls_group.outer_loop_flats_0.setChecked(p['Outer loop']['Flats before'])
            self.scan_controls_group.outer_loop_flats_1.setChecked(p['Outer loop']['Flats after'])
            tmp = self.scan_controls_group.inner_loop_motor. \
                findText(p['Inner loop']['Motor'])
            self.scan_controls_group.inner_loop_motor.setCurrentIndex(tmp)
            self.scan_controls_group.inner_loop_start_entry.setText(str(p['Inner loop']['Start']))
            self.scan_controls_group.inner_loop_steps_entry.setText(str(p['Inner loop']['Steps']))
            self.scan_controls_group.inner_loop_range_entry.setText(str(p['Inner loop']['Range']))
            self.scan_controls_group.inner_loop_flats_0.setChecked(p['Inner loop']['Flats before'])
            self.scan_controls_group.inner_loop_flats_1.setChecked(p['Inner loop']['Flats after'])
            self.scan_controls_group.readout_intheend.setChecked(p['Readout in the end']['Readout in the end'])
        except:
            warning_message('Cannot enter scan parameters correctly')
        try:  ####### FFC settings #######
            tmp = self.ffc_controls_group.motor_options_entry.findText(p['FFC']['Motor'])
            self.ffc_controls_group.motor_options_entry.setCurrentIndex(tmp)
            self.ffc_controls_group.radio_position_entry.setText(p['FFC']['Radio position'])
            self.ffc_controls_group.flat_position_entry.setText(p['FFC']['Flat position'])
            self.ffc_controls_group.numflats_entry.setText(str(p['FFC']['Num flats']))
            self.ffc_controls_group.numdarks_entry.setText(str(p['FFC']['Num darks']))
        except:
            warning_message('Cannot enter flat-field parameters correctly')
        try:  ##### FILE WRITER ########
            self.file_writer_group.setChecked(p['Writer']['Enabled'])
            self.file_writer_group.root_dir_entry.setText(p['Writer']['Data dir'])
            self.file_writer_group.ctset_fmt_entry.setText(p['Writer']['CT scan name'])
            self.file_writer_group.dsetname_entry.setText(p['Writer']['Filename'])
            self.file_writer_group.bigtiff_checkbox.setChecked(p['Writer']['Big tiffs'])
            self.file_writer_group.separate_scans_checkbox.setChecked(p['Writer']['Separate scans'])
        except:
            warning_message('Cannot enter file-writer settings correctly')

if __name__ == '__main__':
    parsed_args, unparsed_args = process_cl_args()
    if parsed_args.debug:
        log.log_to_console(level=logging.DEBUG)
    # QApplication expects the first argument to be the program name.
    qt_args = sys.argv[:1] + unparsed_args
    app = QApplication(qt_args)
    loop = QEventLoop(app)
    root_dir = os.path.dirname(os.path.abspath(__file__))
    style_file = QFile(os.path.join(root_dir, "styles/breeze/dark.qss"))
    style_file.open(QFile.ReadOnly | QFile.Text)
    stream = QTextStream(style_file)
    # Set application style to dark; Comment following line to unset
    # app.setStyleSheet(stream.readAll())
    ex = GUI()
    sys.exit(app.exec_())
