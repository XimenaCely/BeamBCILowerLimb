import numpy as np

import copy
import logging
from ...engine import *

logger = logging.getLogger(__name__)


class RSAPorges(Node):
    data = DataPort(Packet, "Data to process.")

    epoch_dur = FloatPort(None, help="""Length of epochs based on which 
        ln-transformed variance is calculated.""",
                          verbose_name='Epoch duration')
    unit = EnumPort('seconds', ('seconds', 'samples'),
                    help="Unit in which the epoch duration is given.")

    def __init__(self,
                 epoch_dur: Union[float, None, Type[Keep]] = Keep,
                 unit: Union[str, None, Type[Keep]] = Keep,
                 **kwargs):
        super().__init__(epoch_dur=epoch_dur, unit=unit, **kwargs)

    @classmethod
    def description(cls):
        return Description(
            name='RSA Porges',
            description="""Calculates RSA according to Porges and Bohrer. 
                This is a time-domain calculation method and should be 
                superior to STD and HF power spectral calculation.
                Input is filtered HF_ibi signal (0.15-0.4Hz). Then 
                ln-transformed variance is processed of 30s epochs. 
                Afterwards, the mean of epochs is calculated 
                (Lewis et al. 2012).""",
            version='1.0.0')

    @data.setter
    def data(self, v):
        chunk_criteria = {'nonempty': True, 'with_axes': (time,),
                          'name_equals': 'interbeatintervals'}

        for name, c in enumerate_chunks(v, **chunk_criteria):
            view = c.block[..., time]
            times = c.block.axes[time].times

            # --- Preparation ---
            default_dur = 30
            if self.unit == 'seconds':
                epoch_len = self.epoch_dur if self.epoch_dur else default_dur
                n_epochs = int(np.round((times[-1] - times[0])/epoch_len))
            else:
                epoch_len = self.epoch_dur if self.epoch_dur \
                    else default_dur * view.axes[time].nominal_rate
                n_epochs = int(np.round(view.shape[-1]/epoch_len))

            # --- Processing RSA Porges & Bohrer ---
            rsa_epochs = []
            for n in range(n_epochs):
                rsa_epochs.append(np.log(
                    np.var([view[..., time[n * epoch_len + times[0]:(n + 1) * epoch_len + times[0], self.unit]].data])))

            time_stamp = times[-1]
            new_fs = 1/np.round(times.size/view.axes[time].nominal_rate, -1)
            marker_props = copy.deepcopy(c.props)
            v.chunks['hrv'] = Chunk(Block(data=[np.mean(rsa_epochs)],
                                          axes=(SpaceAxis(names=["rsa_porges"]),
                                                TimeAxis(times=[time_stamp],
                                                         nominal_rate=new_fs),)),
                                    marker_props)

        self._data = v
