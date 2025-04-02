import numpy as np

import logging
from ...engine import *

logger = logging.getLogger(__name__)


class LineShiftFilter(Node):
    data = DataPort(Packet, "Data to process.")

    line_freq = FloatPort(50, help="Frequency to be removed.",
                          verbose_name="Line frequency")
    
    def __init__(self, line_freq: Union[float, None, Type[Keep]] = Keep,
                 **kwargs):
        super().__init__(line_freq=line_freq, **kwargs)

    @classmethod
    def description(cls):
        return Description(
            name='Line Shift Filter',
            description="""Removes single frequency component 
            without distorting adjacent frequency components.""",
            version='1.0.0')

    @data.setter
    def data(self, v):
        chunk_criteria = {'nonempty': True, 'with_axes': (time,)}

        for name, c in enumerate_chunks(v, **chunk_criteria):
            fs = c.block.axes[time].nominal_rate

            shift = (1/self.line_freq)*fs + 1
            shift_r = int(np.ceil(shift/2))
            shift_l = int(np.floor(shift/2))

            view = c.block[..., time]
            t_points = view.shape[-1]

            # shift to the right and to the left
            ecg1 = np.concatenate((np.zeros((*view.shape[:-1], shift_r)), view.data), axis=-1)
            ecg2 = np.concatenate((view.data[..., shift_l-1:], np.zeros((*view.shape[:-1], shift_l-1))), axis=-1)
            diff = ecg2[..., :t_points] - ecg1[..., :t_points]

            # replace start and end artefact from line shift filter with zeros
            diff[..., :shift_r+1] = 0
            diff[..., -1-shift_l:] = 0
            # de-mean to avoid mistake during recreation
            diff -= np.mean(diff, axis=-1)
            # recreate the filtered ecg (optional)
            view.data = np.cumsum(diff, axis=-1)/shift

            # gliding filter
            nmax = 3
            for _ in range(nmax):
                d1 = [view.data[..., 0]]
                d2 = [view.data[..., -1]]
                sig = np.concatenate((view.data, d2, d2), axis=-1) \
                         + np.concatenate((d1, d1, view.data), axis=-1) \
                         + 2 * np.concatenate((d1, view.data, d2), axis=-1)
                view.data = sig[..., 1:-1] / 4

            c.block = view

        self._data = v