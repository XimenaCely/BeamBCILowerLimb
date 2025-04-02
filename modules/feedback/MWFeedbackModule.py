import pathlib
import os
import sys
import time
import subprocess
from PyQt5.QtWidgets import QCheckBox
from pylsl import resolve_byprop

import globals
from modules.module import Module


class MWFeedbackModule(Module):

    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME: str = "Lower-limb Feedback Module"
    MODULE_DESCRIPTION: str = ""
    MODULE_PATH = pathlib.Path(os.path.split(os.path.abspath(__file__))[0])
    APP_PATH = MODULE_PATH / "VNF_KNF_LowerLimb.py"

    REQUIRED_LSL_STREAMS = [globals.STREAM_NAME_TASK_EVENTS]
    print("stream tasks: ",globals.STREAM_NAME_TASK_EVENTS)
    # overwrite parameter definition which is empty by superclass
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
        {
            'name': 'activate_robot',
            'displayname': 'activate robot',
            'description': 'whether to activate or not the robot.',
            'type': bool,
            'unit': '',
            'default': False
        },
        {
            'name': 'window_maximized',
            'displayname': 'window maximized',
            'description': '',
            'type': bool,
            'unit': '',
            'default': True
        },
        {
            'name': 'window_width',
            'displayname': 'window width',
            'description': '',
            'type': int,
            'unit': 'px',
            'default': 1000
        },
        {
            'name': 'window_height',
            'displayname': 'window height',
            'description': '',
            'type': int,
            'unit': 'px',
            'default': 750
        },
        {
            'name': 'window_left',
            'displayname': 'window left',
            'description': '',
            'type': int,
            'unit': 'px',
            'default': 0
        },
        {
            'name': 'window_top',
            'displayname': 'window top',
            'description': '',
            'type': int,
            'unit': 'px',
            'default': 0
        }

    ]


    def __init__(self):
        super(MWFeedbackModule, self).__init__()


        self.set_state(Module.Status.STOPPED)

        self.feedback_app_process = None


    def start(self):

        # do not start up if LSL is not available
        if not globals.LSLAvailable:
            print("LSL is not available.")
            return

        # do not start up if the corresponding app is missing
        if not self.APP_PATH.exists():
            print("Feedback application is missing:", self.APP_PATH)
            return

        # do not start up the module if it was already started
        if self.get_state() != Module.Status.STOPPED:
            print("Module is not in STOPPED state.")
            return

        # set status
        self.set_state(Module.Status.STARTING)


        # fetch available lsl streams
        resolve_task_stream = resolve_byprop("name", globals.STREAM_NAME_TASK_EVENTS, minimum=1, timeout=10)

        # if the required task output stream is not available -> do not start
        if len(resolve_task_stream) < 1:
            self.set_state(Module.Status.STOPPED)
            print("Could not start", self.MODULE_NAME,"because of missing stream:", globals.STREAM_NAME_TASK_EVENTS)
            return

        # start the external app process
        self.start_app()

        # set status
        self.set_state(Module.Status.RUNNING)

    def get_controls(self):
        controls = []

        # Crear un control para cada parámetro
        for param in self.PARAMETER_DEFINITION:
            if param['type'] == bool:
                checkbox = QCheckBox(param['displayname'])
                checkbox.setChecked(param['default'])
                checkbox.stateChanged.connect(lambda state, p=param: self.set_parameter_value(p['name'], bool(state)))
                controls.append(checkbox)

        return controls

    def stop(self):

        # do not stop if not running
        if not self.get_state() in [Module.Status.RUNNING, Module.Status.STARTING]:
            return

        self.set_state(Module.Status.STOPPING)

        # stop the feedback app process
        self.stop_app()

        # reset status
        self.set_state(Module.Status.STOPPED)


    def restart(self):
        self.stop()
        time.sleep(0.2)
        self.start()


    def start_app(self):

        # convert to str: if pyth is not give as string but as Path-Object -> conversion is necessary
        args = [
            sys.executable,
            str(self.APP_PATH),            
            "--maximized="+str(int(self.get_parameter_value('window_maximized'))),
            "--width="+str(self.get_parameter_value('window_width')),
            "--height=" + str(self.get_parameter_value('window_height')),
            "--left=" + str(self.get_parameter_value('window_left')),
            "--top=" + str(self.get_parameter_value('window_top')),
            "--showbar="+str(int(self.parameters['display_bar'].getValue())),
            "--restartbar="+str(int(self.parameters['display_relax'].getValue())),
            "--enrobot="+str(int(self.parameters['activate_robot'].getValue()))
        ]

        print("START FB APP:", args)

        # start the subprocess
        self.feedback_app_process = subprocess.Popen(args, shell=False)
        

    def stop_app(self):
        if self.feedback_app_process is not None:
            self.feedback_app_process.terminate()
            print("Waiting for feedback App to terminate...")
            self.feedback_app_process.wait()
            print("terminated.")
            self.feedback_app_process = None
