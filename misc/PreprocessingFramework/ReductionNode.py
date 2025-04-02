from typing import Union, List, Callable
from collections.abc import Iterable
import importlib

from misc.PreprocessingFramework.DataProcessor import check_data_dimensions, T_Data, T_Timestamps
from misc.PreprocessingFramework.ProcessingNode import ProcessingNode

import logging
logger = logging.getLogger(__name__)


class ReductionNode(ProcessingNode):
    # def __init__(self, settings: dict, in_channel_labels: list):
    def __init__(self, in_channel_labels: List[str],
                 functions: List[dict],
                 **settings):
        """
        :param in_channel_labels:
        :param functions: list of dicts, e.g., [dict(module='numpy', name='var', args=dict(axis=-1, keepdims=True))}
        :param settings:
        """

        # "name": "var",
        # "args": {"axis": -1, "keepdims": true}
        super().__init__(in_channel_labels, **settings)

        self.functions: List[dict] = functions if functions is not None else []

        self._functions: List[Callable] = []
        self._arguments: List[dict] = []

        for f_info in self.functions:
            module = importlib.import_module(f_info["module"])
            self._functions.append(getattr(module, f_info["name"]))

            args = f_info['args'] if 'args' in f_info else dict()
            self._arguments.append(args)

    @check_data_dimensions
    def process(self, data: T_Data, timestamps: T_Timestamps = None, *args: any, **kwargs: any) -> (
            T_Data, T_Timestamps):

        if data is None:
            return None, None

        for f, f_args in zip(self._functions, self._arguments):
            data = f(data, **f_args)

        timestamps = self.timestamp_reduction(timestamps)

        return data, timestamps

    def get_settings(self, *args, **kwargs):
        settings = super().get_settings(*args, **kwargs)
        settings['functions'] = self.functions
        return settings

    def timestamp_reduction(self, timestamps) -> Union[float, None]:
        """
        Reduce timestamps to a single value or None
        :param timestamps:
        :return:
        """
        if isinstance(timestamps, (int, float)):
            return [timestamps]
        elif isinstance(timestamps, Iterable):
            return [timestamps[-1]]
        elif timestamps is None:
            return None
        else:
            logger.warning(f"timestamps is of unsupported type: {type(timestamps)=}")
            return None

