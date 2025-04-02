from misc.burg.burg_from_spectrum import arburg2, arma2psd, arburg

import numpy as np
from scipy.integrate import simps

from typeguard import typechecked
from typing import Tuple

@typechecked()
def _get_psd(data: np.ndarray, fs: float, nfft: int, fres: float, psd_len: int, model_order: int, fast_version: bool):
    """Estimate power spectrum using Burg's maximum entropy method.
       Scale to get results close to those of BCI2000."""
    if fast_version:
        ar, rho, ref = arburg2(data, model_order)
    else:
        ar, rho, ref = arburg(data, model_order)
    psd = arma2psd(A=ar[1:], rho=rho, T=fs, NFFT=nfft)
    psd = psd[0:psd_len] * 2

    # no mathematical explanation, not quite the same,
    # closer: 2 * np.sqrt(np.pi)*np.pi**2 / fres
    return psd * (2 * np.pi) ** 2 / fres

@typechecked()
def calc_burg_spectrum(
        signal, foi: float = 11, nbins: int = 1, bin_width: float = 3.0, evals_per_bin: int = 15,
        output_type: str = 'amplitude', fs: float = 500, model_order: int = 10, fast_version: bool = True) -> Tuple[np.ndarray, np.ndarray]:
    """
    Uses the burg algorithm to compute a frequency spectrum of a signal

        Parameters:
            signal: the signal to generate the spectrum of
            foi:    center frequency of the spectrum
            nbins:  number of bins centered around foi
            bin_width:  width of each bin in Hz
            evals_per_bin:
            output_type: 'power' or 'amplitude'
            fs:     sampling frequency of the signal
            model_order: order of the AR model
            fast_version: whether to use a ~10x faster but wrongly scaled version of the algorithm

        Returns:
            (output, frequencies):  Arrays containing the spectrum and the center frequencies of the bins


    """

    # fs = 500
    nfft = int(fs / (bin_width / evals_per_bin))
    start_freq = (foi
                  - nbins // 2 * bin_width
                  - bin_width / 2)

    fres: float = fs / nfft
    psd_len = int(np.floor(nfft / 2) + 1)
    freqs = np.linspace(0, fs / 2, psd_len)

    # output = np.zeros((nbins, space_ax.length(), instance_ax.length()))
    output = np.zeros(nbins, dtype=np.float64)
    psd = _get_psd(signal, fs, nfft, fres, psd_len, model_order, fast_version)

    for n in range(nbins):
        low = start_freq + n * bin_width
        high = low + bin_width
        output[n] = simps(psd[(freqs >= low)
                              & (freqs <= high)],
                          dx=fres)

        # Add power from negative frequencies (same as positive)
        if n == 0 and start_freq < 0:
            output[n] += simps(freqs <= abs(start_freq),
                               dx=fres)

    if output_type == 'amplitude':
        output = np.sqrt(output)

    # frequency labels
    first_center = start_freq + bin_width / 2
    freqs = np.linspace(first_center,
                        first_center + (nbins - 1) * bin_width,
                        nbins)

    return (output, freqs)


# example using burg spectrum
if __name__ == '__main__':

    # set random seed to always get same results
    np.random.seed(1)

    # specify sampling frequency, frequency of the signal
    fs = 1000
    f: float = 14.0

    # generate timestamps and signal
    tt = np.linspace(0, 0.4, 401)
    sig = np.sin(2 * np.pi * f * tt) + np.random.normal(size=401)

    # specify burg spectrum parameters
    evals_per_bin = 15
    bin_width: float = 3
    foi = 10.0
    nbins = 1
    model_order = 100

    amplitudes, freqs = calc_burg_spectrum(sig,
                                           foi=foi,
                                           nbins=nbins,
                                           bin_width=bin_width,
                                           evals_per_bin=evals_per_bin,
                                           output_type='amplitude',
                                           fs=fs,
                                           model_order=model_order,
                                           fast_version=True)

    print(freqs, amplitudes)

    import timeit

    print(
        round(timeit.timeit(
            lambda : calc_burg_spectrum(sig, foi=foi, nbins=nbins, bin_width=bin_width, evals_per_bin=evals_per_bin, output_type='amplitude', fs=fs, model_order=model_order, fast_version=True),
            number=100
        ) / 100 * 1000, 5), "ms"
    )