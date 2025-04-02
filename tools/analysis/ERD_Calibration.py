"""
Script to process motor imagery data
- Compute spatial Laplacian filter - to extract C3 or C4
- Compute Fast Fourier Transform to compute the Power Spectrum and target alpha peak
- Normalize data with Reference value and compute threshold (using preprocessed data)
- Plot ERD/ERS analysis with data acquired with the pythonBCI during rest and motor imagery

History:

based on ERDCalibration_MNE by Annalisa

13/03/2022 by Niels:
    * added GUI optional file selector
    * changed laterality to refer to laterality of hand movements (was laterality of brain signal before)
    * laterality is now automatically set by 'laterality' parameter of the FeedbackStates Stream
    * cleaned up plotting code, combined plots into one single window
    * added table with results (RV, TH) below plots
    * changed computation of Laplace filter so it works both with 3 ref-ch and 4 ref-ch configurations
    * changed time axis of plot to seconds instead of samples

14/02/2023 by Mareike:
    * added various names (SourceEEG, SourceData, LiveAmp...) to select data stream
    * added plot of whole timeseries of preprocessed data

06/04/2023 by Niels:
    * removed unused bits of code
    * re-ordered layout and spacing of plots
    * added labels and other details to plots

"""
import sys
import os
sys.path.append(os.getcwd())
import numpy as np
import pyxdf
import mne
from misc.xdf2mne import stream2raw
from misc.XDF_utils import find_channel_index, get_parameters_from_xdf_stream
from matplotlib import pyplot as plt
import matplotlib
matplotlib.use('Qt5Agg')
matplotlib.rcParams['toolbar'] = 'None'
from misc.enums import Side
from helpers.analysis_file_selector import select_file_dialog
from misc.burg.burg_utils import calc_burg_spectrum

plot_spectrum_method = 'burg'    # fft or burg

filepath = None             # set to None to have graphical file selection, set to a path to have that file processed without interruption
show_newest_n_files = 5     # number of recently recorded files that are shown in file selection dialog

if filepath is None:

    # show graphical dialog to pick file
    filepath = select_file_dialog(show_newest_n_files)

    # if filepath is still None -> no file was selected, stop script
    if filepath is None:
        exit()


# Load data from xdf file
# find correct streams (randomly assigned during recording)
stream, fileheader = pyxdf.load_xdf(filepath, dejitter_timestamps=True, select_streams=[{'name': 'SourceEEG'}, {'name': 'SourceData'}, {'name': 'LiveAmpSN-054211-0207'}, {'name': 'LiveAmpSN-054208-0183'}])
stream = stream[0]
stream['time_series'] /= 1000000

marker_stream, _ = pyxdf.load_xdf(filepath, dejitter_timestamps=True, select_streams=[{'name': 'TaskOutput'}])
marker_stream = marker_stream[0]

preprocessed_stream, _ = pyxdf.load_xdf(filepath, dejitter_timestamps=True, select_streams=[{'name': 'PreprocessedData'}])
preprocessed_stream = preprocessed_stream[0]

feedback_stream, _ = pyxdf.load_xdf(filepath, dejitter_timestamps=True, select_streams=[{'name': 'FeedbackStates'}])
feedback_stream = feedback_stream[0]

# Select the laterality of the hand for which motor imagery / motor attemt was executed
# LEFT  (hand) -> brain signal from right hemisphere (C4)
# RIGHT (hand) -> brain signal from right hemisphere (C3)
Laterality = Side(get_parameters_from_xdf_stream(feedback_stream)['laterality'])

# Extract raw and preprocessed data, convert into MNE raw_data object and assign as annotations the markers
raw, events, event_id = stream2raw(stream, marker_stream=marker_stream, marker_out=3)
preprocessed_data, ev, ev_id = stream2raw(preprocessed_stream,marker_stream=marker_stream, marker_out=3)

# Montage definition - Target channels - Band pass filtering
# easycap_montage = mne.channels.make_standard_montage("easycap-M1")
# montage = mne.io.Raw.set_montage(raw, montage=easycap_montage)

sampling_freq = raw.info['sfreq']
bci_freq = preprocessed_stream['info']['effective_srate']
targets = {'prep': ['µC3', 'µC4']}
prep_channel = find_channel_index(preprocessed_stream, targets['prep'])
data_prep = preprocessed_data.pick_channels([ch for ch in targets['prep']])

filt_data = raw.copy().filter(l_freq=6, h_freq=30)

if Laterality is Side.RIGHT:
    targetC3 = ['C3']
    targetLaplace = ['F3','Cz','P3','T7']
    laplace_data = filt_data.copy().pick_channels(targetC3)
    ref_data = filt_data.copy().pick_channels(targetLaplace, ordered=False)
    #Compute Laplace
    laplaceC3 = np.sum(ref_data._data[:], axis=0) * (1/len(ref_data.ch_names)) # this works for 3 & 4 ch laplace
    laplace_data._data = laplace_data._data - laplaceC3
elif Laterality is Side.LEFT:
    targetC4 = ['C4']
    targetLaplace = ['F4','Cz','P4','T8']
    laplace_data = filt_data.copy().pick_channels(targetC4)
    ref_data = filt_data.copy().pick_channels(targetLaplace, ordered=False)
    laplaceC4 = np.sum(ref_data._data[:], axis=0) * (1/len(ref_data.ch_names))
    laplace_data._data =  laplace_data._data - laplaceC4

# Extract events from annotations
Close_events = mne.events_from_annotations(raw, regexp="CLOSE") #Motor imagery task
Relax_events = mne.events_from_annotations(raw, regexp="RELAX") #Relax task

# Extract epochs from events
close_epochs = mne.Epochs (laplace_data, Close_events[0], tmin=0,tmax=5, baseline=None, preload=True)
relax_epochs = mne.Epochs (laplace_data, Relax_events[0], tmin=0, tmax=5, baseline=None, preload=True)


# Calculate Power spectrum with FFT for PSD plot
#  - hann the signal before to avoid bleeding
close_trials = close_epochs._data * np.hanning(close_epochs._data.shape[2]) * 2
relax_trials = relax_epochs._data * np.hanning(relax_epochs._data.shape[2]) * 2

#  - Real FFT because we just have real signals
#  - build abs because we aren't interested in phase
rfft_close = abs(np.fft.rfft(close_trials))
rfft_relax = abs(np.fft.rfft(relax_trials))

#  - multiply by two because we discard the "negative" frequencies
#  - divide by signal length for normalization
rfft_close = rfft_close * 2 / close_trials.shape[2]
rfft_close_mean = np.square(rfft_close).mean(axis=(0,1), keepdims=False)

rfft_relax = rfft_relax * 2 /relax_trials.shape[2]
rfft_relax_mean = np.square(rfft_relax).mean(axis=(0,1), keepdims=False)
#rfft_relax_mean = np.mean (rfft_relax,0)

# - get frequencies corresponding to FFT signal (the same for close or relax trials)
fftfreq = np.fft.rfftfreq(close_trials.shape[2], d=1/sampling_freq)
start = int(round(4 / (fftfreq[1] - fftfreq[0])))
end = 4 * start
mask_alpha = np.logical_and(fftfreq>start,fftfreq<end)

rfft_close_alpha = rfft_close_mean[start:end]
rfft_relax_alpha = rfft_relax_mean[start:end]
fftfreq_alpha = fftfreq[start:end]

if plot_spectrum_method != 'fft':
    # burg spectra
    close_spectra = []
    relax_spectra = []

    evals = 15
    bin_width = 0.02
    n_bins = int(1 + 1/bin_width * 12)
    model_order = int(sampling_freq * 0.8)


    for tr in close_trials:
        spectrum, freqs = calc_burg_spectrum(tr.flatten()-tr.mean(), foi=10.0, nbins=n_bins, bin_width=bin_width, evals_per_bin=evals,
                                             output_type='power', fs=sampling_freq, model_order=model_order, fast_version=True)
        close_spectra.append(spectrum)

    for tr in relax_trials:
        spectrum, freqs = calc_burg_spectrum(tr.flatten()-tr.mean(), foi=10.0, nbins=n_bins, bin_width=bin_width, evals_per_bin=evals,
                                             output_type='power', fs=sampling_freq, model_order=model_order, fast_version=True)
        relax_spectra.append(spectrum)

    close_spectra = np.array(close_spectra)
    relax_spectra = np.array(relax_spectra)

    burg_frequs = freqs.copy()
    close_burg_spectrum = close_spectra.mean(axis=0)
    relax_burg_spectrum = relax_spectra.mean(axis=0)


# Calculate reference value (RV) on preprocessed data from Start on and normalize the data based on the RV
start = int(round(15 * bci_freq)) # Skip the first 15 seconds

if Laterality is Side.RIGHT:
    data_prepC3 = data_prep.copy().pick(targets['prep'][0])
    rv = data_prepC3.get_data([0],start=start).mean()
    # Extract Close and Relax trials from the preprocessed data
    Close_processed_events = mne.events_from_annotations(data_prepC3, regexp="CLOSE")
    Relax_processed_events = mne.events_from_annotations(data_prepC3, regexp="RELAX")
    close_preprocessed_epochs = mne.Epochs(data_prepC3, Close_processed_events[0], tmin=0, tmax=5, baseline=None,
                                           preload=True)
    relax_preprocessed_epochs = mne.Epochs(data_prepC3, Relax_processed_events[0], tmin=0, tmax=5, baseline=None,
                                           preload=True)
    # Normalize close and relax trials
    norm_close = (close_preprocessed_epochs._data / rv) - 1
    norm_relax = (relax_preprocessed_epochs._data/rv)-1


elif Laterality is Side.LEFT:
    data_prepC4 = data_prep.copy().pick(targets['prep'][1])
    rv = preprocessed_data.get_data([1],start=start).mean()
    # Extract Close and Relax trials from the preprocessed data
    Close_processed_events = mne.events_from_annotations(data_prepC4, regexp="CLOSE")
    Relax_processed_events = mne.events_from_annotations(data_prepC4, regexp="RELAX")
    close_preprocessed_epochs = mne.Epochs (data_prepC4,Close_processed_events[0], tmin=0,tmax=5, baseline=None, preload=True)
    relax_preprocessed_epochs = mne.Epochs (data_prepC4, Relax_processed_events[0], tmin=0, tmax=5, baseline=None, preload=True)

    # Normalize close and relax trials
    norm_close = (close_preprocessed_epochs._data/rv) - 1
    norm_relax = (relax_preprocessed_epochs._data/rv)-1

# Calculate threshold - extract mean value of the close runs
close_mn = norm_close.copy().mean(axis=(0,2))
counter = 0
valid_trial = []
for x in range(len(norm_close)):
    if norm_close[x].mean() <= 0:
        valid_trial.append(counter)
        valid_trial[counter] = norm_close[x]
        counter += 1

valid_trials = np.concatenate(valid_trial)
close_TH = valid_trials.mean()

# print RV
print('RV : ' + str(rv))
print('easy TH : ' + str(close_mn))
print('hard TH : ' + str(close_TH))

# Average close and relax trials
close_prep = norm_close.mean(axis=0)
relax_prep = norm_relax.mean(axis=0)



# ======================== #
#       PLOTTING           #
# ======================== #

if Laterality is Side.LEFT:
    title = 'C4'
    colorClose = "tab:orange"
elif Laterality is Side.RIGHT:
    title = 'C3'
    colorClose = "tab:red"
colorRelax = "tab:blue"


# start plotting
# fig = plt.figure("ERD Analysis")
fig = plt.figure("ERD Analysis", layout="constrained")
spec = fig.add_gridspec(6, 2)

# Plot power spectrum
ax0 = fig.add_subplot(spec[0:4, 0])
plt.sca(ax0)

def plot_power_spec(relax_fftfreq, relax_mean_power,
                    close_fftfreq, close_mean_power,
                    title, side, color):
    """Plot power spectrum: plot mean power spectra of close and
    relax trials."""

    plt.title("{} power spectrum".format(title))
    plt.xlabel("frequency [$Hz$]")
    plt.ylabel("power [$(µV)^2$]")
    plt.grid(color='#cccccc', axis='x')

    plt.xticks(list(range(4,17)))

    plt.plot(relax_fftfreq, relax_mean_power,
             label="relax", color=colorRelax)
    plt.plot(close_fftfreq, close_mean_power,
             label="motor imagery/attempt " + side, color=color)
    plt.legend(loc="upper right")


if plot_spectrum_method == 'fft':
    plot_power_spec(fftfreq_alpha, rfft_relax_alpha,
                  fftfreq_alpha, rfft_close_alpha,
                  title, Laterality.value, colorClose)
else:
    plot_power_spec(burg_frequs, relax_burg_spectrum,
                    burg_frequs, close_burg_spectrum,
                    title, Laterality.value, colorClose)


# Plot Close and Relax trials
ax = fig.add_subplot(spec[0:3, 1])
plt.sca(ax)

close_time_in_seconds = np.arange(close_prep.size)/bci_freq
relax_time_in_seconds = np.arange(relax_prep.size)/bci_freq
plt.plot(relax_time_in_seconds, relax_prep[0],  linestyle='solid', label="Relax", color=colorRelax)
plt.plot(close_time_in_seconds, close_prep[0], linestyle='solid', label="Motor imagery/attempt", color=colorClose) # for the Opening Task Module
plt.hlines(close_mn, xmin=0, xmax=relax_time_in_seconds[-1], colors='black', linestyles='dashed', label="easy threshold")
plt.hlines(close_TH, xmin=0, xmax=relax_time_in_seconds[-1], colors='red', linestyles='dashed', label="hard threshold")
plt.legend()

plt.title('Motor Imagery/Attempt vs. Relax trials : ' + title)
plt.xlabel('time [s]')
plt.ylabel('relative µ modulation')


# plot a table displaying the reference and threshold vALUES
ax = fig.add_subplot(spec[3, 1])
plt.sca(ax)
# hide axes
fig.patch.set_visible(False)
ax.axis('off')
ax.axis('tight')
plt.table([
    ['Reference Value (RV):', np.round(rv, 1)],
    ['Easy Threshold:', -np.round(close_mn.flatten()[0], 2)],
    ['Hard Threshold:', -np.round(close_TH, 2)]
], loc='center')


# plot the entire time-series of the preprocessed signal
ax = fig.add_subplot(spec[-2:, :])
plt.sca(ax)

if Laterality is Side.RIGHT:
    timearray = np.arange(preprocessed_stream['time_series'][:, 1].size) / bci_freq
    ax.plot(timearray, preprocessed_stream['time_series'][:, 1], label='Preprocessed C3', color='black', lw=1)

if Laterality is Side.LEFT:
    timearray = np.arange(preprocessed_stream['time_series'][:, 2].size) / bci_freq
    ax.plot(timearray, preprocessed_stream['time_series'][:, 2], label='Preprocessed C4', color='black', lw=1)

plt.hlines(rv, 0, timearray[-1], color='#888888', ls='--', lw=1.0, label='reference value')

plt.xlabel('time [s]')
plt.ylabel('µ modulation')


close_events_idx = Close_processed_events[0][:].ravel()
close_events_idx = close_events_idx[close_events_idx>1]/bci_freq

relax_events_idx = Relax_processed_events[0][:].ravel()
relax_events_idx = relax_events_idx[relax_events_idx>1]/bci_freq


for i, idx in enumerate(close_events_idx):
    label = 'close' if i == 1 else None
    ax.axvspan(idx, idx+5, alpha=0.15, facecolor='C1', label=label)

for i, idx in enumerate(relax_events_idx):
    label = 'relax' if i == 1 else None
    ax.axvspan(idx, idx+5, alpha=0.15, facecolor='C0', label=label)

plt.legend()
plt.title('Preprocessed data')

figManager = plt.get_current_fig_manager()
figManager.window.showMaximized()
plt.show()

