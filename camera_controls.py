import atexit
from random import choice
import time

from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject, QTimer
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, \
    QPushButton, QComboBox, QFileDialog, QCheckBox

from message_dialog import info_message, error_message, warning_message

from concert.devices.cameras.uca import Camera as UcaCamera
from concert.devices.cameras.dummy import Camera as DummyCamera
from concert.quantities import q
import os.path as osp
from matplotlib import pyplot as plt
from concert.devices.cameras.base import CameraError
from concert.storage import write_tiff
from concert.writers import TiffWriter
from time import sleep
import os

class CameraControlsGroup(QGroupBox):
    """
    Camera controls
    """
    camera_connected_signal = pyqtSignal(object)

    def __init__(self, viewer, *args, **kwargs):
        # Timer - just as example
        super(CameraControlsGroup, self).__init__(*args, **kwargs)
        self.timer = QTimer()
        self.camera = None

        # Buttons
        self.live_on_button = QPushButton("LIVE ON")
        self.live_on_button.clicked.connect(self.live_on_func)
        self.live_on_button.setEnabled(False)
        self.lv_duration = 0.0
        self.frames_in_last_lv_seq = 0

        self.live_off_button = QPushButton("LIVE OFF")
        self.live_off_button.setEnabled(False)
        self.live_off_button.clicked.connect(self.live_off_func)
        self.live_off_button.setEnabled(False)

        self.save_lv_sequence_button = QPushButton("SAVE live-view sequence")
        self.save_lv_sequence_button.clicked.connect(self.save_lv_seq)
        self.save_lv_sequence_button.setEnabled(False)
        self.frames_grabbed_so_far = 0

        self.abort_transfer_button = QPushButton("Abort transfer")
        self.abort_transfer_button.clicked.connect(self.abort_transfer_func)
        self.abort_transfer_button.setEnabled(False)
        self.abort_transfer = True

        self.lv_session_info = QLabel()

        #self.buffer_livev

        self.save_one_image_button = QPushButton("SAVE 1 image")
        self.save_one_image_button.clicked.connect(self.save_one_image)
        self.save_one_image_button.setEnabled(False)
        self.QFD = QFileDialog()
        self.nim = 0
        self.last_dir = "/data/image-"

        # Connect to camera
        self.connect_to_camera_button = QPushButton("Connect to camera")
        self.connect_to_camera_button.clicked.connect(self.connect_to_camera)
        self.connect_to_dummy_camera_button = QPushButton("Connect to dummy camera")
        self.connect_to_dummy_camera_button.clicked.connect(
            self.connect_to_dummy_camera)
        self.connect_to_camera_status = QLabel()
        self.connect_to_camera_status.setText("NOT CONNECTED")
        self.connect_to_camera_status.setStyleSheet("color: red")
        self.camera_model_label = QLabel()
        # Camera object
        self.camera = None
        self.viewer = viewer
        self.live_on = False

        # external camera software switch
        self.ttl_scan = QCheckBox("External camera controls")
        self.ttl_scan.setChecked(False)
        self.ttl_scan.clicked.connect(self.extcamera_switched_func)

        # EXPOSURE
        self.exposure_label = QLabel()
        self.exposure_label.setText("EXPOSURE [msec]")
        self.exposure_entry = QLineEdit()
        self.exposure_units = QLabel()
        self.exposure_units.setText("msec")
        self.exposure_entry.editingFinished.connect(self.relate_fps_to_exptime)

        # FPS
        self.fps_label = QLabel()
        self.fps_label.setText("FRAMES PER SECOND")
        self.fps_entry = QLineEdit()

        # DELAY
        self.delay_label = QLabel()
        self.delay_label.setText("Dead time [msec]")
        self.delay_entry = QLineEdit()
        self.delay_entry.setText("10")
        self.delay_units = QLabel()
        self.delay_units.setText("msec")

        # viewer limits
        self.viewer_lowlim_label = QLabel()
        self.viewer_lowlim_label.setText("Viewer low limit")
        self.viewer_lowlim_entry = QLineEdit()
        self.viewer_lowlim_entry.setText("20")
        self.viewer_highlim_label = QLabel()
        self.viewer_highlim_label.setText("Viewer high limit")
        self.viewer_highlim_entry = QLineEdit()
        self.viewer_highlim_entry.setText("120")

        # ROI
        # y0
        self.roi_y0_label = QLabel()
        self.roi_y0_label.setText("ROI first line")
        self.roi_y0_entry = QLineEdit()
        # height
        self.roi_height_label = QLabel()
        self.roi_height_label.setText("ROI height, lines")
        self.roi_height_entry = QLineEdit()
        # x0
        self.roi_x0_label = QLabel()
        self.roi_x0_label.setText("ROI first column")
        self.roi_x0_entry = QLineEdit()

        # width
        self.roi_width_label = QLabel()
        self.roi_width_label.setText("ROI width, columns")
        self.roi_width_entry = QLineEdit()
        # sensor_vertical_binning
        self.sensor_ver_bin_label = QLabel()
        self.sensor_ver_bin_label.setText("Vertical binning")
        self.sensor_ver_bin_entry = QLineEdit()
        self.sensor_ver_bin_entry.setText("1")
        # sensor_horizontal_binning
        self.sensor_hor_bin_label = QLabel()
        self.sensor_hor_bin_label.setText("Horizontal binning")
        self.sensor_hor_bin_entry = QLineEdit()
        self.sensor_hor_bin_entry.setText("1")

        # BUFFERED
        self.buffered_label = QLabel()
        self.buffered_label.setText("BUFFERED")
        self.buffered_entry = QComboBox()
        self.buffered_entry.addItems(["NO", "YES"])

        # N BUFFERS
        self.n_buffers_label = QLabel()
        self.n_buffers_label.setText("N BUFFERS")
        self.n_buffers_entry = QLineEdit()
        self.n_buffers_entry.setText("0")

        # TRIGGER
        self.trigger_label = QLabel()
        self.trigger_label.setText("TRIGGER")
        self.trigger_entry = QComboBox()
        self.trigger_entry.addItems(["AUTO", "SOFTWARE", "EXTERNAL"])

        # ACQUISITION MODE
        self.acq_mode_label = QLabel()
        self.acq_mode_label.setText("ACQUISITION MODE")
        self.acq_mode_entry = QComboBox()
        self.acq_mode_entry.addItems(["AUTO", "EXTERNAL"])
        self.acq_mode_entry.setEnabled(False)

        # STORAGE_MODE
        self.storage_mode_label = QLabel()
        self.storage_mode_label.setText("STORAGE MODE")
        self.storage_mode_entry = QComboBox()
        self.storage_mode_entry.addItems(["RECORDER", "FIFO"])
        #camera.storage_mode = camera.uca.enum_values.storage_mode.UCA_PCO_CAMERA_STORAGE_MODE_RECORDER
        #camera.storage_mode = camera.uca.enum_values.storage_mode.RECORDER
        #camera.storage_mode = camera.uca.enum_values.storage_mode.UCA_PCO_CAMERA_STORAGE_MODE_FIFO_BUFFER

        # RECORD MODE
        self.rec_mode_label = QLabel()
        self.rec_mode_label.setText("RECORD MODE")
        self.rec_mode_entry = QComboBox()
        self.rec_mode_entry.addItems(["RING BUFFER", "SEQUENCE"])

        # PIXELRATE line 6
        self.sensor_pix_rate_label = QLabel()
        self.sensor_pix_rate_label.setText("SENSOR PIXEL RATE, Hz")
        self.sensor_pix_rate_entry = QComboBox()

        # TIMESTAMP
        self.time_stamp = QCheckBox("Add timestamp to camera frames")
        self.time_stamp.setChecked(False)

        # Thread for live preview
        self.live_preview_thread = LivePreviewThread(
            viewer=self.viewer, camera=self.camera)
        self.live_preview_thread.start()

        # Thread for live preview
        self.readout_thread = ReadoutThread(camera=self.camera)
        self.readout_thread.start()

        # signals
        self.delay_entry.editingFinished.connect(self.relate_fps_to_exptime)
        self.exposure_entry.editingFinished.connect(self.relate_fps_to_exptime)
        self.readout_thread.readout_over_signal.connect(self.readout_over_func)
        self.time_stamp.stateChanged.connect(self.set_time_stamp)
        self.trigger_entry.currentIndexChanged.connect(self.restrict_params_depending_on_trigger)

        self.all_cam_params_correct = True
        self.set_layout()

    def constrain_buf_by_trig(self):
        if self.trigger_entry.currentText() == 'AUTO':
            tmp = self.buffered_entry.findText("NO")
            self.buffered_entry.setCurrentIndex(tmp)
        if self.trigger_entry.currentText() == 'SOFTWARE':
            tmp = self.buffered_entry.findText("NO")
            self.buffered_entry.setCurrentIndex(tmp)
            self.buffered_entry.setEnabled(False)
        if self.trigger_entry.currentText() == 'EXTERNAL':
            tmp = self.buffered_entry.findText("YES")
            self.buffered_entry.setCurrentIndex(tmp)
            self.buffered_entry.setEnabled(False)

    def set_layout(self):
        layout = QGridLayout()
        # Buttons on top
        layout.addWidget(self.live_on_button, 0, 0, 1, 2)
        layout.addWidget(self.live_off_button, 0, 2, 1, 2)
        layout.addWidget(self.save_one_image_button, 0, 4, 1, 2)

        # Left column of controls
        layout.addWidget(self.connect_to_camera_button, 1, 0)
        layout.addWidget(self.connect_to_camera_status, 1, 1)
        #layout.addWidget(self.camera_model_label, 1, 2)
        layout.addWidget(self.connect_to_dummy_camera_button, 1, 2)
        layout.addWidget(self.ttl_scan, 1, 3)
        layout.addWidget(self.save_lv_sequence_button, 1, 4)
        layout.addWidget(self.abort_transfer_button, 1, 5)

        # viewer clims
        layout.addWidget(self.viewer_lowlim_label, 2, 0)
        layout.addWidget(self.viewer_lowlim_entry, 2, 1)
        layout.addWidget(self.viewer_highlim_label, 2, 2)
        layout.addWidget(self.viewer_highlim_entry, 2, 3)

        layout.addWidget(self.exposure_label, 3, 0)
        layout.addWidget(self.exposure_entry, 3, 1)
        #layout.addWidget(self.exposure_units, 2, 2)

        layout.addWidget(self.fps_label, 3, 2)
        layout.addWidget(self.fps_entry, 3, 3)

        layout.addWidget(self.delay_label, 4, 0)
        layout.addWidget(self.delay_entry, 4, 1)
        #layout.addWidget(self.delay_units, 3, 2)

        # Right column of controls
        layout.addWidget(self.buffered_label, 2, 4)
        layout.addWidget(self.buffered_entry, 2, 5)

        # layout.addWidget(self.buffer_location_label, 2, 4)
        # layout.addWidget(self.buffer_location_entry, 2, 5)

        layout.addWidget(self.n_buffers_label, 3, 4)
        layout.addWidget(self.n_buffers_entry, 3, 5)

        layout.addWidget(self.trigger_label, 4, 4)
        layout.addWidget(self.trigger_entry, 4, 5)

        layout.addWidget(self.acq_mode_label, 5, 4)
        layout.addWidget(self.acq_mode_entry, 5, 5)

        layout.addWidget(self.sensor_pix_rate_label, 6, 4)
        layout.addWidget(self.sensor_pix_rate_entry, 6, 5)

        layout.addWidget(self.time_stamp, 7, 4)

        #layout.addWidget(self.lv_session_info, 8, 4, 1, 2)

        for column in range(6):
            layout.setColumnStretch(column, 1)

        # ROI/bin group
        layout.addWidget(self.roi_y0_label, 5, 0)
        layout.addWidget(self.roi_y0_entry, 5, 1)
        layout.addWidget(self.roi_height_label, 6, 0)
        layout.addWidget(self.roi_height_entry, 6, 1)
        layout.addWidget(self.sensor_ver_bin_label, 7, 0)
        layout.addWidget(self.sensor_ver_bin_entry, 7, 1)
        layout.addWidget(self.roi_x0_label, 5, 2)
        layout.addWidget(self.roi_x0_entry, 5, 3)
        layout.addWidget(self.roi_width_label, 6, 2)
        layout.addWidget(self.roi_width_entry, 6, 3)
        layout.addWidget(self.sensor_hor_bin_label, 7, 2)
        layout.addWidget(self.sensor_hor_bin_entry, 7, 3)

        self.setLayout(layout)

    def connect_to_camera(self):
        """
        TODO: call you function connecting to camera
        :return: None
        """
        self.connect_to_camera_status.setText("CONNECTING...")
        self.connect_to_camera_status.setStyleSheet("color: orange")

        try:
            self.camera = UcaCamera('pco')
        except:
            try:
                self.camera = UcaCamera('pco')
            except:
                self.on_camera_connect_failure()

        if self.camera is not None:
            self.on_camera_connect_success()


    def connect_to_dummy_camera(self):
        self.camera = DummyCamera()
        self.connect_to_camera_status.setText("CONNECTED")
        self.connect_to_camera_status.setStyleSheet("color: orange")
        self.camera_model_label.setText("Dummy camera")
        self.exposure_entry.setText("{:.02f}".format(
            self.camera.exposure_time.magnitude * 1000))
        self.fps_entry.setText("{:.02f}".format(int(1000.0 / self.exp_time)))
        self.roi_height_entry.setText("{}".format(self.camera.roi_height.magnitude))
        self.roi_width_entry.setText("{}".format(self.camera.roi_width.magnitude))
        self.roi_y0_entry.setText("{}".format(self.camera.roi_y0.magnitude))
        self.roi_x0_entry.setText("{}".format(self.camera.roi_x0.magnitude))
        self.live_preview_thread.camera = self.camera
        self.camera_connected_signal.emit(self.camera)
        self.live_on_button.setEnabled(True)
        self.live_off_button.setEnabled(True)
        self.save_one_image_button.setEnabled(True)
        self.camera.acquire_mode = None

    def on_camera_connect_success(self):
        """
        TODO: this function should be called from your camera connection software on successful connection
        :param camera: Camera object
        :return: None
        """
        self.connect_to_camera_status.setText("CONNECTED")
        self.connect_to_camera_status.setStyleSheet("color: green")
        self.connect_to_dummy_camera_button.setEnabled(False)
        self.connect_to_camera_button.setEnabled(False)
        self.ttl_scan.setEnabled(False)
        # identify model
        # Dimax must use internal buffer, 4000 only soft trigger
        if self.camera.sensor_width.magnitude == 2000:
            self.camera_model_label.setText("PCO Dimax")
            self.connect_to_camera_status.setText("CONNECTED to PCO Dimax")
            ####################################
            # !!!! can we hardcode it ???
            ####################################
            self.camera.storage_mode = self.camera.uca.enum_values.storage_mode.RECORDER
            self.camera.record_mode = self.camera.uca.enum_values.record_mode.RING_BUFFER
            ####
            tmp = self.buffered_entry.findText("NO")
            self.buffered_entry.setCurrentIndex(tmp)
            self.buffered_entry.setEnabled(False)
            self.n_buffers_entry.setEnabled(False)
        if self.camera.sensor_width.magnitude == 4008:
            self.camera_model_label.setText("PCO 4000")
            self.connect_to_camera_status.setText("CONNECTED to PCO 4000")
            self.trigger_entry.addItems(["SOFTWARE"])
            self.trigger_entry.setEnabled(False)
        if self.camera.sensor_width.magnitude == 2560:
            self.camera_model_label.setText("PCO Edge")
            self.connect_to_camera_status.setText("CONNECTED to PCO Edge")
            self.n_buffers_entry.setEnabled(True)
        ####################################
        # Hardcoding automode for now
        ####################################
        if self.camera.acquire_mode != self.camera.uca.enum_values.acquire_mode.AUTO:
            self.camera.acquire_mode = self.camera.uca.enum_values.acquire_mode.AUTO
        self.camera.timestamp_mode = self.camera.uca.enum_values.timestamp_mode.NONE
        # set default values
        self.exposure_entry.setText("{:.02f}".format(
            self.camera.exposure_time.magnitude*1000))
        self.fps_entry.setText("{}".format(
            int(1000.0/self.exp_time)))
        self.roi_height_entry.setText("{}".format(self.camera.roi_height.magnitude))
        self.roi_height_label.setText("ROI height, lines (max. {})".format(
            self.camera.sensor_height.magnitude))
        self.roi_width_entry.setText("{}".format(self.camera.roi_width.magnitude))
        self.roi_width_label.setText("ROI width, columns (max. {})".format(
            self.camera.sensor_width.magnitude))
        self.roi_y0_entry.setText("{}".format(self.camera.roi_y0.magnitude))
        self.roi_x0_entry.setText("{}".format(self.camera.roi_x0.magnitude))
        self.sensor_pix_rate_entry.addItems(
            [str(i) for i in self.camera.sensor_pixelrates])
        tmp = self.sensor_pix_rate_entry.findText(str(self.camera.sensor_pixelrate))
        self.sensor_pix_rate_entry.setCurrentIndex(tmp)
        #sensor_vertical_binning
        # sensor_horizontal_vertical_binning
        self.live_preview_thread.camera = self.camera
        self.readout_thread.camera = self.camera
        self.camera_connected_signal.emit(self.camera)
        self.live_on_button.setEnabled(True)
        self.live_off_button.setEnabled(True)
        self.save_one_image_button.setEnabled(True)
        #had to add this in order to avoid that signals
        #coming to early can break the matplotlib window
        self.live_on_func()
        sleep(1)
        self.live_off_func()

    def on_camera_connect_failure(self):
        """
        TODO: this function should be called from your camera connection software on connection failure
            or on timeout
        :return: None
        """
        self.connect_to_camera_status.setText("CONNECTION FAILED")
        self.connect_to_camera_status.setStyleSheet("color: red")
        self.camera = None
        self.camera_model_label.setText("")

    def set_camera_params(self):
        if self.camera_model_label.text() == 'Dummy camera':
            return -1
        try:
            if self.camera.state == 'recording':
                self.camera.stop_recording()
            self.camera.exposure_time = self.exp_time * q.msec
            #self.camera.frame_rate = fps * q.hertz
            self.camera.buffered = self.buffered
            if self.camera.buffered:
                self.camera.num_buffers = self.buffnum*1.1
            self.set_time_stamp()
            self.setROI()
            #self.camera.sensor_pixelrate = self.sensor_pix_rate_entry.currentText()
        except:
            error_message("Can not set camera parameters")
            return 0
        else:
            return 1

    def set_time_stamp(self):
        if self.time_stamp.isChecked():
            self.camera.timestamp_mode = self.camera.uca.enum_values.timestamp_mode.BINARY
        else:
            self.camera.timestamp_mode = self.camera.uca.enum_values.timestamp_mode.NONE

    def setROI(self):
        try:
            self.camera.roi_x0 = self.roi_x0 * q.pixels
            self.camera.roi_y0 = self.roi_y0 * q.pixels
            self.camera.roi_width = self.roi_width * q.pixels
            self.camera.roi_height = self.roi_height * q.pixels
        except:
            error_message("ROI is not correctly defined for the sensor, check multipliers and centering")

    def live_on_func(self):
        #info_message("Live mode ON")
        self.live_on_button.setEnabled(False)
        self.live_off_button.setEnabled(True)
        if self.camera.state == "recording":
            self.camera.stop_recording()
        if self.camera_model_label.text() == 'Dummy camera':
            pass
        else:
            if self.camera.trigger_source != self.camera.trigger_sources.AUTO:
                self.camera.trigger_source = self.camera.trigger_sources.AUTO
        # it can be buffered, e.g. libuca ring buffer + edge !
        # self.camera.buffered = False #self.buffered
        # self.setROI()
        # self.camera.exposure_time = self.exp_time * q.msec
        # #self.camera.frame_rate = self.fps * q.hertz
        self.set_camera_params()
        self.camera.start_recording()
        self.live_preview_thread.live_on = True
        self.lv_duration = time.time()

    def live_off_func(self):
        #info_message("Live mode OFF")
        self.live_preview_thread.live_on = False
        self.live_off_button.setEnabled(False)
        self.live_on_button.setEnabled(True)
        try:
            self.camera.stop_recording()
        except:
            pass
            # if self.camera_model_label.text() != 'Dummy camera':
            #    error_message("Cannot stop recording")
        self.lv_duration = time.time() - self.lv_duration
        self.frames_in_last_lv_seq = 0.0
        if self.camera_model_label.text() == 'PCO Dimax':# or self.buffered:
            self.save_lv_sequence_button.setEnabled(True)
            self.frames_in_last_lv_seq = self.camera.recorded_frames.magnitude
            self.setTitle("Camera controls. Status: recorded {0} frames in {1:.03f} seconds".
                                     format(self.frames_in_last_lv_seq,self.lv_duration))

    def save_lv_seq(self):
        self.abort_transfer_button.setEnabled(True)
        self.save_lv_sequence_button.setEnabled(False)
        self.live_on_button.setEnabled(False)
        self.save_one_image_button.setEnabled(False)
        # Get file name
        f, fext = self.QFD.getSaveFileName(
            self, 'Select dir and enter prefix', self.last_dir, "Image Files (*.tif)")
        if f == self.last_dir:
            f += "/im-seq-00"
        self.last_dir = os.path.dirname(f)

        # Start readout
        self.readout_thread.filename = f + '.tif'
        self.readout_thread.readout_on = True


    def abort_transfer_func(self):
        ## Readuot Thread
        self.readout_thread.abort_transfer = True
        self.abort_transfer_button.setEnabled(False)

    def readout_over_func(self, val):
        self.live_on_button.setEnabled(val)
        self.save_one_image_button.setEnabled(val)
        self.abort_transfer_button.setEnabled(False)

    def save_one_image(self):
        self.save_one_image_button.setEnabled(False)
        f, fext = self.QFD.getSaveFileName(
            self, 'Save image', self.last_dir, "Image Files (*.tif)")
        if f == self.last_dir:
            fname = os.path.join(f, "image-{:>04}.tif".format(self.nim))
            self.nim += 1
        else:
            fname = f + '.tif'
        self.last_dir = os.path.dirname(fname)
        tmp = False
        if self.live_preview_thread.live_on == True:
            self.live_off_func()
            tmp = True
        if self.camera_model_label.text() != 'Dummy camera':
            if self.camera.state == 'recording':
                self.camera.stop_recording()
            self.camera['trigger_source'].stash().join()
            self.camera.trigger_source = self.camera.trigger_sources.SOFTWARE
        self.set_camera_params()
        try:
            if self.camera_model_label.text() != 'Dummy camera':
                with self.camera.recording():
                    self.camera.trigger()
                    im = self.camera.grab()
            else:
                im = self.camera.grab()
        finally:
            write_tiff(fname, im)
            if self.camera_model_label.text() != 'Dummy camera':
                self.camera['trigger_source'].restore().join()
            self.save_one_image_button.setEnabled(True)
        if tmp == True:
            self.live_on_func()

    def restrict_params_depending_on_trigger(self):
        if self.trigger_entry.currentText() == 'SOFTWARE':
            tmp = self.buffered_entry.findText("NO")
            self.buffered_entry.setCurrentIndex(tmp)
            self.buffered_entry.setEnabled(False)
            self.n_buffers_entry.setEnabled(False)
        # delays only applicable in case of external trigger
        if self.trigger_entry.currentText() == 'AUTO' or\
            self.trigger_entry.currentText() == 'SOFTWARE':
            self.delay_entry.setEnabled(False)
        else:
            self.delay_entry.setEnabled(True)



        # getters/setters
    @property
    def exp_time(self):
        try:
            x = float(self.exposure_entry.text())
        except ValueError:
            error_message("{:}".format("Exp. time must be a positive number. Setting to default"))
            x = 13
            self.all_cam_params_correct = False
        if x < 0:
            error_message("{:}".format("Exp. time must be positive. Setting to default"))
            x = 13
            self.exposure_entry.setText('13')
            self.all_cam_params_correct = False
        if self.camera_model_label.text() == 'PCO Dimax' and (x > 40):
            error_message("{:}".format("Max exp. time for Dimax is 40 msec"))
            self.all_cam_params_correct = False
            x = 39.9
            self.exposure_entry.setText('39.9')
        if self.camera_model_label.text() == 'PCO Edge' and (x > 2000):
            error_message("{:}".format("Max exp. time for Edge is 2 sec"))
            x = 1999.9
            self.exposure_entry.setText('1999.9')
            self.all_cam_params_correct = False
        return x

    def relate_fps_to_exptime(self):
        if self.trig_mode == "EXTERNAL":
            x = int(1000.0 / (self.exp_time + self.dead_time))
        else:
            x = int(1000.0 / self.exp_time)
        self.fps_entry.setText("{:.02f}".format(x))

    @property
    def fps(self):
        try:
            x = float(self.fps_entry.text())
        except ValueError:
            warning_message("{:}".format(
                "FPS a positive number. Setting FPS based on exp. time"))
            self.relate_fps_to_exptime()
        if x < 0:
            error_message("{:}".format("FPS must be positive"))
            self.all_cam_params_correct = False
        if self.camera_model_label.text() == 'PCO Dimax' and (x < 25):
            error_message("{:}".format("Dimax FPS must be greater than 25"))
            self.all_cam_params_correct = False
        # if self.camera_model_label.text() == 'PCO Edge' and (x > 100):
        #     error_message("{:}".format("PCO Edge max FPS is 100"))
        #     self.all_cam_params_correct = False
        if int(x) > int(1000.0/self.exp_time): #because of round of errors
            warning_message("FPS [Hz] cannot exceed 1/exp.time[s]; setting fps=1/exp.time")
            self.relate_fps_to_exptime()
        return x

    @property
    def dead_time(self):
        try:
            x = float(self.delay_entry.text())
        except ValueError:
            warning_message("{:}".format(
                "Dead time must be a non-negative number"))
            x = 0
            self.delay_entry.setText('0')
            self.all_cam_params_correct = False
        if x < 0:
            warning_message("{:}".format(
                "Dead time must be a non-negative number"))
            x = 0
            self.delay_entry.setText('0')
            self.all_cam_params_correct = False
        return x

    @property
    def roi_height(self):
        try:
            h = int(self.roi_height_entry.text())
        except ValueError:
            error_message("ROI height must be  positive integer number smaller then {}"
                          .format(self.camera.sensor_height.magnitude))
        if self.camera_model_label.text() == 'PCO Dimax':
            h = int(h / 4) * 4
            if h > 2000:
                h = 2000
            self.roi_height_entry.setText(str(h))
            return h
        else:
            return h

    @property
    def roi_y0(self):
        try:
            h = int(self.roi_y0_entry.text())
        except ValueError:
            if self.camera_model_label.text() == 'PCO Dimax':
                error_message("ROI height must be positive integer number divisible by 4 and smaller then {:}"
                              .format(996))
            else:
                error_message("ROI height must be positive integer number smaller then {:}"
                              .format(self.camera.sensor_height.magnitude))
        if self.camera_model_label.text() == 'PCO Dimax':
            h = 1000 - self.roi_height / 2
            self.roi_y0_entry.setText(str(h))
            return h
        else:
            return h

    @property
    def roi_x0(self):
        try:
            h = int(self.roi_x0_entry.text())
        except ValueError:
            if self.camera_model_label.text() == 'PCO Dimax':
                error_message("ROI height must be positive integer number divisible by 4 and smaller then {:}"
                              .format(996))
            else:
                error_message("ROI height must be positive integer number smaller then {:}"
                              .format(self.camera.sensor_height.magnitude))
        if self.camera_model_label.text() == 'PCO Dimax':
            h = 1000 - self.roi_width / 2
            self.roi_x0_entry.setText(str(h))
            return h
        else:
            return h

    @property
    def roi_width(self):
        try:
            h = int(self.roi_width_entry.text())
        except ValueError:
            error_message("ROI height must be  positive integer number smaller then {}"
                          .format(self.camera.sensor_height.magnitude))
        if self.camera_model_label.text() == 'PCO Dimax':
            h = int(h / 4) * 4
            if h > 2000:
                h = 2000
            self.roi_width_entry.setText(str(h))
            return h
        else:
            return h

    @property
    def trig_mode(self):
        try:
            return self.trigger_entry.currentText()
        except ValueError:
            return None

    @property
    def acq_mode(self):
        try:
            return self.acq_mode_entry.currentText()
        except ValueError:
            return None

    @property
    def buffered(self):
        if self.camera_model_label == "PCO Dimax":
            return False
        try:
            if self.buffered_entry.currentText() == "YES":
                return True
            else:
                return False
        except ValueError:
            return None

    @property
    def buffnum(self):
        try:
            return int(self.n_buffers_entry.text())
        except ValueError:
            return None

    @property
    def pix_rate(self):
        try:
            return int(self.camera.sensor_pixelrates.currentText())*1e6
        except:
            warning_message('Can not get read-out rate')

    def extcamera_switched_func(self):
        if self.ttl_scan.isChecked():
            self.live_on_button.setEnabled(False)
            self.live_off_button.setEnabled(False)
            self.save_one_image_button.setEnabled(False)
        else:
            self.live_on_button.setEnabled(True)
            self.live_off_button.setEnabled(True)
            self.save_one_image_button.setEnabled(True)


class LivePreviewThread(QThread):
    def __init__(self, viewer, camera):
        super(LivePreviewThread, self).__init__()
        self.viewer = viewer
        self.camera = camera
        self.thread_running = True
        self.live_on = False
        atexit.register(self.stop)

    def stop(self):
        self.thread_running = False
        self.wait()

    def run(self):
        while self.thread_running:
            if self.live_on:
                self.viewer.show(self.camera.grab())
                time.sleep(0.05)
            else:
                time.sleep(1)


class ReadoutThread(QThread):
    readout_over_signal = pyqtSignal(bool)
    def __init__(self, camera):
        super(ReadoutThread, self).__init__()
        self.camera = camera
        self.thread_running = True
        self.readout_on = False
        self.last_dir = '/data'
        self.abort_transfer = False
        self.frames_grabbed_so_far = 0
        self.filename = None
        atexit.register(self.stop)

    def stop(self):
        self.thread_running = False
        self.wait()

    def run(self):
        while self.thread_running:
            if self.readout_on:
                # f, fext = self.qfd.getSaveFileName(
                #     None, 'Select dir and enter prefix', self.last_dir, "Image Files (*.tif)")
                # if f == self.last_dir:
                #     f += "/im-seq-00"
                # self.last_dir = os.path.dirname(f)
                self.frames_grabbed_so_far = 0
                tmp = time.time()
                self.abort_transfer = False

                self.camera.uca.start_readout()
                wrtr = TiffWriter(self.filename, bytes_per_file=2 ** 37)
                while not self.abort_transfer:
                    try:
                        wrtr.write(self.camera.grab())
                        # fname = f + "{:>04d}".format(self.frames_grabbed_so_far)+'.tif'
                        # write_tiff(fname, self.camera.grab())
                        self.frames_grabbed_so_far += 1
                    except CameraError:
                        # No more frames
                        self.abort_transfer = True
                self.camera.uca.stop_readout()
                wrtr.close()
                self.readout_over_signal.emit(True)
                info_message("Saved {0} images in {1} sec".
                             format(self.frames_grabbed_so_far, int(time.time() - tmp)))
                # Must be signals
                # self.save_lv_sequence_button.setEnabled(False)
                # self.abort_transfer_button.setEnabled(False)
                # self.viewer.show(self.camera.grab())
                self.readout_on = False
                time.sleep(0.05)
            else:
                time.sleep(1)

    # def run(self):
    #     self.main_loop()
    #
    # def main_loop(self):
    #     if not self.thread_running:
    #         return
    #     if self.live_on:
    #         self.viewer.show(self.camera.grab())
    #         self.timer.singleShot(50, self.main_loop) #timer =QTimer.init()
    #     else:
    #         self.timer.singleShot(1000, self.main_loop)

# class CameraMonitor(QObject):
#     camera_connected_signal = pyqtSignal(object)
#
#     def __init__(self):
#         super(CameraMonitor, self).__init__()
#         self.camera = PV(I0_PV, callback=self.on_camera_state_changed)
#
#     def on_camera_state_changed(self, camera, **kwargs ):
#         self.camera_connected_signal.emit(camera)
