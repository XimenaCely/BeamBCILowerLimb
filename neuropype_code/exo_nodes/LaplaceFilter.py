import numpy as np
import logging
from collections import OrderedDict
from ...engine import *

# {'C3': 1, 'F3': -0.25, 'Cz': -0.25, 'P3': -0.25, 'T7': -0.25}
# {'C4': 1, 'F4': -0.25, 'Cz': -0.25, 'P4': -0.25, 'T8': -0.25}
# {'C3': 1, 'F3': 1, 'P3': 1, 'T7': 1, 'C4': -1, 'F4': -1, 'P4': -1, 'T8': -1}
# ['P3', 'F3', 'C3', 'Cz', 'T7', 'P4', 'F4', 'C4', 'T8']

logger = logging.getLogger(__name__)


class LaplaceFilter(Node):
    data = DataPort(Packet, "Data to process.")

    C3_weights = DictPort({}, help="""A dictionary indicating the Laplace 
                                weights for the EEG channels. Zero-channels 
                                can be omitted.""")
    C4_weights = DictPort({}, help="""A dictionary indicating the Laplace
                                weights for the EEG channels. Zero-channels 
                                can be omitted.""")
    EOG_weights = DictPort({}, help="""A dictionary indicating the Laplace
                                 weights for the EOG channels. Zero-channels 
                                 can be omitted.""")

    def __init__(self,
                 C3_weights: Union[dict, None, Type[Keep]] = Keep,
                 C4_weights: Union[dict, None, Type[Keep]] = Keep,
                 EOG_weights: Union[dict, None, Type[Keep]] = Keep,
                 **kwargs):
        super().__init__(C3_weights=C3_weights,
                         C4_weights=C4_weights,
                         EOG_weights=EOG_weights,
                         **kwargs)

    @classmethod
    def description(cls):
        return Description(name='Surface Laplace Filter',
                           description="""Apply Surface Laplace filter by 
                           calculating the dot product of the Laplace weights 
                           and the recorded channel signals. Only those channels
                           for which weights are given will produce an output.""",
                           version='1.0.0')

    @data.setter
    def data(self, v):
        """Apply Surface Laplace filter by calculating the dot product
           of the Laplace weights and the recorded channel signals."""

        for name, chunk in enumerate_chunks(v, nonempty=True,
                                            allow_markers=False, with_axes=(space, time)):

            view = chunk.block[space, ...]
            channels = view.axes[space].names
            
            # Create weight vectors from the EEG and EOG weights dictionaries
            # for calculation of the Surface Laplace Filter. Channels not
            # indicated in a dictionary will be assigned with 0 in the vector.
            C3_vals = [self.C3_weights.get(c, 0) for c in channels]
            C4_vals = [self.C4_weights.get(c, 0) for c in channels]
            EOG_vals = [self.EOG_weights.get(c, 0) for c in channels]

            filtered_eeg = np.dot(np.vstack((C3_vals, C4_vals)), view.data)
            filtered_eog = np.dot(EOG_vals, view.data)

            view[space[['C3', 'C4']], ...].data = filtered_eeg

            space_ax = SpaceAxis(names="bipolar EOG")
            time_ax = view.axes[time]
            eog_block = Block(data = filtered_eog,
                              axes = (space_ax, time_ax))
            
            view = concat(space, view, eog_block)
            chunk.block = view[space[['bipolar EOG', 'C3', 'C4']], ...]

        self._data = v