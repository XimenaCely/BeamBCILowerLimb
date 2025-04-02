import logging
import numpy as np
from bisect import bisect_left

from ...engine import *

logger = logging.getLogger(__name__)


class PickTimes(Node):
    data1 = DataPort(Packet, "Data to pick from.", IN)
    data2 = DataPort(Packet, "Data with pick times.", IN, mutating=False)
    outdata = DataPort(Packet, "Data to process.", OUT)

    # Input parameters.
    chunks = ListPort([], list, help="""Specify the chunks to be used for 
                      downsampling. E.g., [('eog', 'eeg')] takes eog chunk of 
                      the stream connected to the first data port and the eeg 
                      chunk connected to the second data port and downsamples 
                      the longer of the two time series to the time stamps of 
                      the shorter. Per default ([]) assumes that both time 
                      series have chunks with the same names.""")
    
    def __init__(self, chunks: Union[List[list], None, Type[Keep]] = Keep,
                 **kwargs):
        super().__init__(chunks=chunks, **kwargs)

    @classmethod
    def description(cls):
        return Description(name='Pick Times',
            description="""Takes time series of two packets and downsamples the 
                        longer time series by picking data at or closest to
                        the time stamps of the shorter time series. This node 
                        assumes that the time series chunks of both packets 
                        have the same names. Time stamps must be (strictly) 
                        increasing. Dejitter if in doubt.""",
            version='1.0.0')

    def get_new_indices(self, chunk1, chunk2=None):
        
        chunk2 = chunk2 if chunk2 else chunk1
        time_ax1 = self.data1.chunks[chunk1].block.axes[time]
        time_ax2 = self.data2.chunks[chunk2].block.axes[time]

        # determine longer time series
        # set time series to be downsampled and selection times
        data1_len = time_ax1.length()
        data2_len = time_ax2.length()

        if data1_len == data2_len:
            return
        elif data1_len > data2_len:
            times_to_pick_from = time_ax1.times
            time_stamps = time_ax2.times
            view = self.data1.chunks[chunk1].block[..., time]
        elif data2_len > data1_len:
            times_to_pick_from = time_ax2.times
            time_stamps = time_ax1.times
            view = self.data2.chunks[chunk2].block[..., time]

        # find indices of time stamps in the longer time series,
        # closest to those of the shorter time series
        time_indcs = np.zeros(len(time_stamps), dtype=int)

        for t in range(len(time_stamps)):
            pos = bisect_left(times_to_pick_from, time_stamps[t])

            if pos == 0:
                time_indcs[t] = pos
            elif pos == len(times_to_pick_from):
                time_indcs[t] = pos-1

            else:
                before = times_to_pick_from[pos - 1]
                after = times_to_pick_from[pos]

                if before - time_stamps[t] <= after - time_stamps[t]:
                   time_indcs[t] = pos-1
                else:
                   time_indcs[t] = pos

        return view, time_indcs


    @Node.update.setter
    def update(self, v):
        """
        Assumes time stamps are sorted. Returns data from longer time series
        closest to time stamps of shorter time series.
        """
        if self.chunks:
            for chunk1, chunk2 in self.chunks:
                if (has_any_chunks(self.data1, name_equals=chunk1, nonempty=True, 
                                  with_axes=(time), allow_markers=False) and
                   has_any_chunks(self.data2, name_equals=chunk2, nonempty=True, 
                                  with_axes=(time), allow_markers=False)):

                    view, new_indcs = self.get_new_indices(chunk1, chunk2)
                    self.data1.chunks[chunk1].block = view[..., new_indcs]

        else:
            for name, chunk in enumerate_chunks(self.data1, allow_markers=False,
                                                nonempty=True, with_axes=(time)):                
                if has_any_chunks(self.data2, name_equals=name, nonempty=True, 
                                  with_axes=(time), allow_markers=False):
                    view, new_indcs = self.get_new_indices(name)
                    chunk.block = view[..., new_indcs]

        self._outdata = self.data1