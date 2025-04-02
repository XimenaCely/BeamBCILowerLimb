from misc.PreprocessingFramework.DataProcessor import check_data_dimensions, T_Timestamps, T_Data
from misc.PreprocessingFramework.ProcessingNode import ProcessingNode

from typing import Union, List

import numpy as np
from scipy import signal

import matplotlib.pyplot as plt
import logging

logger = logging.getLogger(__name__)


class IIRFilterNode(ProcessingNode):
    # def __init__(self, in_channel_labels: List[str], sfreq: float, filter_length: int = 499, f_highpass: float = 5,
    #             f_lowpass: float = 30, **settings):

    def __init__(self,
                 in_channel_labels: List[str],
                 sfreq: float,
                 order: int = 1,
                 btype: str = 'bandpass',   # highpass, lowpass, bandpass, bandstop
                 ftype: str = 'butter',  # butter, cheby1, cheby2, ...
                 fpass: Union[float, List[float]] = [1, 30],
                 fstop: Union[float, List[float]] = [0.5, 31],
                 gstop: float = 50.0,
                 gpass: float = 3.0,

                 **settings):

        super().__init__(in_channel_labels, **settings)

        self.sfreq: float = None

        self.order = None
        self.btype = None
        self.ftype = None
        self.fpass = None
        self.fstop = None
        self.gpass = None
        self.gstop = None

        self.sos = None
        self.zf = None

        self._init_filter(sfreq=sfreq, order=order, btype=btype, ftype=ftype, fpass=fpass, fstop=fstop, gpass=gpass, gstop=gstop)

    def _init_filter(self,
                     sfreq: float,
                     order: int,
                     btype: str,
                     ftype: str,
                     fpass: float,
                     fstop: float,
                     gpass: float,
                     gstop: float
                     ):

        self.zf = None
        self.sfreq = sfreq

        self.order = order
        self.btype = btype
        self.ftype = ftype

        self.fpass = fpass
        self.fstop = fstop
        self.gpass = gpass
        self.gstop = gstop

        self.sos = None


        if ftype.lower() == 'butter':
            [minorder, wn] = signal.buttord(wp=self.fpass, ws=self.fstop, gstop=self.gstop, gpass=self.gpass, fs=self.sfreq)

        elif ftype.lower() == 'cheby1':
            [minorder, wn] = signal.cheb1ord(wp=self.fpass, ws=self.fstop, gstop=self.gstop, gpass=self.gpass, fs=self.sfreq)

        else:
            raise Exception("Filter type '{:s}' is not supported.".format(ftype))

        self.sos = signal.iirfilter(N=self.order, Wn=wn, rp=self.gpass, rs=self.gstop, btype=self.btype,
                                    ftype=self.ftype, output='sos', fs=self.sfreq)
        self.init_zi = signal.sosfilt_zi(self.sos)

    @check_data_dimensions
    def process(self, data: T_Data, timestamps: T_Timestamps = None, *args: any, **kwargs: any) -> (
            T_Data, T_Timestamps):

        if data is None or data.shape[-1] == 0:
            return None, None

        # initialize filter with zeros if not initialized yet
        if self.zf is None:
            # initialize with mean along time axis of data:
            self.zf = np.multiply.outer(self.init_zi, data.mean(axis=-1))

            # rearrange dimension correctly (https://docs.scipy.org/doc/scipy/reference/generated/scipy.signal.sosfilt.html)
            self.zf = np.moveaxis(self.zf, 1, -1)

        # filter data
        data, self.zf = signal.sosfilt(self.sos, data, axis=-1, zi=self.zf)

        return data, timestamps

    def clear(self, *args, **kwargs):
        self.zf = None

    def plot_filter_response(self, ax=None):
        if ax is None:
            ax = plt.gca()
        w, h = signal.sosfreqz(sos=self.sos, fs=self.sfreq)

        ax.plot(w, 20 * np.log10(np.abs(h)))
        ax.set_title('Digital filter frequency response')
        ax.set_ylabel('Amplitude Response [dB]')

        ax.set_xlabel('Frequency [Hz]')
        ax.grid()
        return ax

    def get_settings(self, *args, **kwargs):
        settings = super().get_settings(*args, **kwargs)
        settings['sfreq'] = self.sfreq
        settings['order'] = self.order
        settings['ftype'] = self.ftype
        settings['btype'] = self.btype
        settings['fpass'] = self.fpass
        settings['fstop'] = self.fstop
        settings['gpass'] = self.gpass
        settings['gstop'] = self.gstop

        return settings


if __name__ == '__main__':
    num_in_channels = 5
    node = IIRFilterNode(in_channel_labels=[f"Ch{i}" for i in range(num_in_channels)],
                         sfreq=500, order=1, ftype="butter", btype="highpass", fpass=0.1, fstop=0.05, gpass=3, gstop=50)

    data = np.random.random([num_in_channels, 100])
    print(node.process(data))

    import matplotlib
    matplotlib.use('qtagg')
    plt.figure()
    node.plot_filter_response()
    plt.show()
