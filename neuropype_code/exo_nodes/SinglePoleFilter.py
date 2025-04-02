import numpy as np
import logging

from ...engine import *

logger = logging.getLogger(__name__)


class SinglePoleFilter(Node):
    data = DataPort(Packet, "Data to process.", INOUT)

    time_const = FloatPort(0.5, help="Time constant for single-pole filter.")
    sampling_rate = IntPort(1, help="""BCI sampling rate. Usually recording
                                    sampling rate divided by chunk length.""")

    def __init__(self,
                 time_const: Union[float, None, Type[Keep]] = Keep,
                 sampling_rate: Union[int, None, Type[Keep]] = Keep,
                 **kwargs):
        self._reset_states()
        super().__init__(time_const=time_const,
                         sampling_rate=sampling_rate, **kwargs)

    @classmethod
    def description(cls):
        return Description(name='Single Pole Filter',
                           description="""""",
                           version='1.0.0')

    def _reset_states(self):
        self._y = 0

        # convert time-constant in sample blocks since LP filter
        # works on sample block basis
        t_block = self.time_const * self.sampling_rate
        self._decay_factor = np.exp(-1 / t_block)

    def on_signal_changed(self):
        self._reset_states()

    def on_port_assigned(self):
        self._reset_states()

    @data.setter
    def data(self, v):
        """Apply single pole IIR filter."""

        for _, chunk in enumerate_chunks(v, nonempty=True, allow_markers=False,
                                         with_axes=(time,)):
            view = chunk.block[..., time]

            for i in range(view.shape[-1]):
                if np.sum(view.data) not in [float('nan'), float('inf')]:
                    # same as: self.y = decay_factor*self.y + (1-decay_factor)*data
                    self._y += (1-self._decay_factor) * (view.data[..., i] - self._y)
                view.data[..., i] = self._y

            chunk.block = view
        self._data = v
