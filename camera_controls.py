from random import choice
from time import sleep

from PyQt5.QtCore import QTimer
from PyQt5.QtWidgets import QGridLayout, QLabel, QGroupBox, QLineEdit, QPushButton, QComboBox

from message_dialog import info_message

from concert.devices.cameras.uca import Camera as UcaCamera
from matplotlib import pyplot as plt
from concert.devices.cameras.base import CameraError

def connect_to_camera_dummy():
    sleep(5)
    return choice(["Camera PCO", "Camera AAA", "0000"])


class CameraControlsGroup(QGroupBox):
    """
    Camera controls
    """

    def __init__(self, camera, viewer, *args, **kwargs):
        # Timer - just as example
        super(CameraControlsGroup, self).__init__(*args, **kwargs)
        self.timer = QTimer()

        # Buttons
        self.live_on_button = QPushButton("LIVE ON")
        self.live_on_button.clicked.connect(self.live_on)

        self.live_off_button = QPushButton("LIVE OFF")
        self.live_off_button.setEnabled(False)
        self.live_off_button.clicked.connect(self.live_off)

        self.save_one_image_button = QPushButton("SAVE 1 image")
        self.save_one_image_button.clicked.connect(self.save_one_image)

        # Connect to camera
        self.connect_to_camera_button = QPushButton("Connect to camera")
        self.connect_to_camera_button.clicked.connect(self.connect_to_camera)  # No brackets required here!
        self.connect_to_camera_status = QLabel()
        self.connect_to_camera_status.setText("NOT CONNECTED")
        self.connect_to_camera_status.setStyleSheet("color: red")
        self.camera_model_label = QLabel()
        # Camera object
        self.camera = camera
        self.viewer = viewer


        # EXPOSURE
        self.exposure_label = QLabel()
        self.exposure_label.setText("EXPOSURE")
        self.exposure_entry = QLineEdit()
        self.exposure_units = QLabel()
        self.exposure_units.setText("msec")

        # DELAY
        self.delay_label = QLabel()
        self.delay_label.setText("DELAY")
        self.delay_entry = QLineEdit()
        self.delay_entry.setText("0")
        self.delay_units = QLabel()
        self.delay_units.setText("msec")

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

        layout.addWidget(self.exposure_label, 2, 0)
        layout.addWidget(self.exposure_entry, 2, 1)
        layout.addWidget(self.exposure_units, 2, 2)

        layout.addWidget(self.delay_label, 3, 0)
        layout.addWidget(self.delay_entry, 3, 1)
        layout.addWidget(self.delay_units, 3, 2)

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

        for column in range(6):
            layout.setColumnStretch(column, 1)

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

    def connect_to_camera(self, camera):
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

    def on_camera_connect_success(self):
        """
        TODO: this function should be called from your camera connection software on successful connection
        :param camera: Camera object
        :return: None
        """
        self.connect_to_camera_status.setText("CONNECTED")
        self.connect_to_camera_status.setStyleSheet("color: green")
        if self.camera.sensor_width.magnitude == 2000:
            self.camera_model_label.setText("PCO Dimax")
            self.buffer_location_entry.addItems(["ON-BOARD"])
        self.exposure_entry.setText("{}".format(self.camera.exposure_time.magnitude*1000))

        # sensor_height
        # roi_height
        # roi_width
        # roi_x0
        # roi_y0

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

    def live_on(self):
        #info_message("Live mode ON")
        self.live_on_button.setEnabled(False)
        self.live_off_button.setEnabled(True)
        if self.camera.acquire_mode != self.camera.uca.enum_values.acquire_mode.AUTO:
            self.camera.acquire_mode = self.camera.uca.enum_values.acquire_mode.AUTO
        if self.camera.trigger_source != self.camera.trigger_sources.AUTO:
            self.camera.trigger_source = self.camera.trigger_sources.AUTO
        self.camera.start_recording()
        self.viewer(self.camera.grab())
        #self.camera.stream(self.viewer())
        #plt.plot(range(40))
        #plt.show()


    def live_off(self):
        #info_message("Live mode OFF")
        self.live_off_button.setEnabled(False)
        self.live_on_button.setEnabled(True)
        self.camera.stop_recording()

    def save_one_image(self):
        self.save_one_image_button.setEnabled(False)
        info_message("Saving one image...")
        self.timer.singleShot(5000, self.on_image_saved)

    def on_image_saved(self):
        self.save_one_image_button.setEnabled(True)
        info_message("Image saved!")



