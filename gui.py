import os
# PyQT imports
from PyQt5.QtWidgets import QGroupBox, QDialog, QApplication, QGridLayout
from PyQt5.QtWidgets import QLabel, QPushButton, QFileDialog, QHBoxLayout
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
from concert.devices.shutters.dummy import Shutter as DummyShutter
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
import yaml
import time
import argparse
# Dark style
# noinspection PyUnresolvedReferences
from styles.breeze import styles_breeze
from edc import log
concert.require("0.11.0")

# use logging from EDC
log.log_to_file("ezconcert.log", logging.DEBUG)
LOG = log.get_module_logger(__name__)


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
        self.shutter = None


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
        self.scan_controls_group.inner_loop_steps_entry.editingFinished.connect(
            self.autoset_n_buffers)
        # populate motors dictionary when physical device is connected
        self.motor_control_group.connect_hor_mot_button.clicked.connect(self.add_mot_hor)
        self.motor_control_group.connect_vert_mot_button.clicked.connect(self.add_mot_vert)
        self.motor_control_group.connect_CT_mot_button.clicked.connect(self.add_mot_CT)
        self.motor_control_group.connect_shutter_button.clicked.connect(self.add_mot_sh)
        # add motors automatically on start
        # self.motor_control_group.connect_hor_motor_func()
        # self.motor_control_group.connect_CT_motor_func()
        # self.motor_control_group.connect_vert_motor_func()
        # self.motor_control_group.connect_shutter_func()

        self.QFD = QFileDialog()
        self.exp_imp_button_grp = QGroupBox(title='Save/load params')
        self.button_save_params = QPushButton("Export settings and params to file")
        self.button_load_params = QPushButton("Read settings and params from file")
        self.button_save_params.clicked.connect(self.dump2yaml)
        self.button_load_params.clicked.connect(self.load_from_yaml)
        button_grp_layout = QHBoxLayout()
        button_grp_layout.addWidget(self.button_save_params)
        button_grp_layout.addWidget(self.button_load_params)
        self.exp_imp_button_grp.setLayout(button_grp_layout)
        self.exp_imp_button_grp.setEnabled(False)

        # finally
        self.set_layout()
        self.show()
        LOG.info("Start gui.py")




    def set_layout(self):
        main_layout = QGridLayout()
        main_layout.addWidget(self.camera_controls_group)
        main_layout.addWidget(self.exp_imp_button_grp)
        main_layout.addWidget(self.motor_control_group)
        main_layout.addWidget(self.scan_controls_group)
        main_layout.addWidget(self.ffc_controls_group)
        main_layout.addWidget(self.file_writer_group)
        # main_layout.addWidget(self.reco_settings_group)
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

    def enable_sync_daq_ring(self):
        self.concert_scan.acq_setup.top_up_veto_enabled = self.ring_status_group.sync_daq_inj.isChecked()

    def send_inj_info_to_acqsetup(self, value):
        self.concert_scan.acq_setup.top_up_veto_state = value

    def on_camera_connected(self, camera):
        self.concert_scan = ConcertScanThread(self.viewer, camera)
        self.concert_scan.scan_finished_signal.connect(self.end_of_scan)
        self.concert_scan.start()
        self.scan_controls_group.setEnabled(True)
        self.ffc_controls_group.setEnabled(True)
        self.file_writer_group.setEnabled(True)
        self.exp_imp_button_grp.setEnabled(True)
        self.ring_status_group.status_monitor.i0_state_changed_signal2.connect(
            self.send_inj_info_to_acqsetup)
        self.ring_status_group.sync_daq_inj.stateChanged.connect(self.enable_sync_daq_ring)


    def ena_disa_all(self, val=True):
        self.motor_control_group.setEnabled(val)
        self.camera_controls_group.setEnabled(val)
        self.ffc_controls_group.setEnabled(val)
        self.file_writer_group.setEnabled(val)
        self.ring_status_group.setEnabled(val)
        self.exp_imp_button_grp.setEnabled(val)



    def start(self):
        LOG.info("Experiment started")
        self.ena_disa_all(False)
        self.number_of_scans = 1 # we expect to make at least one scan
        self.start_button.setEnabled(False)
        self.abort_button.setEnabled(True)
        self.return_button.setEnabled(False)
        self.scan_controls_group.setTitle("Scan controls. Status: Experiment is running")
        self.move_inner_mot2starting_point()
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
        # in the end of scan next outer loop step is made if applicable
        self.number_of_scans -= 1
        if self.number_of_scans > 0:
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
        # return motors to starting position
        if self.scan_controls_group.inner_motor != 'Timer [sec]':
            self.motors[self.scan_controls_group.inner_motor]['position']. \
                set(self.scan_controls_group.inner_start * self.concert_scan.acq_setup.units).join()
        if self.scan_controls_group.outer_steps > 0 and \
                self.scan_controls_group.outer_motor != 'Timer [sec]':
            self.motors[self.scan_controls_group.outer_motor]['position']. \
                set(self.outer_region[0] * self.outer_unit).join()
        # End of section
        self.scan_controls_group.setTitle(
            "Scan controls. Status: scans were finished without errors. \
            Total acquisition time {:} seconds".format(int(time.time() - self.total_experiment_time)))
        self.start_button.setEnabled(True)
        self.abort_button.setEnabled(False)
        self.ena_disa_all(True)

    def move_inner_mot2starting_point(self):
        # insert check large discrepancy
        LOG.info("Moving inner motor to starting point")
        self.motors[self.scan_controls_group.inner_motor]
        if self.scan_controls_group.inner_motor == 'CT stage [deg]':
            self.motors[self.scan_controls_group.inner_motor]["stepvelocity"]\
                .set(5.0 * q.deg / q.sec).join()
            time.sleep(0.2)
            self.motors[self.scan_controls_group.inner_motor]["position"].\
                set(self.scan_controls_group.inner_start * q.deg).join()

    def set_scan_params(self):
        '''To be called before Experiment.run
           We create new instance of Concert Experiment and set all
           parameters required for correct data acquisition'''
        # SET CAMERA PARAMETER
        if not self.camera_controls_group.ttl_scan.isChecked():
            self.camera_controls_group.set_camera_params()
        # SET ACQUISITION PARAMETERS
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
        # SET FFC parameters
        if self.scan_controls_group.ffc_before or self.scan_controls_group.ffc_after or \
                self.scan_controls_group.ffc_before_outer or self.scan_controls_group.ffc_after_outer:
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
        if self.scan_controls_group.ffc_before or \
                (self.scan_controls_group.ffc_before_outer and \
                    self.number_of_scans == self.scan_controls_group.outer_steps):
            acquisitions.append(self.concert_scan.acq_setup.flats_softr)
            if self.ffc_controls_group.num_darks > 0:
                acquisitions.append(self.concert_scan.acq_setup.darks_softr)
        # projections
        if self.camera_controls_group.trig_mode == "EXTERNAL":
            if self.camera_controls_group.camera_model_label.text() == "PCO Dimax":
                acquisitions.append(self.concert_scan.acq_setup.tomo_ext_dimax)
            elif self.camera_controls_group.camera_model_label.text() == "PCO Edge":
                acquisitions.append(self.concert_scan.acq_setup.tomo_ext)
        elif self.camera_controls_group.trig_mode == "AUTO": #make option avaliable only when connected to DIMAX
            if self.camera_controls_group.camera_model_label.text() == "PCO Dimax":
                acquisitions.append(self.concert_scan.acq_setup.tomo_auto_dimax)
            elif self.camera_controls_group.camera_model_label.text() == "PCO Edge":
                acquisitions.append(self.concert_scan.acq_setup.tomo_auto)
        else: #trig_mode is SOFTWARE and rotation is step-wise
            acquisitions.append(self.concert_scan.acq_setup.tomo_softr)
        # ffc after
        if self.scan_controls_group.ffc_after or \
                (self.scan_controls_group.ffc_after_outer and \
                    self.number_of_scans == 1):
            acquisitions.append(self.concert_scan.acq_setup.flats2_softr)

        # special case when ttl scan is used
        if self.camera_controls_group.ttl_scan.isChecked():
            acquisitions = []
            acquisitions.append(self.concert_scan.acq_setup.ttl_acq)

        # CREATE NEW WALKER
        if self.file_writer_group.isChecked():
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
        # ATTACH CONSUMERS
        # (they will be detached and deleted in the end of each scan inside the Concert Thread)
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
        self.ena_disa_all(True)

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

    def autoset_n_buffers(self):
        if self.camera_controls_group.buffered_entry.currentText() == "True" and \
                (self.self.camera_controls_group.trigger_entry.currentText() == 'EXTERNAL' or \
                self.camera_controls_group.trigger_entry.currentText() == 'AUTO'):
            self.camera_controls_group.n_buffers_entry.setText(\
                "{:}".format(self.scan_controls_group.inner_loop_steps_entry.text()))


    def validate_velocity(self):
        velocitymax = tomo_max_speed(self.setup.camera.roi_width,
                                  self.setup.camera.frame_rate)
        velocity = self.scan_controls_group.inner_range * q.deg / (self.scan_controls_group.inner_loop_steps_entry
                                  / self.camera_controls_group.fps)
        if velocity > velocitymax:
            warning_message("Rotation speed is too large for this sensor width. \
                            Reduce fps or increase exposure time \
                            to avoid blurring.")


    def dump2yaml(self):

        f, fext = self.QFD.getSaveFileName(
            self, 'Select file', self.file_writer_group.root_dir, "YAML files (*.yaml)")
        if f == '':
            return

        params ={"Camera":
                    {'Model': self.camera_controls_group.camera_model_label.text(),
                   'Trigger': self.camera_controls_group.trigger_entry.currentText()},\
                 "Outer loop":
                  {'Motor': self.scan_controls_group.outer_loop_motor.currentText()},
                 "Writer":
                  {'Data dir': self.file_writer_group.root_dir_entry.text()}}

        def my_unicode_repr(data):
            return self.represent_str(data.encode('utf-8'))

        yaml.representer.Representer.add_representer(unicode, my_unicode_repr)

        with open(f+'.yaml', 'w') as f:
            yaml.safe_dump(params, f, allow_unicode=True, default_flow_style=False)

    def load_from_yaml(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select yaml file with BMITgui params",
                                               self.file_writer_group.root_dir,
                                               "Python Files (*.yaml)")

        with open(fname) as f:
            p = yaml.load(f, Loader=yaml.FullLoader)

        if p['Camera']['Model'] != self.camera_controls_group.camera_model_label.text():
            error_message('Param file is for different camera')
            return

        try: ####### CAMERA  #######
            tmp = self.camera_controls_group.trigger_entry.findText(p['Camera']['Trigger'])
            self.camera_controls_group.trigger_entry.setCurrentIndex(tmp)
        except:
            warning_message('Cannot set all camera parameters correctly')

        ###### FILE WRITER ########
        self.file_writer_group.root_dir_entry.setText(p['Writer']['Data dir'])



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
