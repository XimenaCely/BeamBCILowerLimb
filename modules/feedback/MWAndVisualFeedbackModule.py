# from PyQt5.QtWidgets import QPushButton, QLabel, QCheckBox, QLineEdit, QWidget
import time
import globals
from modules.module import Module

from misc import log

logger = log.getLogger("MWAndVisualFeedbackModule")

from modules.feedback import MW2Module, ProgressBarLowerLimbFeedbackModule


class MWAndVisualFeedbackModule(Module):
    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME: str = "MW and Visual Feedback Module"
    MODULE_DESCRIPTION: str = ""

    REQUIRED_LSL_STREAMS = [globals.STREAM_NAME_TASK_EVENTS]
    PARAMETER_DEFINITION = [
        {
            'name': 'display_bar',
            'displayname': 'display bar',
            'description': 'whether to show or to hide the bar representing the controlled hand/exoskeleton',
            'type': bool,
            'unit': '',
            'default': False
        },
        {
            'name': 'display_relax',
            'displayname': 'display relax feedback',
            'description': 'whether to show or hide the relax cue text and present a colour changing ball as feedback.',
            'type': bool,
            'unit': '',
            'default': False
        },
    ]
    def __init__(self):

        super().__init__()
        self.set_state(Module.Status.STOPPED)

        self.module_1 = ProgressBarLowerLimbFeedbackModule.ProgressBarLowerLimbFeedbackModule()
        self.module_2 = MW2Module.MW2Module()
        self.module_2.OUTPUT_STREAM_NAME = "TESTSTREAMNAME"

        
    
    def start(self):

        # do not start up the module if it was already started
        if self.module_1.get_state() != Module.Status.STOPPED or self.module_2.get_state() != Module.Status.STOPPED:
            return

        # set status
        self.set_state(Module.Status.STARTING)

        self.module_1.parameters['display_bar'].setValue(self.parameters['display_bar'].getValue())
        self.module_1.parameters['display_relax'].setValue(self.parameters['display_relax'].getValue())

        logger.info("Starting ProgressBarLowerLimbFeedbackModule...")
        self.module_1.start()
        logger.info("Starting MWModule...")
        self.module_2.start()
        logger.info("... both started.")


        # set status
        self.set_state(Module.Status.RUNNING)

    def stop(self):

        # do not try to stop if not even running
        if self.get_state() != Module.Status.RUNNING:
            return

        self.set_state(Module.Status.STOPPING)

        self.module_1.stop()
        self.module_2.stop()

        # set status
        self.set_state(Module.Status.STOPPED)
        logger.info(f"Module {self.MODULE_NAME} stopped")

    def restart(self):
        self.stop()
        time.sleep(0.2)
        self.start()

