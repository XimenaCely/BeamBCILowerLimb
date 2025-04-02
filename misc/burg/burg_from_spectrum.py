"""
The following source code is based on the work done by Thomas Cokelaer that
has been published in the python library 'spectrum', specifically version 0.8.1.

The original code can be found here: https://github.com/cokelaer/spectrum

Thus, the following license applies to all the source code in this file:

Copyright (c) 2011-2017, Thomas Cokelaer
All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

* Redistributions of source code must retain the above copyright notice, this
  list of conditions and the following disclaimer.

* Redistributions in binary form must reproduce the above copyright notice,
  this list of conditions and the following disclaimer in the documentation
  and/or other materials provided with the distribution.

* Neither the name of spectrum nor the names of its
  contributors may be used to endorse or promote products derived from
  this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""

import numpy as np
from numpy.fft import fft

from collections import deque


def arburg(X, order):
    r"""Estimate the complex autoregressive parameters by the Burg algorithm.

    .. math:: x(n) = \sqrt{(v}) e(n) + \sum_{k=1}^{P+1} a(k) x(n-k)

    :param x:  Array of complex data samples (length N)
    :param order: Order of autoregressive process (0<order<N)
    :param criteria: select a criteria to automatically select the order

    :return:
        * A Array of complex autoregressive parameters A(1) to A(order). First
          value (unity) is not included !!
        * P Real variable representing driving noise variance (mean square
          of residual noise) from the whitening operation of the Burg
          filter.
        * reflection coefficients defining the filter of the model.

    .. plot::
        :width: 80%
        :include-source:

        from pylab import plot, log10, linspace, axis
        from spectrum import *

        AR, P, k = arburg(marple_data, 15)
        PSD = arma2psd(AR, sides='centerdc')
        plot(linspace(-0.5, 0.5, len(PSD)), 10*log10(PSD/max(PSD)))
        axis([-0.5,0.5,-60,0])

    .. note::
        1. no detrend. Should remove the mean trend to get PSD. Be careful if
           presence of large mean.
        2. If you don't know what the order value should be, choose the
           criterion='AKICc', which has the least bias and best
           resolution of model-selection criteria.

    .. note:: real and complex results double-checked versus octave using
        complex 64 samples stored in marple_data. It does not agree with Marple
        fortran routine but this is due to the simplex precision of complex
        data in fortran.

    :reference: [Marple]_ [octave]_
    """
    if order <= 0.:
        raise ValueError("order must be > 0")

    if order > len(X):
        raise ValueError("order must be less than length input - 2")

    x = np.array(X)
    N = len(x)

    # Initialisation
    # ------ rho, den
    rho = sum(abs(x)**2.) / float(N)  # Eq 8.21 [Marple]_
    den = rho * 2. * N

    #p =0
    a = np.zeros(0, dtype=complex)
    ref = np.zeros(0, dtype=complex)
    ef = x.astype(complex)
    eb = x.astype(complex)
    temp = 1.
    #   Main recursion

    for k in range(0, order):

        # calculate the next order reflection coefficient Eq 8.14 Marple
        num = sum([ef[j]*eb[j-1].conjugate() for j in range(k+1, N)])
        den = temp * den - abs(ef[k])**2 - abs(eb[N-1])**2
        kp = -2. * num / den #eq 8.14

        temp = 1. - abs(kp)**2.
        new_rho = temp * rho

        # this should be after the criteria
        rho = new_rho
        if rho <= 0:
            raise ValueError("Found a negative value (expected positive strictly) %s. Decrease the order" % rho)

        a.resize(a.size+1,refcheck=False)
        a[k] = kp
        if k == 0:
            for j in range(N-1, k, -1):
                save2 = ef[j]
                ef[j] = save2 + kp * eb[j-1]          # Eq. (8.7)
                eb[j] = eb[j-1] + kp.conjugate() *  save2

        else:
            # update the AR coeff
            khalf = (k+1)//2  # FIXME here khalf must be an integer
            for j in range(0, khalf):
                ap = a[j] # previous value
                a[j] = ap + kp * a[k-j-1].conjugate()      # Eq. (8.2)
                if j != k-j-1:
                    a[k-j-1] = a[k-j-1] + kp * ap.conjugate()    # Eq. (8.2)

            # update the prediction error
            for j in range(N-1, k, -1):
                save2 = ef[j]
                ef[j] = save2 + kp * eb[j-1]          # Eq. (8.7)
                eb[j] = eb[j-1] + kp.conjugate() *  save2

        # save the reflection coefficient
        ref.resize(ref.size+1, refcheck=False)
        ref[k] = kp

    return a, rho, ref

def arburg2(X, order):
    """This version is 10 times faster than arburg, but the output rho is not correct.

    returns [1 a0,a1, an-1]
    """
    x = np.array(X)
    N = len(x)

    if order <= 0.:
        raise ValueError("order must be > 0")

    # Initialisation
    # ------ rho, den
    rho = sum(abs(x)**2.) / N  # Eq 8.21 [Marple]_
    den = rho * 2. * N

    # ------ backward and forward errors
    ef = np.zeros(N, dtype=complex)
    eb = np.zeros(N, dtype=complex)
    for j in range(0, N):  #eq 8.11
        ef[j] = x[j]
        eb[j] = x[j]

    # AR order to be stored
    a = np.zeros(1, dtype=complex)
    a[0] = 1
    # ---- rflection coeff to be stored
    ref = np.zeros(order, dtype=complex)

    temp = 1.
    E = np.zeros(order+1)
    E[0] = rho

    for m in range(0, order):
        #print m
        # Calculate the next order reflection (parcor) coefficient
        efp = ef[1:]
        ebp = eb[0:-1]
        #print efp, ebp
        num = -2.* np.dot(ebp.conj().transpose(),  efp)
        den = np.dot(efp.conj().transpose(),  efp)
        den += np.dot(ebp,  ebp.conj().transpose())
        ref[m] = num / den

        # Update the forward and backward prediction errors
        ef = efp + ref[m] * ebp
        eb = ebp + ref[m].conj().transpose() * efp

        # Update the AR coeff.
        a.resize(len(a)+1, refcheck=False)
        a = a + ref[m] * np.flipud(a).conjugate()

        # Update the prediction error
        E[m+1] = np.real((1 - ref[m].conj().transpose()*ref[m]) * E[m])
        #print 'REF', ref, num, den
    return a, E[-1], ref


def arma2psd(A=None, B=None, rho=1., T=1., NFFT=4096, sides='default',
        norm=False):
    r"""Computes power spectral density given ARMA values.

    This function computes the power spectral density values
    given the ARMA parameters of an ARMA model. It assumes that
    the driving sequence is a white noise process of zero mean and
    variance :math:`\rho_w`. The sampling frequency and noise variance are
    used to scale the PSD output, which length is set by the user with the
    `NFFT` parameter.

    :param array A:   Array of AR parameters (complex or real)
    :param array B:   Array of MA parameters (complex or real)
    :param float rho: White noise variance to scale the returned PSD
    :param float T:   Sampling frequency in Hertz to scale the PSD.
    :param int NFFT:  Final size of the PSD
    :param str sides: Default PSD is two-sided, but sides can be set to centerdc.

    .. warning:: By convention, the AR or MA arrays does not contain the
        A0=1 value.

    If :attr:`B` is None, the model is a pure AR model. If :attr:`A` is None,
    the model is a pure MA model.

    :return: two-sided PSD

    .. rubric:: Details:

    AR case: the power spectral density is:

    .. math:: P_{ARMA}(f) = T \rho_w \left|\frac{B(f)}{A(f)}\right|^2

    where:

    .. math:: A(f) = 1 + \sum_{k=1}^q b(k) e^{-j2\pi fkT}
    .. math:: B(f) = 1 + \sum_{k=1}^p a(k) e^{-j2\pi fkT}

    .. rubric:: **Example:**

    .. plot::
        :width: 80%
        :include-source:

        import spectrum.arma
        from pylab import plot, log10, legend
        plot(10*log10(spectrum.arma.arma2psd([1,0.5],[0.5,0.5])), label='ARMA(2,2)')
        plot(10*log10(spectrum.arma.arma2psd([1,0.5],None)), label='AR(2)')
        plot(10*log10(spectrum.arma.arma2psd(None,[0.5,0.5])), label='MA(2)')
        legend()

    :References: [Marple]_
    """
    if NFFT is None:
        NFFT = 4096

    if A is None and B is None:
        raise ValueError("Either AR or MA model must be provided")

    psd = np.zeros(NFFT, dtype=complex)

    if A is not None:
        ip = len(A)
        den = np.zeros(NFFT, dtype=complex)
        den[0] = 1.+0j
        for k in range(0, ip):
            den[k+1] = A[k]
        denf = fft(den, NFFT)

    if B is not None:
        iq = len(B)
        num = np.zeros(NFFT, dtype=complex)
        num[0] = 1.+0j
        for k in range(0, iq):
            num[k+1] = B[k]
        numf = fft(num, NFFT)

    # Changed in version 0.6.9 (divided by T instead of multiply)
    if A is not None and B is not None:
        psd = rho / T * abs(numf)**2. / abs(denf)**2.
    elif A is not None:
        psd = rho / T / abs(denf)**2.
    elif B is not None:
        psd = rho / T * abs(numf)**2.


    psd = np.real(psd)
    # The PSD is a twosided PSD.
    # to obtain the centerdc
    if sides != 'default':
        from . import tools
        assert sides in ['centerdc']
        if sides == 'centerdc':
            psd = tools.twosided_2_centerdc(psd)

    if norm == True:
        psd /= max(psd)

    return psd


def twosided_2_centerdc(data):
    """Convert a two-sided PSD to a center-dc PSD"""
    N = len(data)
    # could us int() or // in python 3
    newpsd = np.concatenate((cshift(data[N//2:], 1), data[0:N//2]))
    newpsd[0] = data[-1]
    return newpsd


def cshift(data, offset):
    """Circular shift to the right (within an array) by a given offset

    :param array data: input data (list or numpy.array)
    :param int offset: shift the array with the offset

    .. doctest::

        >>> from spectrum import cshift
        >>> cshift([0, 1, 2, 3, -2, -1], 2)
        array([-2, -1,  0,  1,  2,  3])

    """
    # the deque method is suppose to be optimal when using rotate to shift the
    # data that playing with the data to build a new list.
    if isinstance(offset, float):
        offset = int(offset)
    a = deque(data)
    a.rotate(offset)
    return np.array(a)  #convert back to an array. Is it necessary?
