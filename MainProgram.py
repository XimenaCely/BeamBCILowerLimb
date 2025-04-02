# imports from standard libraries
import importlib
import subprocess
import time
import sys
import os

from typing import List, Dict, Optional
from functools import reduce

import json
from enum import Enum
import pathlib

# PyQt5 imports
from PyQt5 import QtCore, QtWidgets
from PyQt5.QtWidgets import QGridLayout, QGroupBox, QHBoxLayout, QWidgetItem
from PyQt5.QtTest import QTest
from PyQt5.QtCore import Qt

# import own scripts
from misc.gui import *
from misc import log

from misc import config_parser
config_parser.parse_args()
args = config_parser.args

import globals

# flag whether external signal processing App is available
from globals import LSLAvailable

# import PyLSL
if LSLAvailable:
    from pylsl import resolve_streams

# import modules
from modules.module import Module, AbstractModule
from modules.QtGuiModuleWrapper import QtGuiModuleWrapper
import modules.src
import modules.preprocessing
import modules.classification
import modules.task
import modules.feedback
import modules.rec

from misc.timing import clock

# reference for time since program started
START_CLOCK = clock()

pbciLogHandler = log.initialize_logger(START_CLOCK)  # Reference to LogHandler for displaying in the log-widget
logger = log.getLogger(__name__)

logger.debug(f"Configuration loaded: {args}")

main_grid_layout_margin: int = 10   # spacing between window edges and content
main_grid_layout_spacing: int = 10   # spacing between main sections of GUI
module_groupbox_margin: int = 5     # spacing between module box and its content
module_layout_margin: int = 0       # behaves weird, better keep at zero
module_layout_spacing: int = 0      # spacing between elements in module layout
additional_px_lost_per_module: int = 15


class ModuleType(Enum):
    SOURCE = 'source'
    PREPROCESSING = 'preprocessing'
    CLASSIFICATION = 'classification'
    TASK = 'task'
    FEEDBACK = 'feedback'
    RECORDING = 'recording'


# Thread that resolves available LSL streams every few seconds and makes them accessible through QtSignal
class LSLStreamResolverThread(QtCore.QThread):
    LSLStreamsResolved = QtCore.pyqtSignal(object)

    def __init__(self, update_interval: int = 3, wait_time: int = 1):
        QtCore.QThread.__init__(self)

        if update_interval < wait_time:
            raise ValueError('LSLStreamResolverThread: update_interval can not be smaller than wait_time!')

        self.update_interval = update_interval
        self.wait_time = wait_time

    def run(self):
        # can use True because Thread will be started as a daemon
        while self.isRunning():
            if LSLAvailable:
                try:
                    streams = resolve_streams(wait_time=self.wait_time)
                    self.LSLStreamsResolved.emit(streams)
                except Exception:
                    pass

            time.sleep(self.update_interval - self.wait_time)


# Main class: Represents the application's main window and manages all other components of the application
class MainWindow(QtWidgets.QMainWindow):

    # Constructor - arguments:
    # - left: position from left edge of screen
    # - top: ...
    # - width: width of the window
    # - height: height of the window
    # - maximized: wether to show maximized
    def __init__(self, left: int, top: int, width: int, height: int, maximized: bool = True):
        super(MainWindow, self).__init__()

        # Set window Title and position the window according to the given parameters
        self.setWindowTitle("BeamBCI")

        if hasattr(args, 'frameless_window') and args.frameless_window:
            self.setWindowFlags(Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        # self.setWindowOpacity(0.6)
        self.resizeAndPosition(left, top, width, height)

        self.setStyleSheet(main_stylesheet)

        self.modules: Dict[str, Optional[AbstractModule]] = {
            ModuleType.SOURCE.value: None,
            ModuleType.PREPROCESSING.value: None,
            ModuleType.CLASSIFICATION.value: None,
            ModuleType.TASK.value: None,
            ModuleType.FEEDBACK.value: None,
            ModuleType.RECORDING.value: QtGuiModuleWrapper(
                modules.rec.LabRecorderModule.LabRecorderModule())
        }

        self.module_layouts: Dict[str, Optional[QVBoxLayout]] = {
            ModuleType.SOURCE.value: None,
            ModuleType.PREPROCESSING.value: None,
            ModuleType.CLASSIFICATION.value: None,
            ModuleType.TASK.value: None,
            ModuleType.FEEDBACK.value: None,
            ModuleType.RECORDING.value: None
        }

        self.module_reload_buttons: Dict[str, Optional[QPushButton]] = {
            ModuleType.SOURCE.value: None,
            ModuleType.PREPROCESSING.value: None,
            ModuleType.CLASSIFICATION.value: None,
            ModuleType.TASK.value: None,
            ModuleType.FEEDBACK.value: None,
        }

        self.module_select_menus: Dict[str, Optional[QtWidgets.QComboBox]] = {
            ModuleType.SOURCE.value: None,
            ModuleType.PREPROCESSING.value: None,
            ModuleType.CLASSIFICATION.value: None,
            ModuleType.TASK.value: None,
            ModuleType.FEEDBACK.value: None,
            ModuleType.RECORDING.value: None
        }

        self.module_paths = {
            ModuleType.SOURCE.value: modules.src,
            ModuleType.PREPROCESSING.value: modules.preprocessing,
            ModuleType.CLASSIFICATION.value: modules.classification,
            ModuleType.TASK.value: modules.task,
            ModuleType.FEEDBACK.value: modules.feedback,
            ModuleType.RECORDING.value: modules.rec
        }

        # build menubar
        self.setupMenu()

        # build the GUI
        mainwidget = QWidget()
        mainwidget.setObjectName("MainWidget")
        mainwidget.setLayout(self.setupGUI())
        self.setCentralWidget(mainwidget)

        # show the main window
        if maximized:
            self.showMaximized()
        else:
            self.show()

        # bring the MainWindow on top
        self.activateWindow()

        # create a timer which updates the logs
        timer_gui_update = QtCore.QTimer(self)
        timer_gui_update.timeout.connect(self.update_gui_dimensions)
        timer_gui_update.start(100)

        # create a timer which updates the modules GUIs every second
        timer_gui_update_sec = QtCore.QTimer(self)
        timer_gui_update_sec.timeout.connect(self.update_module_guis_secondly)
        timer_gui_update_sec.start(200)

        logger.info("GUI started.")

        # create a thread that observers available LSL streams
        if LSLAvailable:
            self.lslthread = LSLStreamResolverThread()
            self.lslthread.LSLStreamsResolved.connect(self.updateLSLStreams)
            self.lslthread.start()

        # create a timer which updates the logs
        timer = QtCore.QTimer(self)
        timer.timeout.connect(self.updateLogs)
        timer.start(100)

        # start other startup processes separatley from the GUI
        fireoffFunction(self.startUpAsyncTasks)

        # init placeholder for information window
        self.about_window = None

        if type(args.experiment_config) is str and len(args.experiment_config) > 5:
            config_path = globals.PYTHONBCI_PATH / "experiments" / args.experiment_config
            if config_path.exists():
                self.load_experiment(path=str(config_path))



    # Function that runs some startup processes in another thread to avoid blocking the GUI
    def startUpAsyncTasks(self):
        time.sleep(0.5)

        # Check if LSL is available
        if LSLAvailable:
            logger.success("LSL available")
        else:
            logger.error("LSL not available")


    #####################################################
    #                                                   #
    #   GUI related functions:                          #
    #                                                   #
    #####################################################

    def allModulesStopped(self) -> bool():

        for module in self.modules.values():
            if module is not None and module.get_state() is not Module.Status.STOPPED:
                return False

        return True

    def reloadModule(self, module_type: ModuleType, class_name, parameters={}):
        if class_name == 'None':
            logger.warning(f"No module loaded, cannot reload")
            return

        module_path = self.module_paths[module_type.value]
        logger.info(f"Reloading Module {getattr(module_path, class_name).__name__}")
        importlib.reload(getattr(module_path, class_name))
        self.changeModule(module_type, class_name, parameters)

    def changeModule(self, module_type: ModuleType, class_name, parameters={}):
        """
        Exchanges a Module by another one

        :param module_type: Type of the Module which is to be exchanged
        :param class_name: Class name of the new module
        :param parameters: Parameters to set in the new module
        """

        if not self.allModulesStopped():
            alert("You can not change a module while any module is running!")
            return

        layout = self.module_layouts[module_type.value]
        module_path = self.module_paths[module_type.value]
        logger.debug(f"Changing {module_path.__name__} to {class_name}")


        # For debugging: Prints types of widgets in the modules parent layout
        # for i in range(layout.count()):
        #    if layout.itemAt(i).widget() is not None:
        #        print(i, "W", layout.itemAt(i).widget().objectName())
        #    else:
        #        print(i, "I", layout.itemAt(i))

        # This is where the Module's button is to be expected with the (invisible) reload button above
        module_index = 3

        layout.itemAt(module_index).widget().setParent(None)
        layout.removeWidget(layout.itemAt(module_index).widget())

        new_mod = None

        if class_name != 'None':
            try:
                new_mod: Module = QtGuiModuleWrapper(getattr(getattr(module_path, class_name), class_name)())

                for key, val in parameters.items():
                    if not new_mod.set_parameter_value(key, val):
                        logger.warning(f"Could not set Parameter '{key}' to '{val}' in Module '{new_mod.get_name()}'")

                layout.insertWidget(module_index, new_mod.getGUI())

                if self.module_select_menus[module_type.value] is not None:
                    for i in range(len(self.module_select_menus[module_type.value])):
                        if self.module_select_menus[module_type.value].itemText(i) == class_name:
                            self.module_select_menus[module_type.value].setCurrentIndex(i)

            except AttributeError as e:
                logger.error(f"Could not load Module '{class_name}': Module does not exist.")
                logger.exception(e)
                class_name = 'None'

        if class_name == 'None':
            layout.insertWidget(module_index, QLabel("no module selected"))
            self.module_select_menus[module_type.value].setCurrentIndex(0)

        layout.addStretch()

        self.modules[module_type.value] = new_mod

    # starts a module without freezing the GUI
    def startModule(self, mod: Module) -> bool:
        if mod.get_state() == Module.Status.STOPPED:
            logger.info(f"Starting module {mod.get_name()}...")
            fireoffFunction(mod.start)
            QTest.qWait(300)

            while mod.get_state() is not Module.Status.STOPPED and mod.get_state() is not Module.Status.RUNNING:
                QTest.qWait(100)

            if mod.get_state() is Module.Status.RUNNING:
                logger.info("... Module started.")
                return True

            else:
                logger.error("... failed to start Module.")
                return False

    # stops a module without freezing the GUI
    def stopModule(self, mod: Module):
        if mod is not None and mod.get_state() != Module.Status.STOPPED:
            logger.info(f"Stopping module {mod.get_name()}...")

            fireoffFunction(mod.stop)
            while mod.get_state() != Module.Status.STOPPED:
                QTest.qWait(100)

            logger.info("... done.")

    # starts all modules that are not running yet
    def startExperiment(self):

        for mod in self.modules.values():
            if mod is not None and mod.get_state() is Module.Status.STOPPED:
                if not self.startModule(mod):
                    logger.warning(f"Could not start Module {mod.get_name()}. Start of experiment aborted.")
                    return

    # stops all modules one after the other
    def stopExperiment(self):

        for mod in self.modules.values():
            self.stopModule(mod)

    # this function is called automatically when the main window gets closed.
    # it terminates the rest of the program
    def closeEvent(self, event):

        self.stopExperiment()
        logger.info("All modules stopped. Terminating.")
        QTest.qWait(500)
        event.accept()

    # resizes and moves the window on the screen
    def resizeAndPosition(self, left, top, width, height):
        self.move(left, top)
        self.resize(width, height)

    # builds the main window's menubar
    def setupMenu(self):

        menubar = self.menuBar()
        fileMenu = menubar.addMenu('&File')

        action_load_experiment = QtWidgets.QAction("Load Experiment", self)
        action_load_experiment.triggered.connect(self.load_experiment)

        action_save_experiment = QtWidgets.QAction("Save Experiment", self)
        action_save_experiment.triggered.connect(self.save_experiment)

        fileMenu.addAction(action_load_experiment)
        fileMenu.addAction(action_save_experiment)

        toolsMenu = menubar.addMenu('&Tools')

        scripts_dir = pathlib.Path(globals.PYTHONBCI_PATH/"tools"/"analysis")

        if scripts_dir.exists() and scripts_dir.is_dir():
            analysisMenu = toolsMenu.addMenu('&Analysis')

            analysis_scripts = list(scripts_dir.glob("*.py"))
            analysis_scripts.sort()

            for script_path in analysis_scripts:
                action = QtWidgets.QAction(script_path.name[:-3], self)
                action.triggered.connect(lambda *args, script_path=script_path: subprocess.Popen(
                    [sys.executable, str(script_path.resolve())]))
                analysisMenu.addAction(action)

        helpMenu = menubar.addMenu('&Help')

        action_show_about = QtWidgets.QAction(" About BeamBCI", self)
        action_show_about.triggered.connect(self.show_about_info)

        helpMenu.addAction(action_show_about)

    # shows a small window containing information about the BeamBCI
    def show_about_info(self):

        self.about_window = QtWidgets.QWidget()

        lay = QtWidgets.QVBoxLayout()
        lay.setSpacing(20)

        lay.addWidget(HeadlineLabel("BeamBCI"))

        lay.addWidget(BoldLabel("Berlin Adaptable Modular BCI"))

        lay.addWidget(QtWidgets.QLabel("created 2018-2021 by the Clinical Neurotechnology Lab at Charité Berlin."))

        lay.addWidget(BoldLabel("Authors:"))

        lay.addWidget(QtWidgets.QLabel("Niels Peekhaus, Marius Nann, Elisa Bauße, Jan Zerfowski, Annalisa Colucci, Mareike Vermehren"))

        self.about_window.setLayout(lay)
        self.about_window.setWindowTitle("About BeamBCI")

        self.about_window.show()


    def save_experiment(self):
        """
        Saves all loaded Modules and their Parameters into a JSON file
        """

        data = {}

        for mod_type, mod_wrapper in self.modules.items():

            mod_wrapper: QtGuiModuleWrapper
            mod_class = mod_wrapper.module.__class__.__name__ if mod_wrapper is not None else 'None'

            data[mod_type] = {
                'class': mod_class
            }

            param_data = {}

            if mod_wrapper is not None:
                for p_name in mod_wrapper.get_available_parameters():
                    param_data[p_name] = mod_wrapper.get_parameter_value(p_name)

            data[mod_type]['parameters'] = param_data

        pathlib.Path(globals.PYTHONBCI_PATH / 'experiments').mkdir(parents=True, exist_ok=True)

        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Experiment as ...",
                                                        str(globals.PYTHONBCI_PATH / 'experiments'),
                                                        filter="JSON file (*.json)")

        if len(path.strip()) > 4:
            fh = open(path, 'w')
            json.dump(data, fh, indent=4)
            fh.close()
            logger.log(log.SUCCESS, f"Experiment saved to {path}")

    def load_experiment(self, *, path=None):
        """
        Loads a JSON file and sets up Modules and their parameters according to the file.
        """

        if path is None:
            path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Choose Experiment configuration file ...",
                                                            str(globals.PYTHONBCI_PATH / 'experiments'),
                                                            filter="JSON file (*.json)")

        if len(path.strip()) < 5:
            return

        with open(path, 'r') as fh:
            data = json.load(fh)

        for mod_type, mod_data in data.items():
            t = ModuleType(mod_type)
            mod_class = mod_data['class']

            print("Loading", t, mod_class)

            if mod_class:
                self.changeModule(t, mod_class, mod_data['parameters'])

    # builds the GUI out of several components
    def setupGUI(self):

        # Logging area
        self.loglist = QtWidgets.QListWidget()
        lay_logs = QtWidgets.QVBoxLayout()
        lay_logs.addWidget(HeadlineLabel("Logs"))
        lay_logs.addWidget(self.loglist)
        group_log = QtWidgets.QGroupBox()
        group_log.setLayout(lay_logs)

        # main layout
        gridlayout = QtWidgets.QGridLayout()
        gridlayout.setColumnStretch(0, 1)
        gridlayout.setColumnStretch(1, 1)
        gridlayout.setColumnStretch(2, 1)
        gridlayout.setColumnStretch(3, 1)
        gridlayout.setColumnStretch(4, 1)

        gridlayout.setRowStretch(0, 0)
        gridlayout.setRowStretch(1, 4)
        gridlayout.setRowStretch(2, 0)

        gridlayout.setSpacing(main_grid_layout_spacing)
        gridlayout.setContentsMargins(main_grid_layout_margin, main_grid_layout_margin, main_grid_layout_margin, main_grid_layout_margin)


        spacer = QtWidgets.QWidget()
        spacer.setMinimumHeight(0)

        headline = QLabel("BeamBCI Operator GUI")
        headline.setContentsMargins(3, 8, 0, 6)
        headline.setStyleSheet("QLabel{ font-size: 20pt; font-weight: 400; color: white; }")

        btn_start_exp = QPushButton("START experiment")
        btn_start_exp.setStyleSheet("""
            QPushButton{
                font-weight: bold; 
                border-radius: 15px; 
                padding: 5px;
                margin-right: 2px;
                margin-left: 2px;
            }
        """)
        btn_start_exp.clicked.connect(self.startExperiment)

        btn_stop_exp = QPushButton("STOP experiment")
        # btn_stop_exp.setStyleSheet("font-weight: bold; background-color: #e15554; color: #ffffff; border-radius: 5px; padding: 7.5px;")
        btn_stop_exp.setStyleSheet("""
            QPushButton{
                font-weight: bold; 
                border-radius: 15px; 
                padding: 5px;
                margin-right: 2px;
                margin-left: 2px;
            }
        """)
        btn_stop_exp.clicked.connect(self.stopExperiment)

        gridlayout.addWidget(spacer, 0, 2, 1, 1)
        gridlayout.addWidget(headline, 0, 0, 1, 2)
        gridlayout.addWidget(btn_start_exp, 0, 3, 1, 1)
        gridlayout.addWidget(btn_stop_exp, 0, 4, 1, 1)

        # Add all Groupboxes to the Gridlayout
        gridlayout.addWidget(self.setupGUI_SourceMod(), 1, 0, 1, 1)
        gridlayout.addWidget(self.setupGUI_PreprocessingModule(), 1, 1, 1, 1)
        gridlayout.addWidget(self.setupGUI_ClassificationMod(), 1, 2, 1, 1)
        gridlayout.addWidget(self.setupGUI_TaskMod(), 1, 3, 1, 1)
        gridlayout.addWidget(self.setupGUI_FeedbackMod(), 1, 4, 1, 1)

        gridlayout.addWidget(group_log, 2, 0, 1, 2)
        gridlayout.addWidget(self.setupGUI_RecordingMod(), 2, 2, 1, 3)

        return gridlayout

    def setupGUI_Module(self, module_type: ModuleType, headline_label: str) -> QGroupBox:
        module_type_name = module_type.value
        module_path = self.module_paths[module_type_name]
        self.module_layouts[module_type_name] = QtWidgets.QVBoxLayout()
        self.module_layouts[module_type_name].addWidget(HeadlineLabel(headline_label))

        self.module_select_menus[module_type_name] = QtWidgets.QComboBox()
        self.module_select_menus[module_type_name].setMaximumWidth(100)

        available_modules = [x for x in dir(module_path) if
                             x.endswith('Module') and getattr(getattr(module_path, x), x).MODULE_RUNNABLE]

        available_modules.sort()

        reload_button = QPushButton("Reload Module")
        self.module_reload_buttons[module_type_name] = reload_button

        self.module_reload_buttons[module_type_name].clicked.connect(
            lambda: self.reloadModule(module_type,
                                      self.module_select_menus[module_type_name].currentText()))

        reload_button.setVisible(args.dev_mode)

        self.module_select_menus[module_type_name].addItems(['None'] + available_modules)

        self.module_select_menus[module_type_name].activated.connect(
            lambda: self.changeModule(module_type,
                                      self.module_select_menus[module_type_name].currentText()))

        self.module_layouts[module_type_name].addWidget(self.module_select_menus[module_type_name])

        self.module_layouts[module_type_name].addWidget(reload_button)

        self.module_layouts[module_type_name].addWidget(QLabel("No module selected."))

        self.module_layouts[module_type_name].addStretch()

        self.module_layouts[module_type_name].setSpacing(module_layout_spacing)
        self.module_layouts[module_type_name].setContentsMargins(module_layout_margin, module_layout_margin, module_layout_margin, module_layout_margin)

        group_module = QGroupBox()
        group_module.setLayout(self.module_layouts[module_type_name])
        group_module.setContentsMargins(module_groupbox_margin, module_groupbox_margin*2, module_groupbox_margin, module_groupbox_margin)

        return group_module

    def setupGUI_SourceMod(self) -> QGroupBox:
        return self.setupGUI_Module(ModuleType.SOURCE, "Source module<hr />")

    def setupGUI_PreprocessingModule(self) -> QGroupBox:
        return self.setupGUI_Module(ModuleType.PREPROCESSING, "Preprocessing module<hr />")

    def setupGUI_ClassificationMod(self) -> QGroupBox:
        return self.setupGUI_Module(ModuleType.CLASSIFICATION, "Classification module<hr />")

    def setupGUI_TaskMod(self) -> QGroupBox:
        return self.setupGUI_Module(ModuleType.TASK, "Task module<hr />")

    def setupGUI_FeedbackMod(self) -> QGroupBox:
        return self.setupGUI_Module(ModuleType.FEEDBACK, "Feedback module<hr />")

    def setupGUI_RecordingMod(self) -> QGroupBox:

        lay_rec_main = QGridLayout()

        self.module_layouts[ModuleType.RECORDING.value] = QVBoxLayout()
        lay_rec_col2 = QVBoxLayout()
        lay_rec_col3 = QVBoxLayout()

        l1 = HeadlineLabel("Recording module<hr />")
        l1.setFixedHeight(50)
        l2 = QLabel("")
        l2.setFixedHeight(0)
        self.module_layouts[ModuleType.RECORDING.value].addWidget(l1)
        self.module_layouts[ModuleType.RECORDING.value].addWidget(l2)

        reload_button = QPushButton("Reload Module")
        self.module_reload_buttons[ModuleType.RECORDING.value] = reload_button

        self.module_reload_buttons[ModuleType.RECORDING.value].clicked.connect(
            lambda: self.reloadModule(ModuleType.RECORDING, "LabRecorderModule"))

        reload_button.setVisible(args.dev_mode)

        self.module_layouts[ModuleType.RECORDING.value].addWidget(self.module_reload_buttons[ModuleType.RECORDING.value])

        self.module_layouts[ModuleType.RECORDING.value].addWidget(self.modules[ModuleType.RECORDING.value].getGUI())
        self.module_layouts[ModuleType.RECORDING.value].addStretch()

        lay_rec_col2.addWidget(BoldLabel("required LSL streams:"))
        lay_rec_col2.addSpacing(10)
        hlay = QtWidgets.QHBoxLayout()
        self.required_streams = QLabel(
            reduce(lambda l, x: l + x + ":\n\n", globals.RECORD_STREAMS, "")[:-2])
        hlay.addWidget(self.required_streams)
        self.label_streams_required = QLabel((" ... \n\n" * len(globals.RECORD_STREAMS))[:-2])
        hlay.addWidget(self.label_streams_required)
        lay_rec_col2.addLayout(hlay)
        lay_rec_col2.addStretch()

        lay_rec_col3.addWidget(BoldLabel("available LSL streams:"))
        lay_rec_col3.addSpacing(10)
        self.layout_all_lsl_streams = QVBoxLayout()
        self.layout_all_lsl_streams.setSpacing(0)
        self.layout_all_lsl_streams.addWidget(QLabel(" ... "))
        lay_rec_col3.addLayout(self.layout_all_lsl_streams)
        lay_rec_col3.addStretch()

        lay_rec_main.addLayout(self.module_layouts[ModuleType.RECORDING.value], 0, 0, 1, 1)
        lay_rec_main.addLayout(lay_rec_col2, 0, 2, 1, 1)
        lay_rec_main.addLayout(lay_rec_col3, 0, 4, 1, 1)

        lay_rec_main.setColumnStretch(0, 7)
        lay_rec_main.setColumnStretch(1, 1)
        lay_rec_main.setColumnStretch(2, 7)
        lay_rec_main.setColumnStretch(3, 1)
        lay_rec_main.setColumnStretch(4, 7)

        group_rec = QtWidgets.QGroupBox()
        group_rec.setLayout(lay_rec_main)

        return group_rec

    def update_gui_dimensions(self):

        module_widths: List[int] = [
            self.module_layouts[ModuleType.SOURCE.value].itemAt(0).widget().width(),
            self.module_layouts[ModuleType.PREPROCESSING.value].itemAt(0).widget().width(),
            self.module_layouts[ModuleType.CLASSIFICATION.value].itemAt(0).widget().width(),
            self.module_layouts[ModuleType.TASK.value].itemAt(0).widget().width(),
            self.module_layouts[ModuleType.FEEDBACK.value].itemAt(0).widget().width()
        ]

        # width avail = win_w / 5 - additional... - main_grid_spacing*4/5 - main_grid_margin*2/5 - groupbox_margin*2 - ( layout_margin*2 - 12)
        calc_width = self.centralWidget().width()/5
        calc_width -= additional_px_lost_per_module
        calc_width -= main_grid_layout_spacing*4/5
        calc_width -= main_grid_layout_margin*2/5
        calc_width -= module_groupbox_margin*2
        calc_width = int(calc_width)

        #logger.info("Mod width: "+str(module_widths))
        #logger.info("Calc width: "+str(calc_width))
        #logger.info("Window width: "+str(self.centralWidget().width()))


        for mod in self.module_select_menus.values():
            if mod is not None:
                mod.setMaximumWidth(calc_width)

        for type, mod in self.modules.items():
            if type is not ModuleType.RECORDING and mod is not None:
                if mod.gui is not None:
                    mod.gui.setMaximumWidth(calc_width)

    def update_module_guis_secondly(self):

        for type, mod in self.modules.items():
            if mod is not None:
                mod.updateGuiSecondly()

    # fetches all received logs from the log server and displays them in a list view
    def updateLogs(self):
        # Collect all new log records
        records = pbciLogHandler.get_records()

        for record in records:
            # Concatenate the log messages into a single string with all information
            # message = f"{record.time:.2f}s {record.name}: {record.message}"
            message = f"{record.time:.2f}s   {record.message}"

            # Add the message text to a QtWidget (for display) and set the appropriate color depending on log level
            item = QtWidgets.QListWidgetItem(message)
            item.setForeground(QColor(log.LogHexColors[record.levelno]))

            self.loglist.addItem(item)

        # Only scroll to the newest entry when there are new ones:
        if records:
            self.loglist.scrollToBottom()


    # display which LSL streams are available
    def updateLSLStreams(self, stream_infos):
        label_req = reduce(lambda l, x: l + x + ":\n\n",
                           globals.RECORD_STREAMS, "")[:-2]
        self.required_streams.setText(label_req)

        label_text_all: List[str] = []

        stream_names = []

        for info in stream_infos:
            # retrieve streams name, sampling rate, and channel count
            n: str = info.name()
            fs: float = info.nominal_srate()
            ch: int = info.channel_count()

            label_text_all.append('\u2022 {} ({}ch, {}Hz)\n'.format(n, ch, round(fs, 2)))

            stream_names.append(n)

        names_and_labeltexts = list(zip(stream_names, label_text_all))
        names_and_labeltexts.sort()

        for i in reversed(range(self.layout_all_lsl_streams.count())): 
            item = self.layout_all_lsl_streams.itemAt(i)
            self.layout_all_lsl_streams.removeItem(item)
            if isinstance(item, QWidgetItem):
                item.widget().setParent(None)
            if isinstance(item, QHBoxLayout):
                for ii in reversed(range(item.count())):
                    item.itemAt(ii).widget().setParent(None)
        
        from misc.lslviewer_interface import start_lsl_viewer
        from functools import partial
        for n, s in names_and_labeltexts:
            
            label = QLabel(s[:-1])
            button = Button("")
            button.setFixedSize(18, 18)
            button.setIconSize(QtCore.QSize(16, 16))
            button.setIcon(QtGui.QIcon(str(globals.PYTHONBCI_PATH / "img" / "eye_white.png")))
            button.setStyleSheet("""
                                 QPushButton{ border-radius: 7px; font-size: 14px; background-color: rgba(0, 0, 0, 0); }
                                 QPushButton:hover{ background-color: """ + colors[3] + """; }
                                 """)
            button.clicked.connect(partial(start_lsl_viewer, ['-n', n]))

            layout = QHBoxLayout()
            layout.addWidget(label)
            layout.addWidget(button)
            self.layout_all_lsl_streams.addLayout(layout)



        label_text_required = ""
        for n in globals.RECORD_STREAMS:
            if n in stream_names:
                label_text_required += 'ok\n\n'
            else:
                label_text_required += 'missing\n\n'

        label_text_required = label_text_required[:-2]

        self.label_streams_required.setText(label_text_required)


# start the application
if __name__ == "__main__":
    # set environment variable for Qt to automatically adjust to high-DPI displays
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QtWidgets.QApplication(sys.argv)
    app.setWindowIcon(QtGui.QIcon(str(globals.PYTHONBCI_PATH / "img" / "beambci_logo_rounded_256.png")))
    app.setApplicationName("BeamBCI")
    app.setApplicationDisplayName("BeamBCI")

    app.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)  # enable highdpi scaling
    app.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)  # use highdpi icons

    # get the geometries for the MainWindow
    desktopObject = app.desktop()
    left = int(desktopObject.screenGeometry(0).left() + (desktopObject.screenGeometry(0).width() / 10 * 0.5) / 2)
    top = int(desktopObject.screenGeometry(0).top() + (desktopObject.screenGeometry(0).height() / 10 * 1) / 2)
    width = int(desktopObject.screenGeometry(0).width() / 10 * 9.5)
    height = int(desktopObject.screenGeometry(0).height() / 10 * 9)

    # open the main window and start the application
    window = MainWindow(left, top, width, height, True)
    sys.exit(app.exec_())
