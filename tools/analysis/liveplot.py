from __future__ import annotations
from typing import *
import sys
import os
sys.path.append(os.getcwd())
# from matplotlib.backends.qt_compat import QtCore, QtWidgets
import pylsl.pylsl
from PyQt5 import QtWidgets, QtCore
# from matplotlib.backends.backend_qt5agg import FigureCanvas
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import matplotlib.figure as mpl_fig
import matplotlib.animation as anim
from threading import Thread
import time

import globals
from pylsl import StreamInlet, resolve_byprop

class ApplicationWindow(QtWidgets.QMainWindow):
    '''
    The PyQt5 main window.

    '''
    def __init__(self):
        super().__init__()
        # 1. Window settings
        self.setGeometry(300, 300, 800, 600)
        self.setWindowTitle("LivePlot")
        self.frm = QtWidgets.QFrame(self)
        self.frm.setStyleSheet("QWidget { background-color: #444444; }")
        self.lyt = QtWidgets.QVBoxLayout()
        self.frm.setLayout(self.lyt)
        self.setCentralWidget(self.frm)

        self.inlet_classifier_output = None
        self.inlet_preprocessed_data = None

        # 2. Place the matplotlib figure
        #self.myFig = MyFigureCanvas(x_len=int(25*12.5), y_range=[-1, 2], interval=50,
        #                            inlet_classifier_output=self.inlet_classifier_output,
        #                            inlet_preprocessed_data=self.inlet_preprocessed_data)
        self.myFig = None
        #self.lyt.addWidget(self.myFig)



        # 3. Show
        self.show()

        self.update_fig = False

        timer_gui_update = QtCore.QTimer(self)
        timer_gui_update.timeout.connect(self.fig_updater)
        timer_gui_update.start(100)


        self.stream_connect_task_thread = Thread(name="StreamConnectionTask", target=self.stream_connect_task, daemon=True)
        self.stream_connect_task_thread.start()

    def fig_updater(self):

        if self.update_fig:

            print("Updating Figure.")

            if self.myFig is not None:
                self.lyt.removeWidget(self.myFig)

            #self.myFig = MyFigureCanvas(x_len=int(25*12.5), y_range=[-1, 2], interval=50,
            #                            inlet_classifier_output=self.inlet_classifier_output,
            #                            inlet_preprocessed_data=self.inlet_preprocessed_data,
            #                            parent=self)
            self.myFig = MyFigureCanvas(x_len=int(25*12.5), y_range=[-1, 2], interval=50,
                                        inlet_classifier_output=None,
                                        inlet_preprocessed_data=None,
                                        parent=self)
            self.lyt.addWidget(self.myFig)

            self.update_fig = False

    def stream_connect_task(self):

        print("Stream Connector started")

        while True:

            time.sleep(1)

            if self.inlet_classifier_output is None:

                streams = resolve_byprop('name', globals.STREAM_NAME_CLASSIFIED_SIGNAL, minimum=1, timeout=1)
                if len(streams) > 0:
                    print("Connecting to ClassifierOutput")
                    self.inlet_classifier_output = StreamInlet(streams[0], recover=False)
                    time.sleep(0.2)
                    self.update_fig = True

            if self.inlet_preprocessed_data is None:
                streams = resolve_byprop('name', globals.STREAM_NAME_PREPROCESSED_SIGNAL, minimum=1, timeout=1)
                if len(streams) > 0:
                    print("Connecting to PreprocessedData")
                    self.inlet_preprocessed_data = StreamInlet(streams[0], recover=False)
                    time.sleep(0.2)
                    self.update_fig = True


class MyFigureCanvas(FigureCanvas, anim.FuncAnimation):
    '''
    This is the FigureCanvas in which the live plot is drawn.

    '''
    def __init__(self, x_len: int, y_range: List, interval: int,
                 inlet_classifier_output: StreamInlet = None, inlet_preprocessed_data: StreamInlet = None, parent = None) -> None:
        '''
        :param x_len:       The nr of data points shown in one plot.
        :param y_range:     Range on y-axis.
        :param interval:    Get a new datapoint every .. milliseconds.

        '''
        FigureCanvas.__init__(self, mpl_fig.Figure())

        self.inlet = inlet_classifier_output
        self.inlet_eog = inlet_preprocessed_data

        self.parent = parent

        streams = resolve_byprop('name', globals.STREAM_NAME_CLASSIFIED_SIGNAL, minimum=1, timeout=1)
        self.inlet = StreamInlet(streams[0], recover=False)
        streams = resolve_byprop('name', globals.STREAM_NAME_PREPROCESSED_SIGNAL, minimum=1, timeout=1)
        self.inlet_eog = StreamInlet(streams[0], recover=False)

        self.th_c3 = - float(self.inlet.info().desc().child("parameters").child_value("ThresholdC3"))
        self.th_c4 = - float(self.inlet.info().desc().child("parameters").child_value("ThresholdC4"))
        self.th_l = float(self.inlet.info().desc().child("parameters").child_value("ThresholdEOGleft"))
        self.th_r = float(self.inlet.info().desc().child("parameters").child_value("ThresholdEOGright"))

        # Range settings
        self._x_len_ = x_len
        self._y_range_ = y_range

        # Store two lists _x_ and _y_
        x = list(range(0, x_len))
        self.y1 = [float('nan')] * x_len
        self.y2 = [float('nan')] * x_len
        self.y3 = [float('nan')] * x_len

        # Store a figure and ax
        self._ax_1, self._ax_2, self._ax_3  = self.figure.subplots(3, 1, sharex=True)
        self._ax_1.set_title("C3 normalized signal (right hand)")
        self._ax_2.set_title("C4 normalized signal (left hand)")
        self._ax_3.set_title("EOG bipolar signal")
        self._ax_1.set_ylim(ymin=self._y_range_[0], ymax=self._y_range_[1])
        self._ax_2.set_ylim(ymin=self._y_range_[0], ymax=self._y_range_[1])
        self._ax_3.set_ylim(ymin=-max(self.th_l, self.th_r)*1.5, ymax=max(self.th_l, self.th_r)*1.5)
        self._line_1, = self._ax_1.plot(x, self.y1)
        self._line_2, = self._ax_2.plot(x, self.y2)
        self._line_3, = self._ax_3.plot(x, self.y3)

        self.line_th_c3 = self._ax_1.hlines(self.th_c3, 0, x_len, lw=1, colors=["#000000"], linestyles=["--"])
        self._ax_2.hlines(self.th_c4, 0, x_len, lw=1, colors=["#000000"], linestyles=["--"])

        self._ax_3.hlines(self.th_l, 0, x_len, lw=1, colors=["#000000"], linestyles=["--"])
        self._ax_3.hlines(self.th_r, 0, x_len, lw=1, colors=["#000000"], linestyles=["--"])

        t = self._ax_1.text(0, 0, '', style='italic',
                            bbox={'facecolor': 'red', 'alpha': 0.5, 'pad': 10})

        self.figure.tight_layout()

        # Call superclass constructors
        anim.FuncAnimation.__init__(self, self.figure, self._update_canvas_, fargs=(self.y1,self.y2,self.y3), interval=interval, blit=True)
        return

    def _update_canvas_(self, i, y1, y2, y3) -> None:
        '''
        This function gets called regularly by the timer.
        '''

        samples = None

        if self.inlet is not None:
            try:
                samples, timestamp = self.inlet.pull_chunk()

                for sample in samples:
                    y1.append(sample[0])
                    y2.append(sample[1])

            except pylsl.pylsl.LostError:

                self.inlet = None
                self.parent.inlet_classifier_output = None

        samples_eog = None

        if self.inlet_eog is not None:
            try:
                samples_eog, timestamp = self.inlet_eog.pull_chunk()

                for sample in samples_eog:
                    y3.append(sample[0])

            except pylsl.pylsl.LostError:

                self.inlet_eog = None
                self.parent.inlet_preprocessed_data = None

        y1 = y1[-self._x_len_:]
        y2 = y2[-self._x_len_:]
        y3 = y3[-self._x_len_:]

        if samples is not None and len(samples) > 0:
            self._line_1.set_ydata(y1)
            self._line_2.set_ydata(y2)

        if samples_eog is not None and len(samples_eog) > 0:
            self._line_3.set_ydata(y3)

        return self._line_1, self._line_2, self._line_3



if __name__ == "__main__":
    qapp = QtWidgets.QApplication(sys.argv)
    app = ApplicationWindow()
    qapp.exec_()