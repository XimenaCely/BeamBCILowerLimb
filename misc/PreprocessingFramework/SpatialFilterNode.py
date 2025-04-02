from misc.PreprocessingFramework.DataProcessor import check_data_dimensions, T_Timestamps, T_Data
from misc.PreprocessingFramework.ProcessingNode import ProcessingNode

from typing import List

import numpy as np

import logging

logger = logging.getLogger(__name__)


class SpatialFilterNode(ProcessingNode):

    def __init__(self,
                 in_channel_labels: List[str],
                 weights: np.ndarray,
                 **settings):

        super().__init__(in_channel_labels, **settings)

        # shape (n_out x n_in)
        self.weights = weights

    @check_data_dimensions
    def process(self, data: T_Data, timestamps: T_Timestamps = None, *args: any, **kwargs: any) -> (
            T_Data, T_Timestamps):

        if data is None or data.shape[-1] == 0:
            return None, None

        if len(data.shape) > 3:
            raise Exception("SpatialFilterNode can not process more than 3 dimensions of data.")

        n_trials, n_channels, n_times = data.shape

        n_out_channels = self.weights.shape[0]

        # create zero-filled array for output data with adjusted number of channels
        output_data = np.zeros([n_trials, n_out_channels, n_times], dtype=data.dtype)

        # process data per trial
        for i in range(n_trials):

            output_data[i] = self.weights @ data[i]

        return output_data, timestamps

    def get_settings(self, *args, **kwargs):
        settings = super().get_settings(*args, **kwargs)
        settings['weights'] = self.weights
        
        return settings


