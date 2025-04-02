import numpy as np
import logging
from collections import OrderedDict
from ...engine import *

logger = logging.getLogger(__name__)


class InterBeatIntervals(Node):
    detected_peaks = DataPort(Packet, "Data to process.", IN)
    intervals = DataPort(Packet, "Processed data.", OUT)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def description(cls):
        return Description(
            name='Extract Inter-Beat Intervals',
            description="""Extracts inter-beat intervals from time 
                stamps. Requires the 'xxx-peaks' stream from the 
                RDetection node and converts it to a chunk with 
                feature (amplitude & inter-beat interval) and time axes.""",
            version='1.0.0')

    @detected_peaks.setter
    def detected_peaks(self, v):
        chunk_criteria = {'nonempty': True,
                          'name_endswith': '-peaks', 'with_axes': instance}

        if has_any_chunks(v, **chunk_criteria):
            _, c = find_first_chunk(v, **chunk_criteria)

            view = c.block
            peak_times = view.axes[instance].times
            peak_intervals = np.diff(peak_times)*1000

            view = Block(data=np.vstack((view.data[:-1], peak_intervals)),
                         axes=(FeatureAxis(names=['amplitude', 'interval'],
                                           units=['microVolt', 'milliseconds']),
                               TimeAxis(times=peak_times[1:]))
                         )

            c.block = view
            c.props['has_markers'] = False

            self._intervals = Packet(chunks={'interbeatintervals': c})
            return

        self._intervals = None
