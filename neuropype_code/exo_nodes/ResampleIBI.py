import numpy as np
from scipy.interpolate import Akima1DInterpolator

import logging
from ...engine import *

logger = logging.getLogger(__name__)


class ResampleIBI(Node):
    data = DataPort(Packet, "Data to process.")

    fs_resamp = FloatPort(4, help="Frequency the data should be resampled to.",
                          verbose_name="Output frequency")

    def __init__(self, fs_resamp: Union[float, None, Type[Keep]] = Keep,
                 **kwargs):
        super().__init__(fs_resamp=fs_resamp, **kwargs)

    @classmethod
    def description(cls):
        return Description(
            name='Resample interbeat intervals',
            description="""Resampling is done with cubic spline interpolation 
            (based on Akima algorithm). To avoid overshoots at start and 
            end, signal starts just from first to last IBI datapoint.""",
            version='1.0.0')

    @data.setter
    def data(self, v):
        chunk_criteria = {'nonempty': True, 'with_axes': (time,)}

        for name, c in enumerate_chunks(v, **chunk_criteria):
            t = c.block.axes[time].times
            y = c.block[..., time].data

            # Cubic spline interpolation
            # -Interpolate time vector
            t_vec = np.arange(np.floor(t[0]), np.ceil(t[-1]), 1 / self.fs_resamp)
            y_out = Akima1DInterpolator(t, y, axis=-1).__call__(t_vec)

            # Correct overshoot errors at signal borders:
            # -Cut signal from 1st to last IBI datapoint
            start_ind = np.where(t_vec - (np.floor(t[0] * self.fs_resamp) / self.fs_resamp) < 0.001)[0][-1]
            end_ind = np.where(t_vec - (np.ceil(t[-1] * self.fs_resamp) / self.fs_resamp) < 0.001)[0][-1]

            y_out_cut = y_out[..., start_ind + 1:end_ind]
            t_vec_cut = t_vec[..., start_ind + 1:end_ind]

            # Output time vector and interpolated IBIs
            c.block = Block(data=y_out_cut,
                            axes=(FeatureAxis(names=['amplitude', 'interval'],
                                              units=['microVolt', 'milliseconds']),
                                  TimeAxis(times=t_vec_cut, nominal_rate=self.fs_resamp))
                            )

        self._data = v
