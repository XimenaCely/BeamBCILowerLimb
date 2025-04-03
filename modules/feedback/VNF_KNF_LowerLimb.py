import sys, time
import PyQt5 as Qt
from PyQt5 import QtCore, QtGui
from PyQt5.QtWidgets import QWidget, QApplication, QMainWindow, QGridLayout
# import simpleaudio as sa
from threading import Thread
import random
import os
import argparse

import pathlib
curpath = pathlib.Path(os.path.split(os.path.abspath(__file__))[0])
modules_path = curpath.parent
pybci_path = modules_path.parent
sys.path.append(str(modules_path))
sys.path.append(str(pybci_path))

import globals
from pylsl import StreamInlet, StreamOutlet, StreamInfo, resolve_byprop
from misc.enums import Side, Cue, DisplayText, WalkExo, RelaxFeedbackState
from modules.module import Module
from misc import LSLStreamInfoInterface

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
            self.connected = False
            print(f"TCP Connection failed: {e}")

    def send_message(self, command_key):
        if command_key not in commands:
            print("Invalid command.")
            return
        print("command: ", command_key)
        message = json.dumps(commands[command_key])  # JSON Convert
        print(f"message: {message}")
        if self.connected:
            try:
                message_bytes = message.encode('utf-8') + b'\0'
                print(message_bytes)
                self.client.sendall(message_bytes)
                # print(f"Sent (TCP): {message}")
            except Exception as e:
                print(f"TCP Send error: {e}")
        else:
            print("TCP Client not connected.")

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

class TextWidget(QWidget):

    def __init__(self):

        super(TextWidget, self).__init__()

        self.visible = True

        self.text_lines = []

        self.color = QtGui.QColor(255, 255, 255)


    def paintEvent(self, e):

        if self.visible:
            qp = QtGui.QPainter()
            qp.begin(self)
            self.drawText(qp)
            qp.end()


    def drawText(self, qp):

        size = self.size()
        w = size.width()
        h = size.height()

        fontdiv = 8

        if len(self.text_lines) == 1 and len(self.text_lines[0]) < 4:
            fontdiv = 2
        elif len(self.text_lines) == 1 and len(self.text_lines[0]) <= 12:
            fontdiv = 4

        font = qp.font()
        font.setPixelSize(int(round(h/fontdiv)))
        qp.setFont(font)
        qp.setPen(self.color)

        for i in range(len(self.text_lines)):
            qp.drawText(0, 0+int(round(i*h/(fontdiv-3))), w, h, QtCore.Qt.AlignHCenter, self.text_lines[i])

    def setText(self, text: str):
        self.text_lines = text.split("\n")


class RelaxFeedbackWidget(QWidget):
    GOOD_COLOR = Qt.QtGui.QColor(100, 200, 255)
    BAD_COLOR = Qt.QtGui.QColor(255, 200, 50)
    
    def __init__(self):
        super().__init__()

        self.visible: bool = True
        self.enabled: bool = True

        self.relax_value = 1.0
        self.state: int = Cue.EMPTY.value

        self.background = Qt.QtGui.QColor(0, 0, 0)
        self.color = Qt.QtGui.QColor(0, 0, 0)

    def updateStates(self):

        if self.state == Cue.RELAX.value:
            value = self.relax_value

            if value > 1:
                value = 1
            elif value < 0:
                value = 0

            value = value*0.8+0.2

            # mix colors
            self.color.setRed(int(round(
                self.GOOD_COLOR.red()*value + self.BAD_COLOR.red()*(1-value)
            )))
            self.color.setGreen(int(round(
                self.GOOD_COLOR.green()*value + self.BAD_COLOR.green()*(1-value)
            )))
            self.color.setBlue(int(round(
                self.GOOD_COLOR.blue()*value + self.BAD_COLOR.blue()*(1-value)
            )))

    def paintEvent(self, e):

        self.updateStates()

        if self.visible and self.state == Cue.RELAX.value:
            qp = QtGui.QPainter()
            qp.begin(self)
            self.drawRelax(qp)
            qp.end()
      
    def drawRelax(self, qp):

        size = self.size()
        w = size.width()
        h = size.height()

        gr = Qt.QtGui.QRadialGradient(0.5, 0.5, 0.5)
        gr.setCoordinateMode(Qt.QtGui.QRadialGradient.ObjectBoundingMode)

        gr.setColorAt(1, self.background)
        if self.enabled:
            gr.setColorAt(0, self.color)
        else:
            gr.setColorAt(0, self.background)

        br = Qt.QtGui.QBrush(gr)
        qp.setBrush(br)

        qr_size = min(w, h)
        radius = qr_size/2
        qp.fillRect(int(round(w/2-radius)), int(round(h/2-radius)), qr_size, qr_size, br)

class PacmanWidget(QWidget):

    DEFAULT_COLOR = QtGui.QColor(255, 200, 100)
    RELAX_COLOR = QtGui.QColor(100, 200, 255)
    DISABLED_COLOR = QtGui.QColor(100, 100, 100)
    BACKGROUND_COLOR = QtGui.QColor(255, 0, 0)

    UP_DOWN_PERCENT_PER_SEC: float = 25

    def __init__(self, rotation: int = 0, color: QtGui.QColor = DEFAULT_COLOR):
        super(PacmanWidget, self).__init__()

        self.rotation = rotation
        self.color = color

        self.visible: bool = True
        self.enabled: bool = True

        self.minimum_value: float = 1.0
        self.up_down_percent: float = self.minimum_value

        self.lastUpdate = time.time()

        self.state: int = WalkExo.STOP.value


    def updateStates(self):

        t = time.time()
        dt = t - self.lastUpdate

        self.lastUpdate = t
        #print("up_down_percent: ",self.UP_DOWN_PERCENT_PER_SEC)
        #print("state: ",self.state)
        if self.state in (WalkExo.WALK.value, WalkExo.HIDE_WALK.value):  
            #print("Entered state")
            self.up_down_percent += dt * self.UP_DOWN_PERCENT_PER_SEC
            self.up_down_percent = max(self.minimum_value, min(100, self.up_down_percent))
        elif self.state == WalkExo.RESET.value:
            self.up_down_percent = self.minimum_value
        #else:
            #print("Not entered to state")

    def paintEvent(self, e):

        self.updateStates()

        if self.visible and self.state not in [WalkExo.HIDE_STOP.value, WalkExo.HIDE_WALK.value, WalkExo.RESET.value]:
            qp = QtGui.QPainter()
            qp.begin(self)
            self.drawBar(qp)
            qp.end()

    ## function draw a bar!!!
    def drawBar(self, qp):
        size = self.size()
        w = size.width()
        h = size.height()
        
        if self.enabled:
            qp.setPen(self.color)
            qp.setBrush(self.color)
        else:
            qp.setPen(self.DISABLED_COLOR)
            qp.setBrush(self.DISABLED_COLOR)
        
        bar_width = w * 0.3 
        bar_height = (self.up_down_percent / 100) * h  # Change height based on performance
        # print("bar height: ", bar_height)
        bar_x = w / 2 - bar_width / 2
        bar_y = h - bar_height  # Start since the bottom part
        bar_value = 0
        # print("bar value inside function: ",self.up_down_percent, "bar height: ",bar_height)
        qp.drawRect(int(bar_x), int(bar_y), int(bar_width), int(bar_height))

class VNF_KNF_LowerLimb(QMainWindow):

    OUTPUT_CHANNEL_NAMES: list = ["progress bar"]
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

    def __init__(self, left, top, width=1000, height=700, fullscreen=False, maximized=False, frameless=False, display_bar: bool = True,  display_relax: bool = False, display_activate_robot: bool = False):

        super(VNF_KNF_LowerLimb, self).__init__()

        self.display_bar = display_bar
        self.display_relax = display_relax
        self.display_activate_robot = display_activate_robot

        self.parameters = {            
            "display bar": Module.Parameter("display_bar", "display bar", bool, self.display_bar, "", ""),
            "display relax": Module.Parameter("display_relax", "display_relax", bool, self.display_relax, "", ""),
            "display activate robot": Module.Parameter("display_activate_robot", "display_activate_robot", bool, self.display_activate_robot, "", "")
        }


        # states
        self.state_display_text: int = 0
        self.state_bar: int = 0
        self.state_exo: str = "none"
        self.trigger_exo: str = "none"

        #activate communication        
        self.client = None
        self.connected = False
        
        if self.display_activate_robot:
            # connect to exo's electronic box
            if self.connected:            
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
                    self.tcp_client.disconnect()
                    if self.udp_client:
                        self.udp_client.disconnect()                
                    self.is_connected = False
                    return
        

        # flag to allow external process to close the window
        self.close_sheduled = False

        # lsl setup
        streams = resolve_byprop("name", globals.STREAM_NAME_TASK_EVENTS, minimum=1, timeout=3)
        
        if len(streams) < 1:
            
            if self.display_activate_robot:
                if self.connected:
                    self.tcp_client.disconnect()
                    if self.udp_client:
                        self.udp_client.disconnect()
                    self.is_connected = False
            
            print("Missing LSL stream")
            sys.exit()
        self.lsl_inlet = StreamInlet(streams[0], max_buflen=360, max_chunklen=1, recover=True)
        
        if self.display_relax:
            streams = resolve_byprop("name", globals.STREAM_NAME_CLASSIFIED_SIGNAL, minimum=1, timeout=3)
            if len(streams) < 1:
                print("Missing LSL stream")
                sys.exit()
            self.class_lsl_inlet = StreamInlet(streams[0], max_buflen=360, max_chunklen=1, recover=True)

        self.lsl_stream_info = StreamInfo(
            globals.STREAM_NAME_FEEDBACK_STATES,
            'mixed',
            1, #self.NUM_OUTPUT_CHANNELS,
            globals.FEEDBACK_FRAMERATE,
            'float32', # self.CHANNEL_FORMAT,
            globals.STREAM_NAME_FEEDBACK_STATES+str(random.randint(100000, 999999))
        )
        LSLStreamInfoInterface.add_channel_names(self.lsl_stream_info, self.OUTPUT_CHANNEL_NAMES)
        LSLStreamInfoInterface.add_parameters(self.lsl_stream_info, self.parameters)

        self.lsl_outlet = StreamOutlet(self.lsl_stream_info, chunk_size=10)

        # data handling threads
        self.data_thread = Thread(target=self.data_handler, daemon=True)
        self.data_thread.start()

        self.setWindowTitle("BeamBCI Feedback App")
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint) if frameless else None
        self.move(left, top)

        # create a main widget with black background
        self.mainwidget = QWidget()
        self.mainwidget.setStyleSheet("QWidget{ background-color: #000000; }")
        self.setCentralWidget(self.mainwidget)

        # create pacman widgets
        self.bar = PacmanWidget()
        self.bar_relax = PacmanWidget(color=PacmanWidget.RELAX_COLOR)


        # create relax widget
        if self.display_relax:
            self.relax_widget = RelaxFeedbackWidget()

        # create text display widget
        self.text_widget = TextWidget()
        self.text_widget.setText("")

        # create a grid layout and set all rows and columns to have equal size
        lay = QGridLayout()
        for i in range(10):
            lay.setColumnStretch(i, 1)
            lay.setRowStretch(i, 1)

        # add widgets to the layout
        lay.addWidget(self.text_widget, 7, 1, 3, 8)
        if self.display_bar:
            lay.addWidget(self.bar, 2, 3, 4, 4) 
        if self.display_relax:
            lay.addWidget(self.bar_relax, 2, 3, 4, 4)
        
        # use the layout for the main widget
        self.mainwidget.setLayout(lay)

        # setup redraw timer at 60Hz
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.trigger_update)
        self.timer.start(int(round(1000/globals.FEEDBACK_FRAMERATE)))
        self.lastUpdate = time.time()

        # open the window
        if fullscreen:
            self.showFullScreen()
        elif maximized:
            self.showMaximized()
        else:
            self.resize(width, height)
            self.show()

    def sendMessage(self, msg):
        try:
            # self.tcp_client.send_message(msg)
            print("Sending message to robot: ",msg)
        except Exception:
            return False

    # function to trigger a redraw
    def trigger_update(self):

        # if closing the window was requested externally, close the window
        if self.close_sheduled:
            print("close requested")
            self.close()
            return

        # update the GUI
        self.update()

        # after GUI was updated, push the displayed pacman positions to LSL stream
        self.lsl_outlet.push_sample([self.bar.up_down_percent])

    # function to be executed in a separate thread -> fetches LSL data and updates GUI states
    def data_handler(self):

        # is started as daemon -> while true is ok.
        while True:

            # try to pull a sample from lsl stream
            sample, timestamp = self.lsl_inlet.pull_sample(timeout=1)
            # if successful, process information
            if sample is not None:
                self.state_exo = str(sample[4]).strip().upper()
                self.trigger_exo = str(sample[3]).strip().upper()
                self.state_display_text = int(sample[0])
                # print(self.state_exo, self.trigger_exo, type(self.state_exo),type(self.trigger_exo))
                
                if not (int(sample[0]) == Cue.RELAX.value and self.display_relax == False):
                    self.text_widget.setText(DisplayText[int(sample[0])])

                if self.display_relax:
                    self.relax_widget.state = int(sample[0])

                self.bar.state = int(sample[1])
                self.bar_relax.state = int(sample[2])
                
                if self.display_activate_robot:
                    if self.state_exo == "CONTINUE":
                        self.sendMessage(self.EXO_COMMAND_CONTINUE)
                    elif self.state_exo == "PAUSE":
                        self.sendMessage(self.EXO_COMMAND_PAUSE)
                    elif self.state_exo == "RELAX":
                        self.sendMessage(self.EXO_COMMAND_PAUSE)
                    elif self.state_exo == "START_EXO":
                        self.sendMessage(self.EXO_COMMAND_WALK)
                    elif self.state_exo == "END":
                        self.sendMessage(self.EXO_COMMAND_NONE)
                    else:
                        continue
                
            else:
                print("No samples recevied within 1s.")

    # function to be executed in a separate thread -> fetches LSL data and updates GUI states
    def class_data_handler(self):

        # is started as daemon -> while true is ok.
        while True:

            # try to pull a sample from lsl stream
            sample, timestamp = self.class_lsl_inlet.pull_sample(timeout=1)

            # if successful, process information
            if sample is not None:
                
                norm_val = int(sample[0]) # normalized cz sample
                thresh = float(
                    self.class_lsl_inlet.info().desc() \
                        .child('parameters').child('ThresholdCz') \
                        .child_value()
                )
                
                # use negated thresh since thresh is stored as positive value
                self.relax_widget.relax_value = 1 - (norm_val/-thresh)
                print("norm wal: ", norm_val, "relax val: ", self.relax_widget.relax_value)
            else:
                print("No samples recevied within 1s.")


def demo_thread():

    stream_info = StreamInfo(
        globals.STREAM_NAME_TASK_EVENTS,
        'mixed',
        3, #self.NUM_OUTPUT_CHANNELS,
        10, #self.OUTPUT_SAMPLING_RATE,
        'int16', # self.CHANNEL_FORMAT,
        globals.STREAM_NAME_TASK_EVENTS+str(random.randint(100000, 999999))
    )

    outlet = StreamOutlet(stream_info, chunk_size=1)
    print("Demo Outlet created")

    time.sleep(2)

    outlet.push_sample([0, 0, 0])
    time.sleep(1)

    outlet.push_sample([3, 0, 0])
    time.sleep(2)
    outlet.push_sample([0, 0, 0])
    time.sleep(3)

    outlet.push_sample([1, 2, 2])
    time.sleep(2.5)
    outlet.push_sample([0, 0, 0])
    time.sleep(2.5)


    outlet.push_sample([2, 1, 1])
    time.sleep(2.5)
    outlet.push_sample([0, 0, 0])
    time.sleep(2.5)

    outlet.push_sample([4, 0, 0])
    time.sleep(2)

    outlet.push_sample([0, 0, 0])
    time.sleep(1)

    print("Demo finished.")

    global window
    window.close_sheduled = True
    time.sleep(1)


if __name__ == "__main__":

    app = QApplication(sys.argv)

    maximized = True
    width = 1000
    height = 750
    left = 0
    right = 0

    parser = argparse.ArgumentParser(description='Process some integers.')

    parser.add_argument('--maximized', type=int, default=1)
    parser.add_argument('--width', type=int, default=1000)
    parser.add_argument('--height', type=int, default=700)
    parser.add_argument('--left', type=int, default=0)
    parser.add_argument('--top', type=int, default=0)
    parser.add_argument('--showbar', type=int, required=True)
    parser.add_argument('--restartbar', type=int, required=True)
    parser.add_argument('--enrobot', type=int, required=True)


    args = parser.parse_args()

    print("Arguments received:", sys.argv)

    maximized = bool(args.maximized)
    show_bar = bool(args.showbar)
    restart_bar = bool(args.restartbar)
    activate_robot = bool(args.enrobot)

    # Search in command line arguments for demo argument
    demo = False
    for a in sys.argv:
        if a.strip().upper() == "DEMO":
            demo = True

    if demo:
        t = Thread(target=demo_thread, daemon=True)
        t.start()


    # create Desktop-Object to determine number of available screens and resolution
    desktopObject = app.desktop()
    num_screens = desktopObject.screenCount()
    
    # if there is only one screen available, start in windowed mode
    if num_screens == 1:
        left = desktopObject.screenGeometry(0).left()
        top = desktopObject.screenGeometry(0).top()

        if not maximized:
            left += args.left
            top += args.top

        window = VNF_KNF_LowerLimb(
            left, top, width=width, height=height, maximized=maximized, fullscreen=False, frameless=False, display_bar=show_bar, display_relax=restart_bar, display_activate_robot=activate_robot)

    # if there is more than one screen, start in fullscreen mode on second screen
    elif num_screens > 1:
        left = desktopObject.screenGeometry(1).left()
        top = desktopObject.screenGeometry(1).top()

        if not maximized:
            left += args.left
            top += args.top

        window = VNF_KNF_LowerLimb(
            left, top, width=width, height=height, maximized=maximized, fullscreen=maximized, frameless=True, display_bar=show_bar, display_relax=restart_bar, display_activate_robot=activate_robot)

    sys.exit(app.exec_())
