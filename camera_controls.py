import atexit
from random import choice
from time import sleep

from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, \
    QPushButton, QComboBox, QFileDialog, QCheckBox

from message_dialog import info_message, error_message, warning_message

from concert.devices.cameras.uca import Camera as UcaCamera
from concert.devices.cameras.dummy import Camera as DummyCamera
from concert.storage import write_tiff
from concert.quantities import q
import os.path as osp
from matplotlib import pyplot as plt
from concert.devices.cameras.base import CameraError


def connect_to_camera_dummy():
    sleep(5)
    return choice(["Camera PCO", "Camera AAA", "0000"])


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

        self.live_off_button = QPushButton("LIVE OFF")
        self.live_off_button.setEnabled(False)
        self.live_off_button.clicked.connect(self.live_off_func)
        self.live_off_button.setEnabled(False)

        self.save_one_image_button = QPushButton("SAVE 1 image")
        self.save_one_image_button.clicked.connect(self.save_one_image)
        self.save_one_image_button.setEnabled(False)
        self.QFD = QFileDialog()
        self.nim = 0

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

        # DELAY
        self.delay_label = QLabel()
        self.delay_label.setText("Dead time [msec]")
        self.delay_entry = QLineEdit()
        self.delay_entry.setText("0")
        self.delay_entry.setEnabled(False)
        self.delay_units = QLabel()
        self.delay_units.setText("msec")

        # viewer limits
        self.viewer_lowlim_label = QLabel()
        self.viewer_lowlim_label.setText("Viewer low limit")
        self.viewer_lowlim_entry = QLineEdit()
        self.viewer_lowlim_entry.setText("100")
        self.viewer_highlim_label = QLabel()
        self.viewer_highlim_label.setText("Viewer high limit")
        self.viewer_highlim_entry = QLineEdit()
        self.viewer_highlim_entry.setText("1000")

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

        # BUFFER LOCATION
        # self.buffer_location_label = QLabel()
        # self.buffer_location_label.setText("BUFFER LOCATION")
        # self.buffer_location_entry = QComboBox()
        # self.buffer_location_entry.addItems(["PC", "Camera"])

        # N BUFFERS
        self.n_buffers_label = QLabel()
        self.n_buffers_label.setText("N BUFFERS")
        self.n_buffers_entry = QLineEdit()
        self.n_buffers_entry.setText("0")

        # TRIGGER
        self.trigger_label = QLabel()
        self.trigger_label.setText("TRIGGER")
        self.trigger_entry = QComboBox()
        self.trigger_entry.addItems(["SOFTWARE", "AUTO", "EXTERNAL"])

        # ACQUISITION MODE
        self.acq_mode_label = QLabel()
        self.acq_mode_label.setText("ACQUISITION MODE")
        self.acq_mode_entry = QComboBox()
        self.acq_mode_entry.addItems(["AUTO", "EXTERNAL"])
        self.acq_mode_entry.setEnabled(False)

        # PIXELRATE line 6
        self.sensor_pix_rate_label = QLabel()
        self.sensor_pix_rate_label.setText("SENSOR PIXEL RATE, MHz")
        self.sensor_pix_rate_entry = QComboBox()

        # Thread for live preview
        self.live_preview_thread = LivePreviewThread(
            viewer=self.viewer, camera=self.camera)
        self.live_preview_thread.start()

        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        # Buttons on top
        layout.addWidget(self.live_on_button, 0, 0, 1, 2)
        layout.addWidget(self.live_off_button, 0, 2, 1, 2)
        layout.addWidget(self.save_one_image_button, 0, 4, 1, 2)

        # Left column of controls
        layout.addWidget(self.connect_to_camera_button, 1, 0)
        layout.addWidget(self.connect_to_camera_status, 1, 1)
        layout.addWidget(self.camera_model_label, 1, 2)
        layout.addWidget(self.connect_to_dummy_camera_button, 1, 3)
        layout.addWidget(self.ttl_scan, 1, 4)

        # viewer clims
        layout.addWidget(self.viewer_lowlim_label, 2, 0)
        layout.addWidget(self.viewer_lowlim_entry, 2, 1)
        layout.addWidget(self.viewer_highlim_label, 2, 2)
        layout.addWidget(self.viewer_highlim_entry, 2, 3)

        layout.addWidget(self.exposure_label, 3, 0)
        layout.addWidget(self.exposure_entry, 3, 1)
        #layout.addWidget(self.exposure_units, 2, 2)

        layout.addWidget(self.delay_label, 3, 2)
        layout.addWidget(self.delay_entry, 3, 3)
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

        for column in range(6):
            layout.setColumnStretch(column, 1)

        # ROI/bin group
        layout.addWidget(self.roi_y0_label, 4, 0)
        layout.addWidget(self.roi_y0_entry, 4, 1)
        layout.addWidget(self.roi_height_label, 5, 0)
        layout.addWidget(self.roi_height_entry, 5, 1)
        layout.addWidget(self.sensor_ver_bin_label, 6, 0)
        layout.addWidget(self.sensor_ver_bin_entry, 6, 1)
        layout.addWidget(self.roi_x0_label, 4, 2)
        layout.addWidget(self.roi_x0_entry, 4, 3)
        layout.addWidget(self.roi_width_label, 5, 2)
        layout.addWidget(self.roi_width_entry, 5, 3)
        layout.addWidget(self.sensor_hor_bin_label, 6, 2)
        layout.addWidget(self.sensor_hor_bin_entry, 6, 3)

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
            self.on_camera_connect_failure()

        if self.camera is not None:
            self.on_camera_connect_success()

    def connect_to_dummy_camera(self):
        self.camera = DummyCamera()
        self.connect_to_camera_status.setText("CONNECTED")
        self.connect_to_camera_status.setStyleSheet("color: orange")
        self.camera_model_label.setText("Dummy camera")
        self.exposure_entry.setText("{}".format(
            self.camera.exposure_time.magnitude * 1000))
        self.roi_height_entry.setText("{}".format(self.camera.roi_height.magnitude))
        self.roi_width_entry.setText("{}".format(self.camera.roi_width.magnitude))
        self.roi_y0_entry.setText("{}".format(self.camera.roi_y0.magnitude))
        self.roi_x0_entry.setText("{}".format(self.camera.roi_x0.magnitude))
        self.live_preview_thread.camera = self.camera
        self.camera_connected_signal.emit(self.camera)
        self.live_on_button.setEnabled(True)
        self.live_off_button.setEnabled(True)
        self.save_one_image_button.setEnabled(True)

    def on_camera_connect_success(self):
        """
        TODO: this function should be called from your camera connection software on successful connection
        :param camera: Camera object
        :return: None
        """
        self.connect_to_camera_status.setText("CONNECTED")
        self.connect_to_camera_status.setStyleSheet("color: green")
        # identify model
        if self.camera.sensor_width.magnitude == 2000:
            self.camera_model_label.setText("PCO Dimax")
            # self.buffer_location_entry.addItems(["ON-BOARD"])
        if self.camera.sensor_width.magnitude == 4008:
            self.camera_model_label.setText("PCO 4000")
        # set default values
        self.exposure_entry.setText("{}".format(
            self.camera.exposure_time.magnitude*1000))
        self.roi_height_entry.setText("{}".format(self.camera.roi_height.magnitude))
        self.roi_height_label.setText("ROI height, lines (max. {})".format(
            self.camera.sensor_height.magnitude))
        self.roi_width_entry.setText("{}".format(self.camera.roi_width.magnitude))
        self.roi_width_label.setText("ROI width, columns (max. {})".format(
            self.camera.sensor_width.magnitude))
        self.roi_y0_entry.setText("{}".format(self.camera.roi_y0.magnitude))
        self.roi_x0_entry.setText("{}".format(self.camera.roi_x0.magnitude))
        self.sensor_pix_rate_entry.addItems(
            [str(int(i/1e6)) for i in self.camera.sensor_pixelrates])
        self.live_preview_thread.camera = self.camera
        self.camera_connected_signal.emit(self.camera)
        self.live_on_button.setEnabled(True)
        self.live_off_button.setEnabled(True)
        self.save_one_image_button.setEnabled(True)

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

    def live_on_func(self):
        #info_message("Live mode ON")
        self.live_on_button.setEnabled(False)
        self.live_off_button.setEnabled(True)
        if self.camera.state == "recording":
            self.camera.stop_recording()
        try:
            self.camera.exposure_time = self.exp_time * q.msec
        except:
            error_message("Make sure that exposure time is defined correctly")
        if self.camera_model_label.text() == 'Dummy camera':
            pass
        else:
            try:
                if self.camera.acquire_mode != self.camera.uca.enum_values.acquire_mode.AUTO:
                    self.camera.acquire_mode = self.camera.uca.enum_values.acquire_mode.AUTO
                if self.camera.trigger_source != self.camera.trigger_sources.AUTO:
                    self.camera.trigger_source = self.camera.trigger_sources.AUTO
                self.camera.buffered = False
            except:
                error_message("Cannot change to AUTO acq mode and AUTO trigger")
            self.setROI()
        self.camera.start_recording()
        self.live_preview_thread.live_on = True

    def setROI(self):
        try:
            self.camera.roi_x0 = self.roi_x0 * q.pixels
            self.camera.roi_y0 = self.roi_y0 * q.pixels
            self.camera.roi_width = self.roi_width * q.pixels
            self.camera.roi_height = self.roi_height * q.pixels
        except:
            error_message("ROI is not correctly defined for the sensor, check multipliers and centering")

    # def setdimaxROI(self):
    #     half_height = int(self.roi_height / 4) * 2
    #     half_width = int(self.roi_width / 4) * 2
    #     if half_width > 1000:
    #         half_width = 1000
    #     if half_height > 1000:
    #         half_height = 1000
    #     self.camera.roi_x0 = 1000 - half_width
    #     self.camera.roi_y0 = 1000 - half_height
    #     self.camera.roi_width = half_width*2
    #     self.camera.roi_height = half_height*2


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

    def save_one_image(self):
        self.save_one_image_button.setEnabled(False)

        #options = QFileDialog.Options()
        #options |= QFileDialog.DontUseNativeDialog
        pth = "/data/image-"
        #tmp = osp.join(pth,'image-')
        # self.QFD.selectFile(tmp)
        f, fext = self.QFD.getSaveFileName(
            self, 'Save image', pth, "Image Files (*.tif)")
        # info_message("{:}".format(fname))
        if f == pth:
            fname = "{}{:>04}.tif".format(f, self.nim)
            self.nim += 1
        else:
            fname = f + '.tif'
        tmp = False
        if self.live_preview_thread.live_on == True:
            self.live_off_func()
            tmp = True
        if self.camera_model_label.text() != 'Dummy camera':
            if self.camera.state == 'recording':
                self.camera.stop_recording()
            self.camera['trigger_source'].stash().join()
            self.camera.trigger_source = self.camera.trigger_sources.SOFTWARE
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

    # getters/setters
    @property
    def exp_time(self):
        try:
            return float(self.exposure_entry.text())
        except ValueError:
            return None

    @property
    def dead_time(self):
        try:
            return float(self.delay_entry.text())
        except ValueError:
            return None

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
                sleep(0.05)
            else:
                sleep(1)


# class CameraMonitor(QObject):
#     camera_connected_signal = pyqtSignal(object)
#
#     def __init__(self):
#         super(CameraMonitor, self).__init__()
#         self.camera = PV(I0_PV, callback=self.on_camera_state_changed)
#
#     def on_camera_state_changed(self, camera, **kwargs ):
#         self.camera_connected_signal.emit(camera)
