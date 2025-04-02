# from PyQt5.QtWidgets import QPushButton, QLabel, QCheckBox, QLineEdit, QWidget
import time
import globals
from modules.module import Module

from misc import log

logger = log.getLogger("HOHExoAndVisualFeedbackModule")

from modules.feedback import HOHExoModule, SinglePacmanFeedbackModule


class HOHExoAndVisualFeedbackModule(Module):
    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME: str = "HOH Exo and Visual Feedback Module"
    MODULE_DESCRIPTION: str = ""

    REQUIRED_LSL_STREAMS = [globals.STREAM_NAME_TASK_EVENTS]

    def __init__(self):

        super().__init__()
        self.setStatus(Module.Status.STOPPED)

        self.module_1 = SinglePacmanFeedbackModule.SinglePacmanFeedbackModule()
        self.module_2 = HOHExoModule.HOHExoModule()
        self.module_2.OUTPUT_STREAM_NAME = "TESTSTREAMNAME"

    def initGui(self):
        super().initGui()

        row: int = self.layout.rowCount()

        self.module_1_gui = self.module_1.getGUI()
        self.module_2_gui = self.module_2.getGUI()


        #self.layout.addWidget(BoldLabel("Actions"), row + 1, 0, 1, 4)

        self.layout.addWidget(self.module_1_gui, row+1, 0, 4, 4)
        self.layout.addWidget(self.module_2_gui, row + 5, 0, 4, 4)





    def start(self):

        # do not start up the module if it was already started
        if self.module_1.getStatus() != Module.Status.STOPPED or self.module_2.getStatus() != Module.Status.STOPPED:
            return

        # set status
        self.setStatus(Module.Status.STARTING)

        logger.info("Starting SinglePacmanFeedbackModule...")
        self.module_1.start()
        logger.info("Starting HOHExoModule...")
        self.module_2.start()
        logger.info("... both started.")

        # set status
        self.setStatus(Module.Status.RUNNING)

    def stop(self):

        # do not try to stop if not even running
        if self.getStatus() != Module.Status.RUNNING:
            return

        self.setStatus(Module.Status.STOPPING)

        self.module_1.stop()
        self.module_2.stop()

        # set status
        self.setStatus(Module.Status.STOPPED)
        logger.info(f"Module {self.MODULE_NAME} stopped")

    def restart(self):
        self.stop()
        time.sleep(0.2)
        self.start()

