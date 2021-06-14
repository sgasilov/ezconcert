import re

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QDialog, QLineEdit, QPushButton, QLabel, QGridLayout

from message_dialog import error_message


class Login(QDialog):
    def __init__(self, login_parameters_dict, **kwargs):
        super(Login, self).__init__(**kwargs)
        # Pass a method from main GUI
        self.login_parameters_dict = login_parameters_dict

        self.setWindowTitle("USER LOGIN")
        self.setWindowModality(Qt.ApplicationModal)
        self.setAttribute(Qt.WA_DeleteOnClose)

        self.welcome_label = QLabel()
        self.welcome_label.setText("Welcome to BMIT!")
        self.prompt_label = QLabel()
        self.prompt_label.setText("Please enter your username and project number below.")
        self.user_label = QLabel()
        self.user_label.setText("User name:")
        self.user_entry = QLineEdit()

        self.project_label = QLabel()
        self.project_label.setText("Project:")
        self.project_entry = QLineEdit()
        self.login_button = QPushButton("LOGIN")
        self.login_button.clicked.connect(self.on_login_button_clicked)
        self.set_layout()

    def set_layout(self):
        layout = QGridLayout()
        self.welcome_label.setAlignment(Qt.AlignCenter)
        self.prompt_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.welcome_label, 0, 0, 1, 2)
        layout.addWidget(self.prompt_label, 1, 0, 1, 2)
        layout.addWidget(self.user_label, 2, 0, 1, 1)
        layout.addWidget(self.user_entry, 2, 1, 1, 1)
        layout.addWidget(self.project_label, 3, 0, 1, 1)
        layout.addWidget(self.project_entry, 3, 1, 1, 1)
        layout.addWidget(self.login_button, 4, 0, 1, 2)

        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        self.setLayout(layout)

    def uppercase_project_entry(self):
        self.project_entry.setText(self.project_entry.text().upper())

    def strip_spaces_from_user_entry(self):
        self.user_entry.setText(self.user_entry.text().replace(' ', ''))

    @property
    def project_name(self):
        return self.project_entry.text()

    @property
    def user_name(self):
        return self.user_entry.text()

    def validate_entries(self):
        self.uppercase_project_entry()
        self.strip_spaces_from_user_entry()
        project_valid = bool(re.match(r"^[0-9]{2}[A-Z][0-9]{5}$", self.project_name))
        username_valid = bool(re.match(r"^[a-zA-Z0-9]*$", self.user_name))
        return project_valid, username_valid

    def on_login_button_clicked(self):
        project_valid, username_valid = self.validate_entries()
        if project_valid and username_valid:
            self.login_parameters_dict.update({'user': self.user_name})
            self.login_parameters_dict.update({'project': self.project_name})
            self.accept()
        elif not username_valid:
            error_message("Username should be alpha-numeric ")
        elif not project_valid:
            error_message("The project should be in format: CCTNNNNN, \n" 
                          "where CC is cycle number, "
                          "T is one-letter type, "
                          "and NNNNN is project number")
