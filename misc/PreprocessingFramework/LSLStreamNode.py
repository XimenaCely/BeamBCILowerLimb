import collections
import string
from typing import List

import numpy as np
import pylsl
import logging

from misc.PreprocessingFramework.DataProcessor import check_data_dimensions, T_Data, T_Timestamps
from misc.PreprocessingFramework.ProcessingNode import ProcessingNode

logger = logging.getLogger(__name__)


def random_string(num_chars=6):
    charset = list(string.ascii_uppercase + string.digits)
    return ''.join(np.random.choice(charset, size=num_chars))


class LSLStreamNode(ProcessingNode):
    def __init__(self, in_channel_labels: List[str],
                 stream_name: str = None,
                 source_id: str = None,
                 lsl_type: str = 'mixed',
                 nominal_srate: float = pylsl.IRREGULAR_RATE,
                 channel_format: int = pylsl.cf_double64,
                 chunk_size: int = 1,
                 max_buffered: int = 360,
                 new_timestamps: bool = False,
                 feature_dimensions: list = None,
                 **settings):

        name_default_suffix = random_string()
        super().__init__(in_channel_labels, **settings)

        self.stream_name: str = stream_name if stream_name is not None else "LSLStreamNode_" + name_default_suffix
        self.source_id: str = source_id if source_id is not None else 'StreamNode_' + name_default_suffix
        self.lsl_type: str = lsl_type
        self.nominal_srate = nominal_srate
        self.channel_format = channel_format
        self.chunk_size = chunk_size
        self.max_buffered = max_buffered
        self.new_timestamps = new_timestamps
        self.feature_dimensions = feature_dimensions if feature_dimensions is not None else []
        self.lsl_channel_count = int(self.num_in_channels * np.prod(self.feature_dimensions))

        self.lsl_info: pylsl.StreamInfo = None
        self.lsl_outlet: pylsl.StreamOutlet = None

        self.init_stream()

    def init_stream(self):
        lsl_info = pylsl.StreamInfo(name=self.stream_name, type=self.lsl_type,
                                         channel_count=self.lsl_channel_count,
                                         nominal_srate=self.nominal_srate, channel_format=self.channel_format,
                                         source_id=self.source_id)
        self.lsl_outlet = pylsl.StreamOutlet(lsl_info, chunk_size=self.chunk_size, max_buffered=self.max_buffered)
        self.lsl_info = self.lsl_outlet.get_info()

    def open(self):
        if self.lsl_info is None:
            self.init_stream()

    def close(self):
        self.lsl_outlet = None
        self.lsl_info = None

    def __del__(self):
        self.close()

    @check_data_dimensions
    def process(self, data: T_Data, timestamps: T_Timestamps = None, *args: any, **kwargs: any) -> (
            T_Data, T_Timestamps):
        if data is None:
            return None, None

        n_trials, n_channels, *n_features, n_times = data.shape

        if n_trials > 1:
            logger.warning(f"Received {n_trials} trials for Streaming. Sending separately in a row")

        if np.prod(n_features) * n_channels != self.lsl_channel_count:
            logger.warning(
                f"*n_features * n_channels (={np.prod(n_features) * n_channels}) does not match channel_count (={self.channel_count}). Not sending anything")
            return data, timestamps

        data_original = data.copy()
        data = np.moveaxis(data, -1, 1)  # Move times axis to position after trials

        # data.shape should now be (n_samples, channel_count) for lsl outlet
        if self.new_timestamps or timestamps is None:
            for i in range(n_trials):
                self.lsl_outlet.push_chunk(data[i].reshape((n_times, -1)).tolist(), pylsl.local_clock())
        elif isinstance(timestamps, collections.Iterable):
            # When multiple timestamps are given, push as single samples
            has_none_timestamps = any([timestamp is None for timestamp in timestamps])
            for i in range(n_trials):
                for j in range(n_times):
                    timestamp = timestamps[j]
                    if has_none_timestamps:
                        timestamp = pylsl.local_clock()
                    self.lsl_outlet.push_sample(data[i, j, :].flatten(), timestamp)
        elif isinstance(timestamps, (int, float)):
            # If the given timestamp is only a single value, push the chunk in a whole
            for i in range(n_trials):
                self.lsl_outlet.push_chunk(data[i].reshape((n_times, -1)).tolist(), timestamps)

        return data_original, timestamps

    def train(self, data: np.array, labels, timestamps=None, *args: any, **kwargs: any):
        return data, labels, timestamps

    def get_settings(self, *args, **kwargs):
        settings = super().get_settings(*args, **kwargs)
        settings.update(dict(
            stream_name=self.stream_name,
            source_id=self.source_id,
            lsl_type=self.lsl_type,
            nominal_srate=self.nominal_srate,
            channel_format=self.channel_format,
            chunk_size=self.chunk_size,
            max_buffered=self.max_buffered,
            new_timestamps=self.new_timestamps,
            feature_dimensions=self.feature_dimensions,
            _lsl_channel_count=self.lsl_channel_count,
        ))
        return settings
