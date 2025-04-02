import numpy as np
import logging
from collections import OrderedDict
from ...engine import *

logger = logging.getLogger(__name__)


class ExtractTimeStamps(Node):
    indata = DataPort(Packet, "Data to process.")
    outdata = DataPort(Packet, "Processed data.")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    @classmethod
    def description(cls):
        return Description(name='Extract Time Stamps',
                           description="",
                           version='1.0.0')

    @indata.setter
    def indata(self, v):
        chunk_criteria = {'nonempty': True, 'with_axes': time}
        num = count_chunks(v, **chunk_criteria)
        if num == 0:
            self._outdata = None
            return
        if num > 1:
            warn_once("The given packet has more than one non-empty chunk; "
                      "casting only the first chunk.", logger=logger)
        _, c = find_first_chunk(v, **chunk_criteria)
        data = list(c.axes[time].times)
        if len(data) > 1:
            warn_once("The given data has more than one element; casting only"
                      "the last element.", logger=logger)
        self._outdata = data