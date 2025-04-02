import pathlib
import os
import time
from threading import Thread
import random

from pylsl import StreamInlet, StreamOutlet, StreamInfo, resolve_byprop, IRREGULAR_RATE, cf_float32

import globals
from modules.module import Module
from misc import LSLStreamInfoInterface


class BasicClassificationModule(Module):

    MODULE_NAME: str = "Basic Classification Module"
    MODULE_DESCRIPTION: str = ""
    MODULE_PATH = pathlib.Path(os.path.split(os.path.abspath(__file__))[0])

    REQUIRED_LSL_STREAMS = [globals.STREAM_NAME_PREPROCESSED_SIGNAL]

    NUM_OUTPUT_CHANNELS: int = 0
    OUTPUT_CHANNEL_FORMAT: int = cf_float32
    OUTPUT_CHANNEL_NAMES: list = []

    def __init__(self):
        super(BasicClassificationModule, self).__init__()

        self.set_state(Module.Status.STOPPED)

        self.lsl_inlet = None # StreamInlet(max_buflen=360, max_chunklen=1, recover=True)
        self.lsl_stream_info = None
        self.lsl_outlet_sampling_rate = IRREGULAR_RATE
        self.lsl_outlet = None # StreamOutlet(streaminfo, chunk_size=1)

        self.worker_thread = None # Thread(target=self.worker_thread, args=(self, self.inlet, self.outlet), daemon=True)
        self.running: bool = False

        self.samples_received: int = 0
        self.samples_sent: int = 0

    # function to be run as a thread. Pulls a sample, hands it over to process_data function and pushes the returned sample
    def worker_thread_func(self):

        while self.running:

            in_sample, in_timestamp = self.lsl_inlet.pull_sample(timeout=1)

            if in_sample is not None:

                self.samples_received += 1

                out_sample, out_timestamp = self.process_data(in_sample, in_timestamp)

                if out_sample is not None:

                    if globals.OUTPUT_TRUE_TIMESTAMPS:
                        self.lsl_outlet.push_sample(out_sample)
                    else:
                        self.lsl_outlet.push_sample(out_sample, out_timestamp)

                    self.samples_sent += 1


    def process_data(self, sample, timestamp):

        return (sample, timestamp)


    def start(self):

        # do not start up the LSL LabRecorder App is not available
        if not globals.LSLAvailable:
            return

        # do not start up the module if it was already started
        if self.state != Module.Status.STOPPED:
            return

        # set status
        self.set_state(Module.Status.STARTING)

        # reset sample counter
        self.samples_received = 0
        self.samples_sent = 0

        # fetch necessary lsl stream
        streams = resolve_byprop("name", globals.STREAM_NAME_PREPROCESSED_SIGNAL, minimum=1, timeout=10)

        if len(streams) < 1:
            self.set_state(Module.Status.STOPPED)
            print("Could not start", self.MODULE_NAME, "because of missing stream:", globals.STREAM_NAME_PREPROCESSED_SIGNAL)
            return

        # init LSL inlet
        self.lsl_inlet = StreamInlet(streams[0], max_buflen=360, max_chunklen=1, recover=True)

        # generate stream info
        self.lsl_stream_info = StreamInfo(
            globals.STREAM_NAME_CLASSIFIED_SIGNAL,
            'mixed',
            self.NUM_OUTPUT_CHANNELS,
            self.lsl_inlet.info().nominal_srate(),
            self.OUTPUT_CHANNEL_FORMAT,
            'uid'+str(random.randint(100000, 999999))
        )

        # add channel names to stream info
        LSLStreamInfoInterface.add_channel_names(self.lsl_stream_info, self.OUTPUT_CHANNEL_NAMES)

        # add parameters to stream info
        LSLStreamInfoInterface.add_parameters(self.lsl_stream_info, self.parameters)

        # init LSL outlet
        self.lsl_outlet = StreamOutlet(self.lsl_stream_info, chunk_size=1)

        # start worker thread which receives and processes signals
        self.worker_thread = Thread(target=self.worker_thread_func, daemon=True)
        self.running = True
        self.worker_thread.start()

        # set status
        self.set_state(Module.Status.RUNNING)


    def stop(self):

        # do not try to stop the LSL LabRecorder App if it is not available
        if not globals.LSLAvailable:
            return

        # don't try to stop anything that is already stopped.
        if self.get_state() is not Module.Status.RUNNING:
            return

        self.set_state(Module.Status.STOPPING)

        # stop the worker thread
        self.running = False
        print(self.MODULE_NAME + ': Waiting for worker thread to terminate... ')
        while self.worker_thread.is_alive():
            time.sleep(0.1)
        self.worker_thread = None
        print("done.")

        # close the LSL streams
        self.lsl_inlet.close_stream()
        self.lsl_inlet = None
        self.lsl_outlet = None

        # reset status
        self.set_state(Module.Status.STOPPED)

        # print(self.MODULE_NAME, ": stopped. {} samples received, {} samples sent.".format(self.samples_received, self.samples_sent))


    def restart(self):
        self.stop()
        time.sleep(0.2)
        self.start()
