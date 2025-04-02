import numpy as np
import logging
from collections import OrderedDict
from ...engine import *

logger = logging.getLogger(__name__)


class SlidingBuffer(Node):
    data = DataPort(Packet, "Data to process.")

    window_length = IntPort(100, help="Signal window length to process (in seconds).")
    shift_window = IntPort(90, help="Shift processing window by this many seconds.")
    
    def __init__(self, 
                 window_length: Union[int, None, Type[Keep]] = Keep,
                 shift_window: Union[int, None, Type[Keep]] = Keep,
                 **kwargs):
        self._reset_states()
        super().__init__(window_length=window_length,
                         shift_window=shift_window,
                         **kwargs)

    @classmethod
    def description(cls):
        return Description(
            name='Sliding Buffer',
            description="""Buffers up data until window_length is reached,
            then shifts buffer by shift_window and starts buffering again.
            Should also work with irregularly sampled data.""",
            version='1.0.0')
    
    def _reset_states(self):
        self._buf = {}          # block buffer
        self._time_offset = 0   # start time of new buffer window


    @data.setter
    def data(self, v):
        for n, c in enumerate_chunks(v, nonempty=True, with_axes=time):            
            
            # buffer up incoming data (from IBI)
            try:
                self._buf[n] = concat(time, self._buf[n], c.block)
            except KeyError:
                self._buf[n] = c.block
                self._time_offset = self._buf[n].axes[time].times[0]

            buffer_len = self._buf[n].axes[time].times[-1] - self._time_offset
            num_win = (buffer_len - self.window_length)//self.shift_window + 1

            if num_win > 0:
                # if buffer is long enough, output latest full buffer
                self._time_offset += (num_win-1)*self.shift_window
                c.block = self._buf[n][
                    ..., time[self._time_offset:(self._time_offset + self.window_length), 'seconds'], ...]

                # shift buffer window
                self._time_offset += self.shift_window
                self._buf[n] = self._buf[n][..., time[self._time_offset:, 'seconds'], ...]

            else:
                c.block = Block()

        self._data = v