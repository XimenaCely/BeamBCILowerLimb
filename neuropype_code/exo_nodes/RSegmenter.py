import numpy as np
from biosppy.signals import ecg

import copy
import logging
from ...engine import *

logger = logging.getLogger(__name__)


class RSegmenter(Node):
    data = DataPort(Packet, "Data to process.")

    method = EnumPort('christov', ('christov', 'engzee', 'gamboa', 'hamilton', 'ssf'),
                      help="Method to be used for R peak detection.")
    thresh = FloatPort(
        None, help="Threshold between 0 and 1 (only used for engzee and ssf).")
    tolerance = FloatPort(
        None, help="Tolerance between 0 and 1 (only used for gamboa).")
    before = FloatPort(
        None, help="Search window size (seconds) before R-peak candidate (only used for ssf).")
    after = FloatPort(
        None, help="Search window size (seconds) before R-peak candidate (only used for ssf).")

    def __init__(self,
                 method: Union[str, None, Type[Keep]] = Keep,
                 thresh: Union[float, None, Type[Keep]] = Keep,
                 tolerance: Union[float, None, Type[Keep]] = Keep,
                 before: Union[float, None, Type[Keep]] = Keep,
                 after: Union[float, None, Type[Keep]] = Keep,
                 **kwargs):
        super().__init__(method=method, thresh=thresh,
                         tolerance=tolerance, before=before,
                         after=after, **kwargs)

    @classmethod
    def description(cls):
        return Description(
            name='R Peak Segmentation',
            description="""Finds R peaks in a single-channel ECG signal
                        and outputs an InstanceAxis with R peak amplitudes
                        and R peak times as time stamps.""",
            version='1.0.0')

    @data.setter
    def data(self, v):
        chunk_criteria = {'nonempty': True, 'with_axes': (time,)}

        for name, c in enumerate_chunks(v, **chunk_criteria):
            view = c.block[time, ...]
            fs = view.axes[time].nominal_rate

            if self.method == 'christov':
                r_indcs = ecg.christov_segmenter(
                    signal=view.data[:, 0], sampling_rate=fs)

            elif self.method == 'engzee':
                r_indcs = ecg.engzee_segmenter(
                    signal=view.data[:, 0], sampling_rate=fs,
                    threshold=self.thresh if self.thresh else 0.48)

            elif self.method == 'gamboa':
                r_indcs = ecg.gamboa_segmenter(
                    signal=view.data[:, 0], sampling_rate=fs,
                    tol=self.tol if self.tol else 0.002)

            elif self.method == 'hamilton':
                r_indcs = ecg.hamilton_segmenter(
                    signal=view.data[:, 0], sampling_rate=fs)

            elif self.method == 'ssf':
                r_indcs = ecg.ssf_segmenter(
                    signal=view.data[:, 0], sampling_rate=fs,
                    threshold=self.thresh if self.thresh else 20,
                    before=self.before if self.before else 0.03,
                    after=self.after if self.after else 0.01)

            r_times = view.axes[time].times[r_indcs]
            r_amps = view.data[r_indcs][:, 0]
            data = ['peak']*len(r_amps)

            marker_props = copy.deepcopy(c.props)
            marker_props.update({Flags.has_markers: True,
                                 Flags.has_targets: True,
                                 Flags.is_streaming: True})
            v.chunks[name + '-peaks'] = Chunk(
                Block(data=r_amps,
                      axes=(InstanceAxis(times=r_times, data=data),)),
                marker_props)

        self._data = v
