from typing import Any, Dict, List, Optional, Callable, cast
import math

from modules import module
from modules.types import ModuleStatus

from misc.timing import clock

from misc.gui import BoldLabel, Button, colors, fireoffFunction

from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QWidget,
)


class QtGuiModuleWrapper(module.AbstractModule):

    def __init__(self, wrapped_module: module.Module):

        self.module = wrapped_module

        # init gui
        self.gui: Optional[QWidget] = None

    def get_name(self) -> str:
        return self.module.get_name()

    def get_description(self) -> str:
        return self.module.get_description()

    def get_parameter_definition(self) -> list:
        return self.module.get_parameter_definition()

    def start(self):
        self.module.start()

    def stop(self):
        self.module.stop()

    def restart(self):
        self.module.restart()

    def get_state(self) -> ModuleStatus:
        return self.module.get_state()

    def get_all_parameters(self) -> Dict[str, Any]:
        return self.module.get_all_parameters()

    def get_available_parameters(self) -> List[str]:
        return self.module.get_available_parameters()

    def get_parameter_value(self, key: str) -> Any:
        return self.module.get_parameter_value(key)

    def set_parameter_value(self, key: str, value) -> bool:
        return self.module.set_parameter_value(key, value)

    # creates a GUI Widget displaying the module's status and allowing to adjust its parameters
    def initGui(self):

        self.gui = QWidget()
        self.gui.setMaximumWidth(100)
        # self.gui.setStyleSheet("border: 1px dashed #888888;")
        self.gui.setObjectName("ModuleGUI " + self.module.MODULE_NAME)
        self.status_label = QLabel(self.module.state.value)
        self.status_label.setAlignment(QtCore.Qt.AlignRight)
        self.running_since_label = QLabel("")
        self.running_since_label.setAlignment(QtCore.Qt.AlignRight)

        # create a grid layout
        self.layout = QGridLayout()
        self.layout.setContentsMargins(0, 10, 0, 0)
        self.layout.setVerticalSpacing(3)
        self.layout.setHorizontalSpacing(3)

        # add the module's name as a label as well as its status
        l = BoldLabel(self.module.MODULE_NAME)
        l.setToolTip(
            "<br />Module Description:<br /><b>"
            + self.module.MODULE_NAME
            + "</b><hr /><pre>"
            + self.module.MODULE_DESCRIPTION
            + "</pre>"
        )
        self.layout.addWidget(l, 0, 0, 1, 3)
        self.layout.addWidget(self.status_label, 0, 3, 1, 1)
        self.layout.addWidget(self.running_since_label, 0, 4, 1, 1)

        # create three buttons to control the module
        self.btn_start = Button("start")
        self.btn_stop = Button("stop")
        self.btn_restart = Button("restart")

        # connect the actions
        self.btn_start.clicked.connect(lambda: fireoffFunction(self.module.start))
        self.btn_stop.clicked.connect(lambda: fireoffFunction(self.module.stop))
        self.btn_restart.clicked.connect(lambda: fireoffFunction(self.module.restart))

        # add the buttons to the layout in a single row
        sublayout = QHBoxLayout()
        sublayout.addWidget(self.btn_start)
        sublayout.addWidget(self.btn_stop)
        sublayout.addWidget(self.btn_restart)
        self.layout.addLayout(sublayout, 1, 0, 1, 5)

        # if there are any parameters for this module, create inputs for them
        if len(self.module.parameters) > 0:

            self.layout.addWidget(BoldLabel("Parameters:"), 2, 0, 1, 5)

            self.param_area = QScrollArea()
            self.param_area.setFrameShape(QtWidgets.QFrame.NoFrame)
            self.param_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
            self.param_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
            self.param_area.setWidgetResizable(True)
            self.layout.addWidget(self.param_area, 3, 0, 1, 5)

            self.param_widget = QWidget()
            self.param_layout = QGridLayout()
            self.param_widget.setLayout(self.param_layout)

            self.param_layout.setContentsMargins(0, 0, 0, 0)
            self.param_layout.setVerticalSpacing(3)
            self.param_layout.setHorizontalSpacing(3)

            self.param_area.setWidget(self.param_widget)

            row = 0

            for _, p in self.module.parameters.items():

                parameter_display_name = p.displayname
                if type(p.unit) is str and len(p.unit) >= 1:
                    parameter_display_name += " (" + p.unit + ")"
                p.qlabel = QLabel(parameter_display_name)
                p.qlabel.setToolTip(parameter_display_name)
                self.param_layout.addWidget(p.qlabel, row, 0, 1, 2)

                if p.data_type is list:
                    p.input = QComboBox()
                    p.input.addItems(p.unit)
                    p.input.setCurrentIndex(p.input.findText(p.getValue()))
                    p.input.activated.connect(lambda: self.updateParametersFromGUI())

                elif p.data_type is bool:
                    p.input = QCheckBox()
                    p.input.setChecked(p.getValue())
                    p.input.stateChanged.connect(lambda: self.updateParametersFromGUI())

                elif p.data_type == "button":
                    p.input = QPushButton(p.displayname)

                elif p.data_type == Callable:
                    p.input = QPushButton(parameter_display_name)
                    p.input.clicked.connect(getattr(self.module, p.getValue()))
                else:
                    p.input = QLineEdit(str(p.getValue()))
                    p.input.textEdited.connect(lambda: self.updateParametersFromGUI())

                self.param_layout.addWidget(p.input, row, 2, 1, 3)

                row += 1

            # add expanding empty widget below parameters to take up any leftover space instead of parameters expanding
            empty = QWidget()
            empty.setSizePolicy(
                QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred
            )
            self.param_layout.addWidget(empty, row, 0, 1, 1)

        self.gui.setLayout(self.layout)

        self.timer_gui_update = QtCore.QTimer(self.gui)
        self.timer_gui_update.timeout.connect(self.update_gui_dimensions)
        self.timer_gui_update.start(500)

    def getGUI(self) -> QWidget:

        if self.gui is None:
            self.initGui()

        # self.set_state(self.get_state())

        return self.gui

    def setInputsEnabled(self, en: bool):

        for n, p in self.module.parameters.items():
            if p.data_type is Callable:
                continue
            p.input.setEnabled(en)

    def updateParametersFromGUI(self):

        COLOR_GOOD = ""
        COLOR_BAD = "#ff8844"

        for n, p in self.module.parameters.items():

            if p.data_type is list:

                p.setValue(p.input.currentText())

            elif p.data_type is bool:

                p.setValue(p.input.isChecked())

            elif p.data_type is int:

                try:
                    val = int(p.input.text())
                    p.setValue(val)
                    p.input.setStyleSheet(
                        "QLineEdit{ background-color: %s;}" % COLOR_GOOD
                    )
                except:
                    print(n, "could not convert to int")
                    p.input.setStyleSheet(
                        "QLineEdit{ background-color: %s; }" % COLOR_BAD
                    )

            elif p.data_type is float:

                try:
                    val = float(p.input.text())
                    p.setValue(val)
                    p.input.setStyleSheet(
                        "QLineEdit{ background-color: %s; }" % COLOR_GOOD
                    )
                except:
                    print(n, "could not convert to float")
                    p.input.setStyleSheet(
                        "QLineEdit{ background-color: %s; }" % COLOR_BAD
                    )

            elif p.data_type == "button":
                pass

            elif p.data_type is str:

                p.setValue(p.input.text())

    def update_gui_dimensions(self):

        if self.gui is not None:

            w = self.gui.width()
            maxwidth = int(w / 2 - 3)

            for p in self.module.parameters.values():
                if p.qlabel is not None:
                    p.qlabel.setMinimumWidth(maxwidth)
                    p.qlabel.setMaximumWidth(maxwidth)
                if p.input is not None:
                    p.input.setMaximumWidth(maxwidth)

    def updateGuiSecondly(self):

        # do not do anything if there is no GUI (yet)
        if self.gui is None:
            return

        # update parameter values shown in UI if actual value changed
        for _, p in self.module.parameters.items():

            if p.data_type in [int, float, str]:

                input = cast(QLineEdit, p.input)

                if str(p.getValue()) != input.text() and not input.hasFocus():
                    input.setText(str(p.getValue()))

        # if module is running
        if self.get_state() is ModuleStatus.RUNNING:

            # update the running since label
            running_seconds = clock() - self.module.running_since
            if running_seconds >= 60:
                self.running_since_label.setText(
                    "{:d}m {:02.0f}s".format(
                        math.floor(running_seconds / 60), running_seconds % 60
                    )
                )
            else:
                self.running_since_label.setText(
                    "{:02.0f}s".format(clock() - self.module.running_since)
                )

        # if module is starting, empty the running since label
        elif self.get_state() is ModuleStatus.STARTING:
            self.running_since_label.setText("")

        # update GUI depending on status
        self.status_label.setText(self.get_state().value)
        if self.get_state() is ModuleStatus.RUNNING:
            self.status_label.setStyleSheet("QLabel{ color: green;}")
        else:
            self.status_label.setStyleSheet("QLabel{ color: " + colors[-1] + ";}")

        # set parameter inputs en/disabled depending on state
        if self.get_state() is ModuleStatus.STOPPED:
            self.setInputsEnabled(True)
        else:
            self.setInputsEnabled(False)

        # set start button en/disabled depending on state
        if self.get_state() is ModuleStatus.STOPPED:
            self.btn_start.setEnabled(True)
        else:
            self.btn_start.setEnabled(False)

        # set stop and restart buttons en/disabled depending on state
        if self.get_state() is ModuleStatus.RUNNING:
            self.btn_stop.setEnabled(True)
            self.btn_restart.setEnabled(True)
        else:
            # Note: changing the order of the following two lines prevents the application from
            # crashing without any error from time to time when hitting the "STOP" button
            self.btn_restart.setEnabled(False)
            self.btn_stop.setEnabled(False)


