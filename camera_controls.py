import atexit
from random import choice
from time import sleep

from PyQt5.QtCore import QTimer, QThread, pyqtSignal, QObject
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, QPushButton, QComboBox

from message_dialog import info_message, error_message, warning_message

from concert.devices.cameras.uca import Camera as UcaCamera
from concert.devices.cameras.dummy import Camera as DummyCamera
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

        # Connect to camera
        self.connect_to_camera_button = QPushButton("Connect to camera")
        self.connect_to_camera_button.clicked.connect(self.connect_to_camera)
        self.connect_to_dummy_camera_button = QPushButton("Connect to dummy camera")
        self.connect_to_dummy_camera_button.clicked.connect(self.connect_to_dummy_camera)
        self.connect_to_camera_status = QLabel()
        self.connect_to_camera_status.setText("NOT CONNECTED")
        self.connect_to_camera_status.setStyleSheet("color: red")
        self.camera_model_label = QLabel()
        # Camera object
        self.camera = None
        self.viewer = viewer
        self.live_on = False

        # EXPOSURE
        self.exposure_label = QLabel()
        self.exposure_label.setText("EXPOSURE [msec]")
        self.exposure_entry = QLineEdit()
        self.exposure_units = QLabel()
        self.exposure_units.setText("msec")

        # DELAY
        self.delay_label = QLabel()
        self.delay_label.setText("DELAY [msec]")
        self.delay_entry = QLineEdit()
        self.delay_entry.setText("0")
        self.delay_units = QLabel()
        self.delay_units.setText("msec")

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
        #sensor_vertical_binning
        self.sensor_ver_bin_label = QLabel()
        self.sensor_ver_bin_label.setText("Vertical binning")
        self.sensor_ver_bin_entry = QLineEdit()
        self.sensor_ver_bin_entry.setText("1")
        #sensor_horizontal_binning
        self.sensor_hor_bin_label = QLabel()
        self.sensor_hor_bin_label.setText("Horizontal binning")
        self.sensor_hor_bin_entry = QLineEdit()
        self.sensor_hor_bin_entry.setText("1")

        # BUFFERED
        self.buffered_label = QLabel()
        self.buffered_label.setText("BUFFERED")
        self.buffered_entry = QComboBox()
        self.buffered_entry.addItems(["YES", "NO"])

        # BUFFER LOCATION
        self.buffer_location_label = QLabel()
        self.buffer_location_label.setText("BUFFER LOCATION")
        self.buffer_location_entry = QComboBox()
        self.buffer_location_entry.addItems(["RAM"])

        # N BUFFERS
        self.n_buffers_label = QLabel()
        self.n_buffers_label.setText("N BUFFERS")
        self.n_buffers_entry = QLineEdit()

        # TRIGGER
        self.trigger_label = QLabel()
        self.trigger_label.setText("TRIGGER")
        self.trigger_entry = QComboBox()
        self.trigger_entry.addItems(["AUTO", "EXT", "SOFT"])

        # ACQUISITION MODE
        self.acq_mode_label = QLabel()
        self.acq_mode_label.setText("ACQUISITION MODE")
        self.acq_mode_entry = QComboBox()
        self.acq_mode_entry.addItems(["AUTO", "EXT"])

        # PIXELRATE line 6
        self.sensor_pix_rate_label = QLabel()
        self.sensor_pix_rate_label.setText("SENSOR PIXEL RATE, MHz")
        self.sensor_pix_rate_entry = QComboBox()

        # Thread for live preview
        self.live_preview_thread = LivePreviewThread(viewer=self.viewer, camera=self.camera)
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

        layout.addWidget(self.exposure_label, 2, 0)
        layout.addWidget(self.exposure_entry, 2, 1)
        #layout.addWidget(self.exposure_units, 2, 2)

        layout.addWidget(self.delay_label, 3, 0)
        layout.addWidget(self.delay_entry, 3, 1)
        #layout.addWidget(self.delay_units, 3, 2)

        # Right column of controls
        layout.addWidget(self.buffered_label, 1, 4)
        layout.addWidget(self.buffered_entry, 1, 5)

        layout.addWidget(self.buffer_location_label, 2, 4)
        layout.addWidget(self.buffer_location_entry, 2, 5)

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

    # Convert numeric parameters
    def exposure(self):
        return float(self.exposure_entry.text())

    def delay(self):
        return float(self.delay_entry.text())

    def n_buffers(self):
        return int(self.n_buffers_entry.text())

    def entry_value(self):
        return float(self.entry.text())

    # Return boolean for "buffered" drop-down list
    def buffered(self):
        return self.buffered_entry.currentText() == "YES"

    # Return numeric index for "buffer location" drop-down lists
    def buffer_location(self):
        return self.buffer_location_entry.currentIndex()

    # Return text value for other drop-down lists
    def trigger(self):
        return self.trigger_entry.currentText()

    def acq_mode(self):
        return self.acq_mode_entry.currentText()

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
        self.exposure_entry.setText("{}".format(self.camera.exposure_time.magnitude * 1000))
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
            self.buffer_location_entry.addItems(["ON-BOARD"])
        if self.camera.sensor_width.magnitude == 4008:
            self.camera_model_label.setText("PCO 4000")
        # set default values
        self.exposure_entry.setText("{}".format(self.camera.exposure_time.magnitude*1000))
        self.roi_height_entry.setText("{}".format(self.camera.roi_height.magnitude))
        self.roi_height_label.setText("ROI height, lines (max. {})".format(self.camera.sensor_height.magnitude))
        self.roi_width_entry.setText("{}".format(self.camera.roi_width.magnitude))
        self.roi_width_label.setText("ROI width, columns (max. {})".format(self.camera.sensor_width.magnitude))
        self.roi_y0_entry.setText("{}".format(self.camera.roi_y0.magnitude))
        self.roi_x0_entry.setText("{}".format(self.camera.roi_x0.magnitude))
        self.sensor_pix_rate_entry.addItems([str(int(i/1e6)) for i in self.camera.sensor_pixelrates])
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
        try:
            if self.camera.acquire_mode != self.camera.uca.enum_values.acquire_mode.AUTO:
                self.camera.acquire_mode = self.camera.uca.enum_values.acquire_mode.AUTO
            if self.camera.trigger_source != self.camera.trigger_sources.AUTO:
                self.camera.trigger_source = self.camera.trigger_sources.AUTO
            self.camera.start_recording()
        except:
            if self.camera_model_label.text() != 'Dummy camera':
                error_message("Cannot change acquisition mode and trigger source")
        self.live_preview_thread.live_on = True

    def live_off_func(self):
        #info_message("Live mode OFF")
        self.live_preview_thread.live_on = False
        self.live_off_button.setEnabled(False)
        self.live_on_button.setEnabled(True)
        try:
            self.camera.stop_recording()
        except:
            if self.camera_model_label.text() != 'Dummy camera':
                error_message("Cannot stop recording")

    def save_one_image(self):
        self.save_one_image_button.setEnabled(False)
        info_message("Saving one image...")
        self.timer.singleShot(5000, self.on_image_saved)

    def on_image_saved(self):
        self.save_one_image_button.setEnabled(True)
        info_message("Image saved!")

    #getters/setters
    @property
    def exp_time(self):
        try:
            return int(self.exposure_entry.text())
        except ValueError:
            return None

    @property
    def roi_height(self):
        try:
            return int(self.roi_height_entry.text())
        except ValueError:
            return None


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

# import time
# import numpy as np
#
# def test(nframes):
#     t1 = time.time()
#         for i in range(nframes):
#         camera.trigger()
#         print np.std(camera.grab())
#     t2 = time.time()
#     return t2-t1