import pathlib
import os
import time
from threading import Thread
import random
from typing import Optional

from pylsl import StreamInlet, StreamOutlet, StreamInfo, resolve_byprop, cf_float32
import numpy as np

import globals
from modules.module import Module
from misc import LSLStreamInfoInterface
from misc.PreprocessingFramework.ProcessingPipeline import ProcessingPipeline
from misc.PreprocessingFramework.SmrErdPipeline import create_smr_erd_pipeline
from misc.timing import clock


from modules.preprocessing.SmrErdPipelineModule import SmrErdPipelineModule

class PreprocessingLowerLimbModule(Module):

    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME: str = "Pre-processing Lower Limb"
    MODULE_DESCRIPTION: str = ""
    MODULE_PATH = pathlib.Path(os.path.split(os.path.abspath(__file__))[0])

    REQUIRED_LSL_STREAMS = [globals.STREAM_NAME_RAW_SIGNAL]

    NUM_OUTPUT_CHANNELS: int = 4
    OUTPUT_CHANNEL_FORMAT: int = cf_float32
    # OUTPUT_CHANNEL_NAMES: list = ['µCz']
    OUTPUT_CHANNEL_NAMES: list = ['bipolar EOG', 'µC3', 'µC4', 'µCz']

    # overwrite parameter definition which is empty by superclass
    PARAMETER_DEFINITION = [
        {
            'name': 'fs_out',
            'displayname': 'Pipeline update rate',
            'description': '',
            'type': int,
            'unit': 'Hz',
            'default': 25
        },
        {
            'name': 'FOI',
            'displayname': 'Frequency of interest',
            'description': '',
            'type': float,
            'unit': 'Hz',
            'default': 11.0
        },
        {
            'name': 'sliding_window_seconds',
            'displayname': 'Sliding window length',
            'description': '',
            'type': float,
            'unit': 's',
            'default': 0.4
        },
        {
            'name': 'spatial_filter_type',
            'displayname': 'Spatial Filter',
            'description': '',
            'type': list,
            'unit': ['None', 'Laplacian Cz', '4-Ch Laplacian', '3-Ch Laplacian'],
            'default': 'Laplacian Cz'
        },
        {
            'name': 'eog_filter',
            'displayname': 'EOG channels',
            'description': '',
            'type': list,
            'unit': ['None','F7-F8', 'Cavallo et al.'],
            'default': 'None'
        },
        {
            'name': 'enable_debugging_streams',
            'displayname': 'Debugging streams',
            'description': '',
            'type': bool,
            'unit': '',
            'default': False
        }

    ]

    def __init__(self):
        super().__init__()

        self.set_state(Module.Status.STOPPED)

        self.lsl_inlet: Optional[StreamInlet] = None
        self.lsl_stream_info: Optional[StreamInfo] = None
        self.lsl_outlet: Optional[StreamOutlet] = None

        self.fs_in: float = 0
        self.fs_out: float = 0
        self.receive_chunk_len_seconds: float = 5 * 1e-3

        self.common_pipeline: Optional[ProcessingPipeline] = None
        self.eeg_pipeline: Optional[ProcessingPipeline] = None
        self.eog_pipeline: Optional[ProcessingPipeline] = None

        self.worker_thread: Optional[Thread] = None
        self.running: bool = False

        self.samples_received: int = 0
        self.samples_sent: int = 0

    # function to be run as a thread. Pulls a sample, hands it over to process_data function and pushes the returned sample
    def worker_thread_func(self):

        while self.running:

            # in_sample, in_timestamp = self.lsl_inlet.pull_sample(timeout=1)
            samples, timestamps = self.lsl_inlet.pull_chunk(timeout=self.receive_chunk_len_seconds)
            
            # if in_sample is not None:
            if len(samples) > 0:

                self.samples_received += len(samples)

                out_samples, out_timestamps = self.process_data(samples, timestamps)

                if len(out_samples) > 0:

                    for sample, timestamp in zip(out_samples, out_timestamps):

                        if globals.OUTPUT_TRUE_TIMESTAMPS:
                            self.lsl_outlet.push_sample(sample)

                        else:
                            self.lsl_outlet.push_sample(sample, timestamp)

                        self.samples_sent += 1


    def process_data(self, samples, timestamps):

        n_times = len(timestamps)
        n_channels = len(samples[0])

        # shape (n_times, n_channels)
        data = np.array(samples)

        # -> shape: n_channels, n_times
        data = np.moveaxis(data, 0, -1)

        # -> shape: n_trials, n_channels, ...features, n_times
        data = data.reshape([1, n_channels, n_times])

        out_samples, out_timestamps = self.common_pipeline.process(data, timestamps)
        eeg_out, eeg_timestamps = self.eeg_pipeline.process(out_samples, out_timestamps)
        # eog_out, eog_timestamps = self.eog_pipeline.process(out_samples, out_timestamps)

        # if eeg_out is not None or eog_out is not None:
        if eeg_out is not None:

            # combine into one array
            # combined_out = np.concatenate([eog_out, eeg_out], axis=1)
            combined_out = eeg_out
            
            # remove trials axis -> shape n_channels, n_times
            combined_out = combined_out[0]

            # move n_times to be first axis
            combined_out = np.moveaxis(combined_out, -1, 0)

            # convert to list
            combined_out = combined_out.tolist()

            # make sure timestamps is list of timestamps
            combined_out_timestamps = eeg_timestamps
            if type(combined_out_timestamps) is np.ndarray:
                combined_out_timestamps = combined_out_timestamps.tolist()
            if np.isscalar(combined_out_timestamps):
                combined_out_timestamps = [float(combined_out_timestamps)]

            return combined_out, combined_out_timestamps

        return [], []

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
        streams = resolve_byprop("name", globals.STREAM_NAME_RAW_SIGNAL, minimum=1, timeout=10)

        if len(streams) < 1:
            self.set_state(Module.Status.STOPPED)
            print("Could not start", self.MODULE_NAME, "because of missing stream:", globals.STREAM_NAME_RAW_SIGNAL)
            return

        self.fs_in: float = streams[0].nominal_srate()
        max_chunk_len = max(1, int(self.fs_in * self.receive_chunk_len_seconds))

        # init LSL inlet
        self.lsl_inlet = StreamInlet(streams[0], max_buflen=360, max_chunklen=max_chunk_len, recover=True)

        # read channel labels
        inlet_channel_labels = LSLStreamInfoInterface.get_channel_labels(self.lsl_inlet.info())

        # generate spatial filter maxtrix
        # spatial_filter_out_labels = ['bipolar EOG', 'C3', 'C4']           ##Changes Ximena--check again if there's an error
        spatial_filter_out_labels =  ['bipolar EOG', 'C3', 'C4', 'Cz']
        spatial_filter_weight_matrix = np.zeros([len(spatial_filter_out_labels), len(inlet_channel_labels)])

        # EOG component
        if self.get_parameter_value('eog_filter') == 'Cavallo et al.':
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('C3')] = 1
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('C4')] = -1
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('F3')] = 1
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('F4')] = -1
            # spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('T3')] = 1
            # spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('T4')] = -1
            # spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('P3')] = 1
            # spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('P4')] = -1
        else:
            print("no eog channels")
            # spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('FP1')] = 1
            # spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('FP2')] = -1

        # EEG components
        if self.get_parameter_value('spatial_filter_type') == 'None':
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('Cz'), inlet_channel_labels.index('Cz')] = 1

        elif self.get_parameter_value('spatial_filter_type') == 'Laplacian Cz':          #change here depending on the EEG cap --channels
            # spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('FP1')] = 1
            # spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('FP2')] = -1

            spatial_filter_weight_matrix[spatial_filter_out_labels.index('CZ'), inlet_channel_labels.index('CZ')] = 1
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('CZ'), inlet_channel_labels.index('FZ')] = -0.25
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('CZ'), inlet_channel_labels.index('C3')] = -0.25
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('CZ'), inlet_channel_labels.index('C4')] = -0.25
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('CZ'), inlet_channel_labels.index('PZ')] = -0.25

        elif self.get_parameter_value('spatial_filter_type') == '3-Ch Laplacian':
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('F7')] = 1
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('F8')] = -1

            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C3'), inlet_channel_labels.index('C3')] = 1
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C3'), inlet_channel_labels.index('CZ')] = -0.33
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C3'), inlet_channel_labels.index('F3')] = -0.33
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C3'), inlet_channel_labels.index('P3')] = -0.33

            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C4'), inlet_channel_labels.index('C4')] = 1
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C4'), inlet_channel_labels.index('CZ')] = -0.33
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C4'), inlet_channel_labels.index('F4')] = -0.33
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C4'), inlet_channel_labels.index('P4')] = -0.33

        elif self.get_parameter_value('spatial_filter_type') == '4-Ch Laplacian':
            # spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('F7')] = 1
            # spatial_filter_weight_matrix[spatial_filter_out_labels.index('bipolar EOG'), inlet_channel_labels.index('F8')] = -1

            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C3'), inlet_channel_labels.index('C3')] = 1
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C3'), inlet_channel_labels.index('CZ')] = -0.25
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C3'), inlet_channel_labels.index('F3')] = -0.25
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C3'), inlet_channel_labels.index('P3')] = -0.25
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C3'), inlet_channel_labels.index('T7')] = -0.25

            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C4'), inlet_channel_labels.index('C4')] = 1
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C4'), inlet_channel_labels.index('CZ')] = -0.25
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C4'), inlet_channel_labels.index('P4')] = -0.25
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C4'), inlet_channel_labels.index('F4')] = -0.25
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('C4'), inlet_channel_labels.index('T8')] = -0.25

            spatial_filter_weight_matrix[spatial_filter_out_labels.index('CZ'), inlet_channel_labels.index('CZ')] = 1
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('CZ'), inlet_channel_labels.index('FZ')] = -0.25
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('CZ'), inlet_channel_labels.index('C3')] = -0.25
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('CZ'), inlet_channel_labels.index('C4')] = -0.25
            spatial_filter_weight_matrix[spatial_filter_out_labels.index('CZ'), inlet_channel_labels.index('PZ')] = -0.25

        else:
            raise(Exception('Unsupported spatial filter type: {}'.format(self.get_parameter_value('spatial_filter_type'))))

        # init preprocessing pipeline
        self.common_pipeline, self.eeg_pipeline, self.eog_pipeline, self.fs_out = create_smr_erd_pipeline(
            inlet_channel_labels,
            fs=self.fs_in,
            foi=self.get_parameter_value('FOI'),
            fs_out=self.get_parameter_value('fs_out'),
            sliding_window_seconds=self.get_parameter_value('sliding_window_seconds'),
            enable_debugging_streams=self.get_parameter_value('enable_debugging_streams'),
            spatial_filter_weight_matrix=spatial_filter_weight_matrix,
            spatial_filter_output_labels=spatial_filter_out_labels,
            channels_eeg_processing=["Cz"]
        )

        # generate stream info
        self.lsl_stream_info = StreamInfo(
            globals.STREAM_NAME_PREPROCESSED_SIGNAL,
            'EEG',
            self.NUM_OUTPUT_CHANNELS,
            self.fs_out,
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

        # reset pipelines
        self.common_pipeline = None
        self.eeg_pipeline = None
        self.eog_pipeline = None
        self.fs_out = 0

        # reset status
        self.set_state(Module.Status.STOPPED)

    def restart(self):
        self.stop()
        time.sleep(0.2)
        self.start()
