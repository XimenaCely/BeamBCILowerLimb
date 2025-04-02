import time
import random 
from threading import Thread
from socket import socket, AF_INET, SOCK_STREAM
from PyQt5.QtWidgets import QPushButton, QLabel, QCheckBox

import globals
from misc import enums, log
from misc.timing import clock
from modules.module import Module
from pylsl import StreamInlet, StreamOutlet, StreamInfo, resolve_byprop, IRREGULAR_RATE
from misc.LSLStreamInfoInterface import add_mappings, add_channel_names, add_parameters
from misc.gui import BoldLabel
from misc.enums import WalkExo, Cue, RelaxFeedbackState

import socket
import threading
import json

# ServerSetting
TCP_IP = "192.168.102.1"
TCP_PORT = 50000
UDP_IP = "192.168.102.1"
UDP_PORT = 50000

# Command Dictionary
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

logger = log.getLogger("MW2Module") 

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
        print("command: ", command_key)
        message = json.dumps(commands[command_key])  # JSON Convert
        print(f"message: {message}")
        try:
            message_bytes = message.encode('utf-8') + b'\0'
            print(message_bytes)
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

class MW2Module(Module):

    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True
    
    MODULE_NAME: str = "MW2Module"
    MODULE_DESCRIPTION: str = ""
    # MODULE_PATH = pathlib.Path(os.path.split(os.path.abspath(__file__))[0])
    # APP_PATH = MODULE_PATH / "SinglePacmanFeedbackApp.py"

    REQUIRED_LSL_STREAMS = [globals.STREAM_NAME_TASK_EVENTS]

    # parameters of LSL outlet
    NUM_OUTPUT_CHANNELS: int = 1
    OUTPUT_CHANNEL_NAMES = ['command_sent']
    OUTPUT_SAMPLING_RATE: float = IRREGULAR_RATE
    OUTPUT_CHANNEL_FORMAT: str = 'int32'

    # overwrite parameter definition which is empty by superclass
    PARAMETER_DEFINITION = [
        {
            'name': 'exo_ip',
            'displayname': 'Exoskeleton IP address',
            'description': '',
            'type': str,
            'unit': '',
            'default': '192.168.102.1'
        },
        {
            'name': 'exo_port',
            'displayname': 'Exoskeleton port',
            'description': '',
            'type': int,
            'unit': '',
            'default': 50000
        }

    ]

    # exo commands
    EXO_COMMAND_NONE = "Stop"
    EXO_COMMAND_WALK = "Ground Walking"
    EXO_COMMAND_STAIR_UP = "Stair Up"
    EXO_COMMAND_STAIR_DOWN = "Stair Down"
    EXO_COMMAND_SLOPE_UP = "Slope Up"
    EXO_COMMAND_SLOPE_DOWN = "Slope Down"
    EXO_COMMAND_SPEED_UP = "Speed Up"
    EXO_COMMAND_SPEED_DOWN = "Speed Down"
    EXO_COMMAND_PAUSE = "Pause"
    EXO_COMMAND_CONTINUE = "Continue"
    

    def __init__(self):

        super(MW2Module, self).__init__()
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

        self.client = None
        self.connected = False


    def initGui(self):
        super(MW2Module, self).initGui()

        row: int = self.layout.rowCount()

        label = QLabel("These controls allow to send close and open commands manually. Be aware that these commands are sent without checking the current state of the exoskeleton and are not recorded in the experiments data.")
        label.setWordWrap(True);

        label1 = QLabel("Check this box to disable any reaction to the BCI signal. The button for manual control above will still work.")
        label1.setWordWrap(True);


        self.checkbox_mute = QCheckBox("ignore control commands")



        self.layout.addWidget(BoldLabel("Actions"), row, 0, 1, 4)
        self.layout.addWidget(label, row+1, 0, 1, 5)
        self.layout.addWidget(label1, row+3, 0, 1, 5)
        self.layout.addWidget(self.checkbox_mute, row+4, 0, 1, 5)

    def start(self):
        
        # do not start if the LSL LabRecorder App is not available
        if not globals.LSLAvailable:
            return

        # do not start up the module if it was already started
        if self.state != Module.Status.STOPPED:
            return

        # set status
        self.set_state(Module.Status.STARTING)

        
        # connect to exo's electronic box
        try:
            
            self.tcp_client = TCPClient()
            self.udp_client = None
            self.is_connected = False

            self.tcp_client.connect()
            self.udp_client = UDPClient()
            self.is_connected = self.tcp_client.connected
            # send initial zero
            self.tcp_client.send_message(self.EXO_COMMAND_NONE)
            
        except Exception:
            self.set_state(Module.Status.STOPPED)
            
            self.tcp_client.disconnect()
            if self.udp_client:
                self.udp_client.disconnect()
            
            self.is_connected = False
            logger.error(f"Could not start {self.MODULE_NAME} because exoskeleton could not be connected.")
            return
        

        # fetch necessary lsl stream
        streams = resolve_byprop("name", globals.STREAM_NAME_TASK_EVENTS, minimum=1, timeout=10)
        
        if len(streams) < 1:
            
            self.tcp_client.disconnect()
            if self.udp_client:
                self.udp_client.disconnect()
            self.is_connected = False
            
            self.set_state(Module.Status.STOPPED)
            logger.error(f"Could not start {self.MODULE_NAME} because of missing stream: {globals.STREAM_NAME_CLASSIFIED_SIGNAL}")
            return
        

        # init LSL inlet
        self.lsl_inlet = StreamInlet(streams[0], max_buflen=360, max_chunklen=1, recover=True)

        # create stream info for lsl outlet
        self.lsl_stream_info = StreamInfo(
            globals.STREAM_NAME_FEEDBACK_STATES,
            'mixed',
            self.NUM_OUTPUT_CHANNELS,
            self.OUTPUT_SAMPLING_RATE,
            self.OUTPUT_CHANNEL_FORMAT,
            'uid'+str(random.randint(100000, 999999))
        )

        # add channel names and mappings to stream info
        add_channel_names(self.lsl_stream_info, self.OUTPUT_CHANNEL_NAMES)
        # add_mappings(self.lsl_stream_info, ['cues', 'exo_states'], [enums.Cue, enums.WalkExo])
        add_parameters(self.lsl_stream_info, self.parameters)

        # init LSL outlet
        self.lsl_outlet = StreamOutlet(self.lsl_stream_info, chunk_size=10)


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
        
        # close TCP connection to exoskeleton
        self.tcp_client.disconnect()
        if self.udp_client:
            self.udp_client.disconnect()
        is_connected = False
        
    
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


    # sends a TCP message to the exoskeleton
    def sendMessage(self, msg: bytes) -> bool:
        try:
            self.tcp_client.send_message(msg)
            print("Sending message to robot: ",msg)
        except Exception:
            return False


    def handle_input(self):

        while self.running:            
            in_sample, in_timestamp = self.lsl_inlet.pull_sample(timeout=1)      
            print("in_sample: ", in_sample) 
            if in_sample is not None:     
                ###########################################################BCI CONTROL#########################################################           
                                
                if in_sample[4] == "CONTINUE":
                    self.sendMessage(self.EXO_COMMAND_CONTINUE)
                
                elif in_sample[4] == "PAUSE":
                    self.sendMessage(self.EXO_COMMAND_PAUSE)
                
                ###########################################################CUE CONTROL#########################################################                
                if in_sample[3] == "START_EXO":#NOT NECESSARY TO START THE ROBOT WITHOUT BCI CONTROL
                    self.sendMessage(self.EXO_COMMAND_WALK)
                
                elif in_sample[3] == "RELAX":           #forced to stop-- forced to relax, and imagine again in the new trial
                    self.sendMessage(self.EXO_COMMAND_PAUSE)
                
                elif in_sample[3] == "END":             # forced to stop--end of the experiment
                    self.sendMessage(self.EXO_COMMAND_NONE)
               
                
                
