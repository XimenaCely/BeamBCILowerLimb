import time
import random
from threading import Thread
from PyQt5.QtWidgets import QPushButton, QLabel, QCheckBox, QLineEdit

import globals
from misc import enums
from misc.timing import clock
from modules.module import Module
from pylsl import StreamInlet, StreamOutlet, StreamInfo, resolve_byprop, IRREGULAR_RATE
from misc.LSLStreamInfoInterface import add_mappings, add_channel_names, add_parameters
from misc.gui import BoldLabel

import serial
from serial.tools import list_ports

from misc import log

logger = log.getLogger("HOHExoModule")
import numpy

class HOHExoModule(Module):
    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME: str = "HOH Exo Control Module"
    MODULE_DESCRIPTION: str = ""
    # MODULE_PATH = pathlib.Path(os.path.split(os.path.abspath(__file__))[0])
    # APP_PATH = MODULE_PATH / "SinglePacmanFeedbackApp.py"

    REQUIRED_LSL_STREAMS = [globals.STREAM_NAME_TASK_EVENTS]

    # parameters of LSL outlet
    OUTPUT_STREAM_NAME = globals.STREAM_NAME_FEEDBACK_STATES
    NUM_OUTPUT_CHANNELS: int = 1
    OUTPUT_CHANNEL_NAMES = ['command_sent']
    OUTPUT_SAMPLING_RATE: float = IRREGULAR_RATE
    OUTPUT_CHANNEL_FORMAT: str = 'int32'




    # overwrite parameter definition which is empty by superclass
    PARAMETER_DEFINITION = [
        {
            'name': 'laterality',
            'displayname': 'Laterality',
            'description': 'On which side (left/right) is the exoskeleton mounted?',
            'type': list,
            'unit': [enums.Side.LEFT.value, enums.Side.RIGHT.value],
            'default': enums.Side.LEFT.value
        },
        {
            'name': 'send_command_length',
            'displayname': 'Maximum movement time',
            'description': '',
            'type': float,
            'unit': 's',
            'default': 7
        },
    ]

    # STATE_READY = 4
    STATE_SEND_CLOSE = 3
    STATE_SEND_OPEN = 2
    STATE_SEND_LOCK = 1
    STATE_STOP = 4
    STATE_START = 0
    STATE_READY = 5

    def __init__(self):

        super(HOHExoModule, self).__init__()
        self.state = None
        self.set_state(Module.Status.STOPPED)

        self.lsl_inlet = None
        self.lsl_outlet = None
        self.lsl_stream_info = None

        self.running = False
        self.datathread = None
        self.socket = None
        self.last_msg_sent = None
        self.last_msg_time = None

        self.mute_output = False

        self.btn = None
        self.bool_pinch = False

        self.time_start_open = 0.5 # short time for sending open command in the ready state
        self.exo_start = False

        self.state_machine_thread = Thread(target=self.state_machine, daemon=True)
        self.state_machine_thread.start()

        self.state_machine_state = 4
        self.state_machine_state_change_time = clock()

        self.last_command_sent_to_exo = b''
        self.last_command_sent_to_exo_time = clock()

        self.list_commands = []
        self.cdc = None

        try:
            self.cdc = next(list_ports.grep("CH340"))

        except:
            pass

        if self.cdc == None:
            logger.error("No dongle found")
        else:
            self.ser = serial.Serial(port=self.cdc.device, baudrate=115200, bytesize=serial.EIGHTBITS, \
                                     parity=serial.PARITY_NONE, \
                                     stopbits=serial.STOPBITS_ONE, timeout=None, xonxoff=False, rtscts=False, \
                                     write_timeout=None, dsrdtr=False, inter_byte_timeout=None, exclusive=None)
            logger.info(f"Dongle detected at port: {self.ser.name}")

    def initGui(self):

        super(HOHExoModule, self).initGui()
        row: int = self.layout.rowCount()

        # entry box for entering a command
        self.state = QLineEdit()

        # push button and connect that to the Action function
        btn_send = QPushButton("Action", clicked = lambda: [self.Action()])
        btn_send.setAutoDefault(True)

        label = QLabel("Enter a command!\n[LOCK: 1, OPEN: 2, CLOSE: 3,CHANGING GRASP MODE: P]")
        label.setWordWrap(True)


        self.layout.addWidget(BoldLabel("Actions"), row + 1, 0, 1, 4)
        self.layout.addWidget(label, row + 6, 0, 1, 5)
        self.layout.addWidget(self.state, row + 7, 0, 1, 1)
        self.layout.addWidget(btn_send, row + 7, 2, 1, 2)

    def send_command_to_exo(self, command=b''):
        self.list_commands.append(command)

        #time since last state change
        time_since_last_command = clock() - self.last_command_sent_to_exo_time

        if time_since_last_command >= 0.2:

            while len(self.list_commands) > 0:

                current_command = self.list_commands.pop(0)

                if current_command == self.last_command_sent_to_exo and time_since_last_command < 3.5:

                    continue

                try:
                    self.ser.write(current_command)
                    self.last_command_sent_to_exo = current_command
                    self.last_command_sent_to_exo_time = clock()
                    if self.lsl_outlet is not None:
                        self.lsl_outlet.push_sample([0], clock())

                except:
                    pass

                break

    def state_machine(self):

        while True:
            time.sleep(0.01)

            time_since_state_change = clock() - self.state_machine_state_change_time

            # start
            if self.state_machine_state == self.STATE_START:

                if self.bool_pinch:
                    self.send_command_to_exo(b'ot')

                else:
                    self.send_command_to_exo(b'os')

                if time_since_state_change > self.time_start_open:
                    self.state_machine_state = self.STATE_STOP
                    self.state_machine_state_change_time = clock()

            # stop
            elif self.state_machine_state == self.STATE_STOP:
                self.send_command_to_exo(b'aa')

            # lock
            elif self.state_machine_state == self.STATE_SEND_LOCK:
                self.send_command_to_exo(b'aa')

            # ready
            elif self.state_machine_state == self.STATE_READY:
                self.send_command_to_exo(b'')


            # close
            elif self.state_machine_state == self.STATE_SEND_CLOSE:
                if self.bool_pinch:
                    self.send_command_to_exo(b'ct')
                else:
                    self.send_command_to_exo(b'cs')

                if time_since_state_change >= self.getParameter('send_command_length'):

                    self.state_machine_state = self.STATE_STOP
                    self.state_machine_state_change_time = clock()


            # open
            elif self.state_machine_state == self.STATE_SEND_OPEN:

                if self.bool_pinch:
                    self.send_command_to_exo(b'ot')
                else:
                    self.send_command_to_exo(b'os')

                if time_since_state_change >= self.getParameter('send_command_length'):
                    self.state_machine_state = self.STATE_STOP
                    self.state_machine_state_change_time = clock()

    # sends a command to the exoskeleton
    def Action(self):

        # close
        if str(self.state.text()) == "3":

            self.state_machine_state = self.STATE_SEND_CLOSE
            self.state_machine_state_change_time = clock()

        # open
        elif str(self.state.text()) == "2":

            self.state_machine_state = self.STATE_SEND_OPEN
            self.state_machine_state_change_time = clock()

        # lock
        elif str(self.state.text()) == "1":
            self.state_machine_state = self.STATE_SEND_LOCK
            self.state_machine_state_change_time = clock()

        # changing the grasp mode
        elif str(self.state.text()) == "p" or str(self.state.text()) == "P":
            if self.bool_pinch == True:
                self.bool_pinch = False
                logger.info(f"The grasp mode was changed to palmar grasp...")

            else:
                self.bool_pinch = True
                logger.info(f"The grasp mode was changed to pinch grip...")

        # # Clear the QLineEdit box
        self.state.setText("")

    def start(self):

        # do not start if the LSL LabRecorder App is not available
        if not globals.LSLAvailable:
            return
        # do not start up the module if it was already started
        if self.status != Module.Status.STOPPED:
            return

        # set status
        self.setStatus(Module.Status.STARTING)
        # fetch necessary lsl stream
        streams = resolve_byprop("name", globals.STREAM_NAME_TASK_EVENTS, minimum=1, timeout=10)

        if len(streams) < 1:
            self.setStatus(Module.Status.STOPPED)
            logger.error(
                f"Could not start {self.MODULE_NAME} because of missing stream: {globals.STREAM_NAME_CLASSIFIED_SIGNAL}")
            return
        # init LSL inlet
        self.lsl_inlet = StreamInlet(streams[0], max_buflen=360, max_chunklen=1, recover=True)

        # create stream info for lsl outlet
        self.lsl_stream_info = StreamInfo(
            self.OUTPUT_STREAM_NAME,
            'mixed',
            self.NUM_OUTPUT_CHANNELS,
            self.OUTPUT_SAMPLING_RATE,
            self.OUTPUT_CHANNEL_FORMAT,
            'uid' + str(random.randint(100000, 999999))
        )
        # add channel names and mappings to stream info
        add_channel_names(self.lsl_stream_info, self.OUTPUT_CHANNEL_NAMES)
        add_mappings(self.lsl_stream_info, ['cues', 'exo_states'], [enums.Cue, enums.ExoState])
        add_parameters(self.lsl_stream_info, self.parameters)
        # init LSL outlet
        self.lsl_outlet = StreamOutlet(self.lsl_stream_info, chunk_size=1)

        # set running true to signal threads to continue running
        self.running = True

        # create thread to handle lsl input
        self.datathread = Thread(target=self.handle_input, daemon=True)
        self.datathread.start()
        # set status
        self.setStatus(Module.Status.RUNNING)


    def stop(self):

        # do not try to stop if not even running
        if self.getStatus() != Module.Status.RUNNING:
            return

        self.setStatus(Module.Status.STOPPING)

        # set the running flag to false which signals threads to stop
        self.running = False

        # stop data thread
        # print(self.MODULE_NAME + ': Waiting for data handling thread to terminate... ')
        logger.info(f"Waiting for data handling thread to terminate...")
        while self.datathread is not None and self.datathread.is_alive():
            time.sleep(0.1)
        print("done.")

        # clear reference to threads
        self.datathread = None

        # close lsl connections
        if self.lsl_inlet is not None:
            self.lsl_inlet.close_stream()
        self.lsl_inlet = None
        self.lsl_outlet = None

        # set status
        self.setStatus(Module.Status.STOPPED)
        logger.info(f"Module {self.MODULE_NAME} stopped")

    def restart(self):
        self.stop()
        time.sleep(0.2)
        self.start()


    def handle_input(self):

        self.last_relevant_exo_state = None

        while self.running:

            in_sample, in_timestamp = self.lsl_inlet.pull_sample(timeout=1)

            if in_sample is not None:

                out_sample, out_timestamp = (None, in_timestamp)  # self.process_data(in_sample, in_timestamp)

                # split the input samples into a readable form
                cue = enums.Cue(in_sample[0])
                left_exo_state = enums.ExoState(in_sample[1])
                right_exo_state = enums.ExoState(in_sample[2])

                # choose the relevant exo-state based on the selected laterality
                relevant_exo_state = None

                if self.getParameter('laterality') == enums.Side.LEFT.value:

                    relevant_exo_state = left_exo_state

                elif self.getParameter('laterality') == enums.Side.RIGHT.value:

                    relevant_exo_state = right_exo_state

                if relevant_exo_state != self.last_relevant_exo_state:

                    #logger.info("RECV:"+relevant_exo_state.name)

                    # send Message
                    if relevant_exo_state == enums.ExoState.OPEN:
                        self.state_machine_state = self.STATE_SEND_OPEN
                        self.state_machine_state_change_time = clock()

                    elif relevant_exo_state == enums.ExoState.CLOSE:
                        self.state_machine_state = self.STATE_SEND_CLOSE
                        self.state_machine_state_change_time = clock()

                    elif relevant_exo_state == enums.ExoState.STOP:
                        self.state_machine_state = self.STATE_STOP
                        self.state_machine_state_change_time = clock()

                    elif relevant_exo_state == enums.ExoState.LOCK:
                        self.state_machine_state = self.STATE_SEND_LOCK
                        self.state_machine_state_change_time = clock()

                    elif relevant_exo_state == enums.ExoState.START:
                        self.state_machine_state = self.STATE_START
                        self.state_machine_state_change_time = clock()

                    elif relevant_exo_state == enums.ExoState.READY:
                        self.state_machine_state = self.STATE_READY
                        self.state_machine_state_change_time = clock()

                self.last_relevant_exo_state = relevant_exo_state

                # if a message was sent to the exoskeleton and thus out_sample is not None -> push a sample documenting the message
                #if out_sample is not None:
                #    self.lsl_outlet.push_sample(out_sample, out_timestamp)

