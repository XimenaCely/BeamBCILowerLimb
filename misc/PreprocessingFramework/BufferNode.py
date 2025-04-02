import numpy as np
from typing import List

import logging

from misc.PreprocessingFramework.DataProcessor import check_data_dimensions, T_Timestamps, T_Data, clear_decorator
from misc.PreprocessingFramework.ProcessingNode import ProcessingNode

logger = logging.getLogger(__name__)


class BufferNode(ProcessingNode):
    def __init__(self, in_channel_labels: List[str], buffer_length: int, shift: int, **settings):
        super().__init__(in_channel_labels, **settings)

        self.buffer = np.array([])
        self.buffer_timestamps = []
        self.buffer_length = buffer_length
        self.actual_buffer_length = self.buffer_length * 10
        self.shift = shift
        self.buffer_shape: list = []
        self.return_shape: list = []

        self.write_index = 0
        self.read_index = 0

        self.total_samples_written = 0
        self.total_samples_discarded = 0

    def get_buffer_available(self) -> int:
        return self.actual_buffer_length - (self.total_samples_written - self.total_samples_discarded)

    def init_buffers(self, data):
        self.buffer_shape = list(data.shape)
        self.buffer_shape[-1] = self.actual_buffer_length
        self.return_shape = self.buffer_shape.copy()
        self.return_shape[-1] = self.buffer_length

        self.buffer = np.zeros(self.buffer_shape)
        self.buffer_timestamps = [None] * self.actual_buffer_length

        self.write_index = 0
        self.read_index = 0

        self.total_samples_written = 0
        self.total_samples_discarded = 0

    @check_data_dimensions
    def process(self, data: T_Data, timestamps: T_Timestamps = None, *args: any, **kwargs: any) -> (
    T_Data, T_Timestamps):

        if data is None or data.shape[-1] == 0:
            return None, None

        # check if buffer has not been initialized:
        # shape of buffer array is unknown before data is processed first
        if len(self.buffer_shape) < 1:
            self.init_buffers(data)

        # write new data into buffer
        new_samples = data.shape[-1]

        if timestamps is None:
            new_timestamps = [None] * new_samples
        elif isinstance(timestamps, (float, int)):
            new_timestamps = [None] * (new_samples-1) + [timestamps]
        else:
            new_timestamps = list(timestamps)

        # check if there is enough space in the buffer
        if new_samples > self.get_buffer_available():
            raise Exception("Buffer too short. Data is lost.")

        # calculate how many samples will be inserted into buffer before the write_index is reset to 0
        new_before_turnaround = min(new_samples, self.actual_buffer_length - self.write_index)
        new_after_turnaround = new_samples - new_before_turnaround

        if new_before_turnaround > 0:
            self.buffer[..., self.write_index:self.write_index + new_before_turnaround] = data[...,
                                                                                          0:new_before_turnaround]
            self.buffer_timestamps[self.write_index:self.write_index + new_before_turnaround] = new_timestamps[0:new_before_turnaround]

            self.write_index += new_before_turnaround
            self.write_index = self.write_index % self.actual_buffer_length

        if new_after_turnaround > 0:
            self.buffer[..., self.write_index:self.write_index + new_after_turnaround] = data[...,
                                                                                         new_before_turnaround:]
            self.buffer_timestamps[self.write_index:self.write_index + new_after_turnaround] = new_timestamps[new_before_turnaround:]

            self.write_index += new_after_turnaround
            self.write_index = self.write_index % self.actual_buffer_length

        self.total_samples_written += new_samples

        if self.total_samples_written - self.total_samples_discarded < self.buffer_length:

            logger.debug(f"Buffer does not yet have enough data ({self.total_samples_written - self.total_samples_discarded} samples) to create output (buflen={self.buffer_length}).")
            return None, None

        return_before_turnaround = min(self.buffer_length, self.actual_buffer_length - self.read_index)
        return_after_turnaround = self.buffer_length - return_before_turnaround

        return_data = np.zeros(self.return_shape)
        return_timestamps = [None] * self.buffer_length

        if return_before_turnaround > 0:
            return_data[..., :return_before_turnaround] = self.buffer[...,
                                                          self.read_index:self.read_index + return_before_turnaround]
            return_timestamps[:return_before_turnaround] = self.buffer_timestamps[self.read_index:self.read_index + return_before_turnaround]

        if return_after_turnaround > 0:
            return_data[..., return_before_turnaround:] = self.buffer[..., 0:return_after_turnaround]
            return_timestamps[return_before_turnaround:] = self.buffer_timestamps[0:return_after_turnaround]

        self.read_index = (self.read_index + self.shift) % self.actual_buffer_length
        self.total_samples_discarded += self.shift

        return return_data, return_timestamps

    def process_trial(self, data: np.ndarray, timestamps=None, surrogate_timestamps=False, *args, **kwargs):
        """

        :param data: (1, n_channels, ..., n_times)
        :param timestamps:
        :param args:
        :param kwargs:
        :return:
        """
        n_trials, n_channels, *n_features, n_times = data.shape

        if n_trials != 1:
            logger.warning(f"process_trial() can only be called with a single trial")

        if n_times <= self.buffer_length:
            logger.warning(f"process_trial received fewer samples ({n_times}) than buffer_length ({self.buffer_length})")

        trial_data = []
        for start_sample in np.arange(0, n_times-self.buffer_length+1, self.shift):
            end_sample: int = start_sample + self.buffer_length

            trial_data.append(data[0:1, ..., start_sample:end_sample])
        n_trials_new = len(trial_data)

        # if n_trials_new > 1 or n_trials_new == 0:
        if n_trials_new == 0:
            timestamps = None
        elif n_trials_new > 1 and surrogate_timestamps:
            # When the number of samples exceeded one buffer+shift, timestamps cannot be reasonably computed anymore
            # logger.debug('BufferNode is creating a surrogate set of timestamps')
            timestamps = timestamps[:self.buffer_length]
        else:
            timestamps = timestamps[:self.buffer_length]

        return np.concatenate(trial_data), timestamps

    @clear_decorator(before=True, after=True)
    def train(self, data: np.ndarray, labels, timestamps=None, *args: any, **kwargs: any):
        n_trials, n_channels, *n_features, n_times = data.shape

        labels_new = []
        data_new = []
        for i in range(n_trials):
            label = labels[i]
            data_trial = data[i:i+1, :]  # use slicing to maintain dimensions

            data_trial_out, timestamps_new = self.process_trial(data_trial, timestamps)
            n_trials_new = data_trial_out.shape[0]
            data_new.append(data_trial_out)
            labels_new.extend([label for _ in range(n_trials_new)])

        data_new = np.concatenate(data_new)

        return data_new, labels_new, timestamps_new

    def clear(self, *args, **kwargs):
        self.buffer_shape = []

    def get_settings(self, *args, **kwargs):
        settings = super().get_settings(*args, **kwargs)
        settings['buffer_length'] = self.buffer_length
        settings['shift'] = self.shift

        return settings
