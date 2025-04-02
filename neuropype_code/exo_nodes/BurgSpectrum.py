import logging
import numpy as np
from spectrum import arburg2, arma2psd
from scipy.integrate import simps

from ...engine import *

logger = logging.getLogger(__name__)


class BurgSpectrum(Node):
    data = DataPort(Packet, "Data to process.", INOUT)
    
    # Input parameters.
    create_bins = BoolPort(True, help="""If set, creates power spectrum bins 
        with adjustable frequency of interest, number of bins, bin width and 
        evaluations per bin. If not set, returns power spectrum from 0 to 
        Nyquist frequency based on nfft evaluation points.""")
    foi = FloatPort(0.0, help="Frequency of interest (center of bin).",
        verbose_name="Frequency of interest (when using bins)")
    nbins = IntPort(1, help="""Number of bins to be used. If uneven, FOI is the 
        center of the middle bin. If even, half of the bins cover frequencies 
        lower than the FOI bin.""",
        verbose_name="Number of bins (when using bins)")
    bin_width = FloatPort(1.0, help="""Width of the frequency bins in Hz. The 
        difference of last and first center should be an integer multiple of 
        bin width.""", verbose_name="Bin width (when using bins)")
    evals_per_bin = IntPort(15, help="""Number of equally distributed
        evaluation points per bin for estimating the spectrum. Must be larger 
        than or equal to bin width.""",
        verbose_name="Evaluations per bin (when using bins)")
    nfft = IntPort(None, help="""Evaluation points used for power spectrum 
        estimation. Note that the returned power spectrum will not have a 
        length of nfft but rather ~nfft/2.""")
    output_type = EnumPort("spectrum", ['spectrum', 'amplitude'],
        help="""Output spectrum or amplitude (square root of spectrum).""")

    def __init__(self,
                 create_bins: Union[bool, None, Type[Keep]] = Keep,
                 foi: Union[float, None, Type[Keep]] = Keep,
                 nbins: Union[int, None, Type[Keep]] = Keep,
                 bin_width: Union[float, None, Type[Keep]] = Keep,
                 evals_per_bin: Union[int, None, Type[Keep]] = Keep,
                 nfft: Union[int, None, Type[Keep]] = Keep,
                 output_type: Union[str, None, Type[Keep]] = Keep,
                 **kwargs):

        super().__init__(
            create_bins=create_bins, foi=foi, nbins=nbins,
            bin_width=bin_width, evals_per_bin=evals_per_bin,
            nfft=nfft, output_type=output_type, **kwargs)

    @classmethod
    def description(cls):
        return Description(name='Power Spectrum (Burg)',
            description="""Auto-regression based spectral estimator. 
            The frequency spectrum is estimated using auto-regression
            (Maximum Entropy Method (Burg)). The power spectrum can
            either be returned continuously over the whole frequency 
            range or in frequency bins with specified start and end bin. 
            Spectrum or amplitude can be chosen as output types.""",
            version='1.0.0')

    def _get_psd(self, data, fs, nfft, fres, psd_len):
        """Estimate power spectrum using Burg's maximum entropy method.
           Scale to get results close to those of BCI2000."""
        ar, rho, ref = arburg2(data, int(round(fs)/10))
        psd = arma2psd(A=ar[1:], rho=rho, T=fs, NFFT=nfft)
        psd = psd[0:psd_len] * 2

        # no mathematical explanation, not quite the same, 
        # closer: 2 * np.sqrt(np.pi)*np.pi**2 / fres
        return psd * (2*np.pi)**2/fres

    @data.setter
    def data(self, v):
        """Calculate the power spectrum of the given data using Burg's
        autoregression method.

        For an explanation of the method, see the articles:
        https://en.wikipedia.org/wiki/Autoregressive_model and
        https://en.wikipedia.org/wiki/Maximum_entropy_spectral_estimation
        """

        for _, chunk in enumerate_chunks(v, nonempty=True, allow_markers=False,
                                         with_axes=(time, space, instance)):

            # Set parameters
            fs = chunk.block.axes[time].nominal_rate

            if self.create_bins:
                nfft = int(fs / (self.bin_width/self.evals_per_bin))
                start_freq = (self.foi
                              - self.nbins//2 * self.bin_width
                              - self.bin_width/2)

            else:
                nfft = self.nfft

            fres = fs/nfft
            psd_len = int(np.floor(nfft/2) + 1)
            freqs = np.linspace(0, fs/2, psd_len)

            view = chunk.block[..., space, instance]
            space_ax = view.axes[space]
            instance_ax = view.axes[instance]

            # Allocate space for output matrix
            if self.create_bins:
                output = np.zeros((self.nbins, space_ax.length(), instance_ax.length()))
            else:
                output = np.zeros((psd_len, space_ax.length(), instance_ax.length()))

            # Estimate power spectrum for each instance and channel
            for i in range(instance_ax.length()):
                for s in range(space_ax.length()):
                    psd = self._get_psd(view.data[..., s, i], fs, nfft, fres, psd_len)

                    # Create bins from power spectrum
                    if self.create_bins:

                        for n in range(self.nbins):
                            low = start_freq + n*self.bin_width
                            high = low + self.bin_width
                            output[n, s, i] = simps(psd[(freqs >= low)
                                                        & (freqs <= high)],
                                                    dx=fres)
                            
                            # Add power from negative frequencies (same as positive)
                            if n == 0 and start_freq < 0:
                                output[n, s, i] += simps(freqs <= abs(start_freq),
                                                         dx=fres)

                    else:
                        output[:, s, i] = psd

            if self.output_type == 'amplitude':
                output = np.sqrt(output)

            # Generate new axes
            if self.create_bins:
                first_center = start_freq + self.bin_width/2
                freqs = np.linspace(first_center,
                                    first_center + (self.nbins-1)*self.bin_width,
                                    self.nbins)
            
            time_ax = axes.TimeAxis(instance_ax.times, nominal_rate=fs)
            freq_ax = axes.FrequencyAxis(freqs)
            chunk.block = Block(output, (freq_ax, space_ax, time_ax))
            chunk.props['has_markers'] = False

        self._data = v