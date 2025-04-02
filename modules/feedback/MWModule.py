# Morning Walk (MW) module to control the robot using brain signals. This module is based on HOHExoModule.py
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
from misc import log

#MW libraries - communication
import socket
import threading
import json

logger = log.getLogger("MWModule")
import numpy

# ServerSetting
TCP_IP = "192.168.102.1"
TCP_PORT = 50000
UDP_IP = "192.168.102.1"
UDP_PORT = 50000

commands = {
    "Pause": {"Command": "Pause"},
    "Continue": {"Command": "Continue"},
    "Stop": {"Command": "Stop"},
    "Ground Walking": {"Command": "Ground Walking"},
    "Stair Up": {"Command": "Stair Up"},
    "Stair Down": {"Command": "Stair Down"},
    "Slope Up": {"Command": "Slope Up"},
    "Slope Down": {"Command": "Slope Down"},
    "Speed Up": {"Command": "Speed Up"},
    "Speed Down": {"Command": "Speed Down"},    
}

class TCPClient:
    def __init__(self):
        self.client = None
        self.connected = False

    def connect(self):
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((TCP_IP, TCP_PORT))
            self.connected = True
            print("Connected to TCP server.")
            threading.Thread(target=self.receive_data, daemon=True).start()
        except Exception as e:
            print(f"TCP Connection failed: {e}")

    def send_message(self, command_key):
        if command_key not in commands:
            print("Invalid command.")
            return

        message = json.dumps(commands[command_key])  # JSON Convert
        logger.info(f"message: {message}")
        try:
            message_bytes = message.encode('utf-8') + b'\0'
            self.client.sendall(message_bytes)
            # print(f"Sent (TCP): {message}")
        except Exception as e:
            print(f"TCP Send error: {e}")

    def receive_data(self):
        try:
            while self.connected:
                data = self.client.recv(4096)
                if data:
                    message = data.decode('utf-8').strip()
                    print(f"📩 TCP Received: {message}")
        except Exception as e:
            print(f"TCP Receive error: {e}")

    def disconnect(self):
        if self.client:
            self.client.close()
        self.connected = False
        print("TCP Disconnected.")

class UDPClient:
    def __init__(self):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client.connect((UDP_IP, UDP_PORT))
        self.client.sendall(b"Connect UdpServer!")
        print("Connected to UDP server.")
        threading.Thread(target=self.receive_data, daemon=True).start()

    def receive_data(self):
        try:
            while True:
                data, _ = self.client.recvfrom(4096)
                if data:
                    message = data.decode('utf-8').strip()
                    # print(f"UDP Received: {message}")
        except Exception as e:
            print(f"UDP Receive error: {e}")

    def disconnect(self):
        self.client.close()
        print("UDP Disconnected.")

def get_command_message(command):
    return json.dumps({"Command": command})

class MWModule(Module):
    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME: str = "MW Control Module"
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
            'name': 'send_command_length',
            'displayname': 'Maximum movement time',
            'description': '',
            'type': float,
            'unit': 's',
            'default': 5
        },
    ]

    """
    STATE_SEND_PAUSE = "Pause"
    STATE_SEND_CONTINUE = "Continue"
    STATE_SEND_STOP = "Stop"
    STATE_SEND_GROUND_WALKING = "Ground Walking"
    STATE_SEND_STAIR_UP = "Stair Up"
    STATE_SEND_STAIR_DOWN = "Stair Down"
    STATE_SEND_SLOPE_UP = "Slope Up"
    STATE_SEND_SLOPE_DOWN = "Slope Down"
    STATE_SEND_SPEED_UP = "Speed Up"
    STATE_SEND_SPEED_DOWN = "Speed Down"
    STATE_SEND_CONNECT = "connect"
    """
    STATE_SEND_WALKING =2
    STATE_SEND_SPEEDDOWN = 3
    STATE_SEND_SPEEDUP = 4
    STATE_SEND_LOCK = 1
    STATE_STOP = 5
    STATE_START = 0
    STATE_READY = 6

    def __init__(self):

        super(MWModule, self).__init__()
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

        self.state_machine_state = self.STATE_STOP
        self.state_machine_state_change_time = clock()

        self.last_command_sent_to_exo = b''                 # check this value after
        self.last_command_sent_to_exo_time = clock()

        self.list_commands = []
        self.cdc = None

        #Init MW communication
        self.tcp_client = TCPClient()
        logger.info(f"Connected to TCP server.")
        udp_client = None
        is_connected = False
        
    def initGui(self):

        super().initGui()
        row: int = self.layout.rowCount()

        # entry box for entering a command
        self.state = QLineEdit()

        # push button and connect that to the Action function
        btn_send = QPushButton("Action", clicked = lambda: [self.Action()])
        btn_send.setAutoDefault(True)

        label = QLabel("Enter a command!\n[GROUND WALKING: Ground Walking, PAUSE: Pause, SPEED UP: Speed Up, SPEED DOWN: Speed Down]")
        label.setWordWrap(True)


        self.layout.addWidget(BoldLabel("Actions"), row + 1, 0, 1, 4)
        self.layout.addWidget(label, row + 6, 0, 1, 5)
        self.layout.addWidget(self.state, row + 7, 0, 1, 1)
        self.layout.addWidget(btn_send, row + 7, 2, 1, 2)

    def send_command_to_MW(self, command=""):
        self.list_commands.append(command)

        #time since last state change
        time_since_last_command = clock() - self.last_command_sent_to_exo_time

        if time_since_last_command >= 0.2:

            while len(self.list_commands) > 0:

                current_command = self.list_commands.pop(0)

                if current_command == self.last_command_sent_to_exo and time_since_last_command < 3.5:

                    continue

                try:
                    self.tcp_client.send_message(current_command)
                    logger.info(f"Current command {current_command} sent")
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
                # connect to MW
                self.tcp_client.connect()
                self.udp_client = UDPClient()
                is_connected = self.tcp_client.connected

            # stop
            elif self.state_machine_state == self.STATE_STOP:
                self.send_command_to_MW("Stop")


            # lock
            elif self.state_machine_state == self.STATE_SEND_LOCK:
                self.send_command_to_MW("Pause")

            # walking
            elif self.state_machine_state == self.STATE_SEND_WALKING:
                self.send_command_to_MW("Ground Walking")

            #Speed up
            elif self.state_machine_state == self.STATE_SEND_SPEEDUP:
                self.send_command_to_MW("Speed Up")
                if time_since_state_change >= self.get_parameter_value('send_command_length'):

                    self.state_machine_state = self.STATE_STOP
                    self.state_machine_state_change_time = clock()
            
            #Speed down
            elif self.state_machine_state == self.STATE_SEND_SPEEDDOWN:
                self.send_command_to_MW("Speed Down")
                if time_since_state_change >= self.get_parameter_value('send_command_length'):

                    self.state_machine_state = self.STATE_STOP
                    self.state_machine_state_change_time = clock()

    # sends a command to the robot
    def Action(self):

        # walking
        if str(self.state.text()) == "walking":

            self.state_machine_state = self.STATE_STOP
            self.state_machine_state_change_time = clock()

        # speed up
        elif str(self.state.text()) == "speed up":

            self.state_machine_state = self.STATE_SEND_SPEEDUP
            self.state_machine_state_change_time = clock()

        # speed down
        elif str(self.state.text()) == "speed down":

            self.state_machine_state = self.STATE_SEND_SPEEDDOWN
            self.state_machine_state_change_time = clock()

        # lock
        elif str(self.state.text()) == "pause":
            self.state_machine_state = self.STATE_SEND_LOCK
            self.state_machine_state_change_time = clock()
        
        # stop
        elif str(self.state.text()) == "stop":
            self.state_machine_state = self.STATE_STOP
            self.state_machine_state_change_time = clock()

        # # Clear the QLineEdit box
        self.state.setText("")

    def start(self):

        # do not start if the LSL LabRecorder App is not available
        if not globals.LSLAvailable:
            return
        # do not start up the module if it was already started
        if self.get_state != Module.Status.STOPPED:     #is it correct with get_state?
            return

        # set status
        self.set_state(Module.Status.STARTING)
        # fetch necessary lsl stream
        streams = resolve_byprop("name", globals.STREAM_NAME_TASK_EVENTS, minimum=1, timeout=10)

        if len(streams) < 1:
            self.set_state(Module.Status.STOPPED)
            logger.error(
                f"Could not start {self.MODULE_NAME} because of missing stream: {globals.STREAM_NAME_CLASSIFIED_SIGNAL}")
            return
        # init LSL inlet
        self.lsl_inlet = StreamInlet(streams[0], max_buflen=360, max_chunklen=1, recover=True)
        logger.info(f"stream input {streams[0]}")
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
        add_mappings(self.lsl_stream_info, ['cues', 'walk_states'], [enums.Cue, enums.WalkExo])
        add_parameters(self.lsl_stream_info, self.parameters)
        # init LSL outlet
        self.lsl_outlet = StreamOutlet(self.lsl_stream_info, chunk_size=1)

        # set running true to signal threads to continue running
        self.running = True

        # create thread to handle lsl input
        self.datathread = Thread(target=self.handle_input, daemon=True)
        self.datathread.start()
        # set status
        self.set_state(Module.Status.RUNNING)


    def stop(self):

        # do not try to stop if not even running
        if self.get_state() != Module.Status.RUNNING:
            return

        self.set_state(Module.Status.STOPPING)

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
        self.set_state(Module.Status.STOPPED)
        logger.info(f"Module {self.MODULE_NAME} stopped")

    def restart(self):
        self.stop()
        time.sleep(0.2)
        self.start()


    def handle_input(self):

        while self.running:

            in_sample, in_timestamp = self.lsl_inlet.pull_sample(timeout=1)

            if in_sample is not None:

                out_sample, out_timestamp = (None, in_timestamp)  # self.process_data(in_sample, in_timestamp)

                # split the input samples into a readable form
                cue = enums.Cue(in_sample[0])
                logger.info(f"in_sample {in_sample[0]}")
                relevant_exo_state = None

                # send Message
                if relevant_exo_state == enums.WalkExo.INC_VEL:
                    self.state_machine_state = self.STATE_SEND_SPEEDUP
                    self.state_machine_state_change_time = clock()

                elif relevant_exo_state == enums.WalkExo.DEC_VEL:
                    self.state_machine_state = self.STATE_SEND_SPEEDDOWN
                    self.state_machine_state_change_time = clock()

                elif relevant_exo_state == enums.WalkExo.STOP:
                    self.state_machine_state = self.STATE_STOP
                    self.state_machine_state_change_time = clock()

                elif relevant_exo_state == enums.WalkExo.HIDE_WALK:         #Check this condition to which refers to?
                    self.state_machine_state = self.STATE_SEND_LOCK
                    self.state_machine_state_change_time = clock()

                elif relevant_exo_state == enums.WalkExo.WALK:
                    self.state_machine_state = self.STATE_SEND_WALKING
                    self.state_machine_state_change_time = clock()

                elif relevant_exo_state == enums.WalkExo.RESET:
                    self.state_machine_state = self.STATE_SEND_LOCK
                    self.state_machine_state_change_time = clock()
