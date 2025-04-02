from misc.PreprocessingFramework.DataProcessor import check_data_dimensions, T_Timestamps, T_Data, \
    clear_decorator
from misc.PreprocessingFramework.ProcessingNode import ProcessingNode

from typing import Union, List

import numpy as np

import matplotlib.pyplot as plt
import logging

logger = logging.getLogger(__name__)


class SinglePoleFilterNode(ProcessingNode):
    def __init__(self, in_channel_labels: List[str], time_const: float, sfreq: float, **settings):
        super().__init__(in_channel_labels, **settings)

        self.time_const: float = time_const
        self.sfreq: float = sfreq

        self._decay_factor: float = None
        self._y: np.ndarray = None
        self._init_filter()
        self.clear()

    def _init_filter(self):
        t_block = self.time_const * self.sfreq
        # if time_const is chosen =0 that should effectively skip the filter
        if t_block == 0:
            self._decay_factor = 0
        else:
            self._decay_factor = np.exp(-1/t_block)

    @check_data_dimensions
    def process(self, data: T_Data, timestamps: T_Timestamps = None, *args: any, **kwargs: any) -> (
            T_Data, T_Timestamps):
        if data is None or data.shape[-1] == 0:
            return None, None

        data = data.copy()

        for i in range(data.shape[-1]):
            self._y = self._y + (1-self._decay_factor) * (data[..., i] - self._y)
            data[..., i] = self._y

        return data, timestamps

    @clear_decorator(before=True, after=True)
    def train(self, data: T_Data, labels: np.ndarray, timestamps=None, *args: any, **kwargs: any) -> (
            Union[T_Data, List[T_Data]]):

        data_out, timestamps_out = self.process(data, timestamps)
        return data_out, labels, timestamps_out

    def clear(self, *args, **kwargs):
        self._y = np.array(0.0, dtype=float)

    def get_settings(self, decay_factor: bool = False, *args, **kwargs):
        settings = super().get_settings(*args, **kwargs)
        settings['sfreq'] = self.sfreq
        settings['time_const'] = self.time_const
        if decay_factor:
            settings['_decay_factor'] = self._decay_factor

        return settings


if __name__ == '__main__':
    num_in_channels = 1

    timestamps = np.arange(0, 20, 0.1)
    data = np.random.rand(1, 1, len(timestamps))-0.5
    # data = (timestamps > 10).astype(float)[np.newaxis, np.newaxis, :]

    plt.plot(timestamps, data.squeeze(), label='data')

    for time_const in [0, 0.2, 0.5, 1, 1.5, 2]:
        node = SinglePoleFilterNode(in_channel_labels=[f"Ch{i}" for i in range(num_in_channels)], sfreq=10, time_const=time_const)
        data_out, timestamps_out = node.process(data, timestamps)
        plt.plot(timestamps, data_out.squeeze(), label=f'data out ({time_const=})')
    plt.legend()
    plt.show()
