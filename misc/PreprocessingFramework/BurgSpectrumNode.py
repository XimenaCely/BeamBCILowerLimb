import collections
import collections.abc

from misc.PreprocessingFramework.DataProcessor import check_data_dimensions, T_Timestamps, T_Data
from misc.PreprocessingFramework.ProcessingNode import ProcessingNode

from misc.burg.burg_utils import calc_burg_spectrum

from typing import List

import numpy as np

import logging

logger = logging.getLogger(__name__)


class BurgSpectrumNode(ProcessingNode):

    def __init__(self,
                 in_channel_labels: List[str],
                 sfreq: float,
                 foi: float = 11,
                 nbins: int = 1,
                 bin_width: float = 3.0,
                 evals_per_bin: int = 15,
                 output_type: str = 'amplitude',    # amplitude, spectrum -> amplitude means square-rooting of power data
                 **settings):

        super().__init__(in_channel_labels, **settings)

        self.sfreq: float = sfreq
        self.foi = foi
        self.nbis = nbins
        self.bin_width = 3.0
        self.evals_per_bin = evals_per_bin
        self.output_type = output_type


    @check_data_dimensions
    def process(self, data: T_Data, timestamps: T_Timestamps = None, *args: any, **kwargs: any) -> (
            T_Data, T_Timestamps):

        if data is None or data.shape[-1] == 0:
            return None, None

        if len(data.shape) > 3:
            raise Exception("BurgSpectrumNode is not implemented for ndim > 3 yet. Got data with shape {}.".format(data.shape))

        n_trials, n_channels, n_times = data.shape

        output = []

        for i_trial in range(n_trials):

            trial_output = []

            for i_ch in range(n_channels):

                amplitudes, freqs = calc_burg_spectrum(
                    signal=data[i_trial, i_ch, :], foi=self.foi, nbins=self.nbis, bin_width=self.bin_width, evals_per_bin=self.evals_per_bin,
                    output_type=self.output_type, fs=self.sfreq, model_order=int(self.sfreq/10), fast_version=True)

                trial_output.append(amplitudes)

            output.append(trial_output)

        output = np.array(output)
        output_timestamp = None
        if isinstance(timestamps, (int, float)):
            output_timestamp = timestamps
        elif isinstance(timestamps, collections.abc.Iterable):
            output_timestamp = timestamps[-1]

        return output, [output_timestamp]

    def get_settings(self, *args, **kwargs):
        settings = super().get_settings(*args, **kwargs)

        settings['sfreq'] = self.sfreq
        settings['foi'] = self.foi
        settings['nbins'] = self.nbis
        settings['bin_width'] = self.bin_width
        settings['evals_per_bin'] = self.evals_per_bin
        settings['output_type'] = self.output_type

        return settings
