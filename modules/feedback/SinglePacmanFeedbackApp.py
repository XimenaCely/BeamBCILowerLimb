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
from misc.enums import Side, Cue, DisplayText, ExoState
from modules.module import Module
from misc import LSLStreamInfoInterface


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

    ENABLED_COLOR = QtGui.QColor(255, 200, 100)
    DISABLED_COLOR = QtGui.QColor(100, 100, 100)

    CLOSE_SPEED_PERCENT_PER_SEC: float = 25
    OPEN_SPEED_PERCENT_PER_SEC: float = 200

    def __init__(self, rotation: int = 0):
        super(PacmanWidget, self).__init__()

        self.rotation = rotation

        self.visible: bool = True
        self.enabled: bool = True

        self.closed_percent: float = 0.0

        self.lastUpdate = time.time()

        self.state: int = ExoState.STOP.value


    def updateStates(self):

        t = time.time()
        dt = t - self.lastUpdate

        self.lastUpdate = t

        if self.state == ExoState.CLOSE.value or self.state == ExoState.HIDE_CLOSE.value:
            self.closed_percent += dt * self.CLOSE_SPEED_PERCENT_PER_SEC
            self.closed_percent = max(0, min(100, self.closed_percent))
        # elif self.state == ExoState.OPEN.value or self.state == ExoState.HIDE_OPEN.value:
        #     self.closed_percent -= dt * self.OPEN_SPEED_PERCENT_PER_SEC
        #     self.closed_percent = max(0, min(100, self.closed_percent))


    def paintEvent(self, e):

        self.updateStates()

        if self.visible and self.state not in [ExoState.HIDE_STOP.value, ExoState.HIDE_OPEN.value, ExoState.HIDE_CLOSE.value]:
            qp = QtGui.QPainter()
            qp.begin(self)
            self.drawPacman(qp)
            qp.end()


    def drawPacman(self, qp):

        size = self.size()
        w = size.width()
        h = size.height()

        if self.enabled:
            qp.setPen(self.ENABLED_COLOR)
            qp.setBrush(self.ENABLED_COLOR)
        else:
            qp.setPen(self.DISABLED_COLOR)
            qp.setBrush(self.DISABLED_COLOR)

        diameter = min(w, h)
        radius = diameter / 2
        qp.drawPie(
            int(round(w/2 - radius)), int(round(h/2 - radius)), diameter, diameter, 
            int(round(self.rotation + 60-self.closed_percent*1.2/2))*16, int(round(240+self.closed_percent*1.2))*16
        )


class SinglePacmanFeedbackApp(QMainWindow):

    OUTPUT_CHANNEL_NAMES: list = ["left pacman closed", "right pacman closed"]

    def __init__(self, left, top, width=1000, height=700, fullscreen=False, maximized=False, frameless=False, side=Side.RIGHT, display_pacman: bool = True,  display_relax: bool = False):

        super(SinglePacmanFeedbackApp, self).__init__()

        self.side = side
        self.display_pacman = display_pacman
        self.display_relax = display_relax

        self.parameters = {
            "laterality": Module.Parameter("laterality", "laterality", str, self.side.value, "", ""),
            "display pacman": Module.Parameter("display_pacman", "display pacman", bool, self.display_pacman, "", ""),
            "display relax": Module.Parameter("display_relax", "display pacman during open", bool, self.display_relax, "", "")
        }


        # states
        self.state_display_text: int = 0
        self.state_left_pacman: int = 0
        self.state_right_pacman: int = 0

        # flag to allow external process to close the window
        self.close_sheduled = False

        # lsl setup
        streams = resolve_byprop("name", globals.STREAM_NAME_TASK_EVENTS, minimum=1, timeout=3)
        if len(streams) < 1:
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
            2, #self.NUM_OUTPUT_CHANNELS,
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

        if self.display_relax:
            self.class_data_thread = Thread(target=self.class_data_handler, daemon=True)
            self.class_data_thread.start()

        self.setWindowTitle("BeamBCI Feedback App")
        self.setWindowFlags(QtCore.Qt.FramelessWindowHint) if frameless else None
        self.move(left, top)

        # create a main widget with black background
        self.mainwidget = QWidget()
        self.mainwidget.setStyleSheet("QWidget{ background-color: #000000; }")
        self.setCentralWidget(self.mainwidget)

        # create pacman widgets
        self.pacman_left = PacmanWidget()
        self.pacman_right = PacmanWidget(180)

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
        if self.display_pacman:
            lay.addWidget(self.pacman_left, 2, 3, 4, 4) if self.side == Side.LEFT else None
            lay.addWidget(self.pacman_right, 2, 3, 4, 4) if self.side == Side.RIGHT else None
        if self.display_relax:
            lay.addWidget(self.relax_widget, 2, 3, 4, 4)
        
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
        self.lsl_outlet.push_sample([self.pacman_left.closed_percent, self.pacman_right.closed_percent])


    # function to be executed in a separate thread -> fetches LSL data and updates GUI states
    def data_handler(self):

        # is started as daemon -> while true is ok.
        while True:

            # try to pull a sample from lsl stream
            sample, timestamp = self.lsl_inlet.pull_sample(timeout=1)

            # if successful, process information
            if sample is not None:
                
                self.state_display_text = int(sample[0])

                if not (int(sample[0]) == Cue.RELAX.value and self.display_relax == False):
                    self.text_widget.setText(DisplayText[int(sample[0])])

                if self.display_relax:
                    self.relax_widget.state = int(sample[0])
                self.pacman_left.state = int(sample[1])
                self.pacman_right.state = int(sample[2])

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

                if self.side == Side.RIGHT:
                    norm_val = int(sample[0]) # normalized c3 sample
                    thresh = float(
                        self.class_lsl_inlet.info().desc() \
                            .child('parameters').child('ThresholdC3') \
                            .child_value()
                    )
                elif self.side == Side.LEFT:
                    norm_val = int(sample[1]) # normalized c4 sample
                    thresh = float(
                        self.class_lsl_inlet.info().desc() \
                            .child('parameters').child('ThresholdC4') \
                            .child_value()
                    )
                else:
                    norm_val = 0.5 * int(sample[0]) + int(sample[1])
                    thresh_right = float(
                        self.class_lsl_inlet.info().desc() \
                            .child('parameters').child('ThresholdC3') \
                            .child_value()
                    )   
                    thresh_left = float(
                        self.class_lsl_inlet.info().desc() \
                            .child('parameters').child('ThresholdC4') \
                            .child_value()
                    )
                    thresh = 0.5 * (thresh_right + thresh_left)

                # use negated thresh since thresh is stored as positive value
                self.relax_widget.relax_value = 1 - (norm_val/-thresh)

            else:
                print("No samples recevied within 1s.")


def demo_thread():

    stream_info = StreamInfo(
        globals.STREAM_NAME_TASK_EVENTS,
        'mixed',
        2, #self.NUM_OUTPUT_CHANNELS,
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
    parser.add_argument('--side', type=str, required=True)
    parser.add_argument('--showpacman', type=int, required=True)
    parser.add_argument('--showopen', type=int, required=True)

    args = parser.parse_args()

    maximized = bool(args.maximized)
    side = Side.RIGHT if args.side.upper() == "RIGHT" else Side.LEFT
    show_open = bool(args.showopen)
    show_pacman = bool(args.showpacman)


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

        window = SinglePacmanFeedbackApp(
            left, top, width=width, height=height, maximized=maximized, fullscreen=False, frameless=False, side=side, display_pacman=show_pacman, display_relax=show_open)

    # if there is more than one screen, start in fullscreen mode on second screen
    elif num_screens > 1:
        left = desktopObject.screenGeometry(1).left()
        top = desktopObject.screenGeometry(1).top()

        if not maximized:
            left += args.left
            top += args.top

        window = SinglePacmanFeedbackApp(
            left, top, width=width, height=height, maximized=maximized, fullscreen=maximized, frameless=True, side=side, display_pacman=show_pacman, display_relax=show_open)

    sys.exit(app.exec_())
