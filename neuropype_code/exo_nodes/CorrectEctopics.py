import numpy as np
from statsmodels.nonparametric.smoothers_lowess import lowess
from scipy.interpolate import pchip_interpolate

import logging
from ...engine import *

logger = logging.getLogger(__name__)


class CorrectEctopics(Node):
    data = DataPort(Packet, "Data to process.")

    percentage = FloatPort(30, help="Percentage of ectopic detection.")
    span = IntPort(
        21, help="Span for moving average for ectopic replacement. Needs to be odd!")

    def __init__(self,
                 percentage: Union[int, None, Type[Keep]] = Keep,
                 span: Union[int, None, Type[Keep]] = Keep,
                 **kwargs):
        super().__init__(percentage=percentage, span=span, **kwargs)

    @classmethod
    def description(cls):
        return Description(
            name='Correct Ectopic Beats',
            description="""Finds and interpolates ectopic beats
            by replacing them with shape-preserving piecewise
            cubic spline interpolations.""",
            version='1.0.0')

    def _reset_states(self):
        self._half_length = 0   # window length to both sides of the sample

    @span.setter
    def span(self, v):
        self._half_length = (self.span-1)//2

    @data.setter
    def data(self, v):
        if self.percentage > 1:
            self.percentage /= 100

        chunk_criteria = {
            'nonempty': True, 'name_equals': 'interbeatintervals', 'with_axes': feature}

        for name, c in enumerate_chunks(v, **chunk_criteria):
            view = c.block[..., feature[['amplitude', 'interval'], 'names']]
            amp = view.data[..., 0]
            ibi = view.data[..., 1]

            # Locate ectopic
            # -extend signal
            # -calculate moving average over certain amount of samples
            # -remove mirrored areas
            # -detect deviation of actual from smoothed signal bigger than x%
            # (compare Von Tscharner 2017, there it was 30%)
            front_mirror = ibi[self._half_length-1::-1]
            end_mirror = ibi[-1:-1-self._half_length:-1]
            ibi_extended = np.hstack((front_mirror, ibi, end_mirror))

            # this seems to suggest, that the time stamps of the beats are equally distributed :/
            # using the actual time stamps also doesn't work, though,
            # since they incorporate the originally detected IBIs which we wish to correct
            ibi_smoothed = lowess(ibi_extended, range(len(ibi_extended)),
                                  frac=self.span/len(ibi_extended),
                                  return_sorted=False)

            ibi_smoothed = ibi_smoothed[self._half_length:-self._half_length]
            art = np.abs((ibi / ibi_smoothed) - 1) > self.percentage

            if sum(art) > 0:
                # Replace ectopics
                indices = np.arange(0, len(ibi))

                # this seems to suggest, that the time stamps of the beats are equally distributed :/
                # using the actual time stamps also doesn't work, though,
                # since they incorporate the originally detected IBIs we wish to correct
                ibi_out = pchip_interpolate(indices[~art], ibi[~art], indices)
                amp_out = pchip_interpolate(indices[~art], amp[~art], indices)

                view.data = np.transpose(np.vstack((amp_out, ibi_out)))
                c.block = view

                if sum(art)/len(art) > 0.05:
                    logger.warning('Corrected >5% of all ibis')

        self._data = v
