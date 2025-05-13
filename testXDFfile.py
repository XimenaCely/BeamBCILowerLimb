import pyxdf
import os
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
from misc.burg.burg_utils import calc_burg_spectrum
import pprint as pp
###############################################################################
# file
file_path = r"C:\Users\aurax\Downloads\Task_1_281.xdf"
###############################################################################
# Verificar si el archivo existe
if not os.path.exists(file_path):
    raise FileNotFoundError(f"El archivo no existe: {file_path}")

# Cargar el archivo XDF
try:
    streams, header = pyxdf.load_xdf(file_path)
    print(f"Archivo cargado con {len(streams)} streams.")
    streams = pyxdf.resolve_streams(file_path)
except Exception as e:
    print(f"Error al cargar el archivo: {e}")


import copy
import random
import numpy as np
import pickle
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.metrics import accuracy_score
from sklearn.metrics import confusion_matrix
from sklearn.metrics import roc_auc_score
import time
import pyxdf
import numpy as np
import matplotlib.pyplot as plt

def band_pass_filter(signal, fs, f_low, f_high):
    freqs = np.fft.fftfreq(signal.shape[0], 1 / fs)
    mask = (freqs >= f_low) & (freqs <= f_high)
    filtered_signal_fft = np.fft.fft(signal, axis=0) * mask[:, np.newaxis]
    return np.real(2 * np.fft.ifft(filtered_signal_fft, axis=0))

def filter_episodes(episodes, fs, f_low, f_high):
    filtered_episodes = np.empty_like(episodes)
    for i, window in enumerate(episodes):
        filtered_episodes[i] = band_pass_filter(window, fs, f_low, f_high)
    return filtered_episodes

def compute_power(episodes):
    return np.mean(episodes**2, axis=1)  
    


preprocessed_stream, _ = pyxdf.load_xdf(file_path, select_streams=[{"name": "SourceEEG"}])
preprocessed_stream = preprocessed_stream[0]
pp.pprint(preprocessed_stream['info'])
task_stream, _ = pyxdf.load_xdf(file_path, select_streams=[{"name": "TaskOutput"}])
task_stream = task_stream[0]

# timestamps and data to operate on
prep_timestamps = preprocessed_stream['time_stamps']
prep_data = preprocessed_stream["time_series"]
print("prep_data: ",prep_data.shape, "prep_timestamps: ",prep_timestamps.shape)  # Shape of preprocessed data
# select µCz channel 
# prep_data = prep_data[:, 11]

markers = np.array(task_stream['time_series'])[:, 3] #cues are in the 4th column of the task stream
print("prep_data: ", prep_data.shape, "markers: ",markers.shape)  # Shape of markers
# onset timestamps of episodes
close_onset_times = task_stream['time_stamps'][markers == 'WALK']
relax_onset_times = task_stream['time_stamps'][markers == 'RELAX']

print("close_onset_times: ",len(close_onset_times), "relax_onset_times: ",len(relax_onset_times))

episode_length_seconds = 5.0

# need this to make sure we have equal amount of samples in each close_episode due to jitter - see in following lines: dt/2 is subtracted
dT = np.diff(prep_timestamps).mean() 

# slice data into episodes -> shape: [n_episodes, n_samples], e.g. [10, 125] for 10 episodes, 125 samples (= 5s @ 25Hz)
walk_episodes = np.array([prep_data[np.logical_and(prep_timestamps >= t-dT/2, prep_timestamps < t-dT/2+episode_length_seconds)] for t in close_onset_times])
relax_episodes = np.array([prep_data[np.logical_and(prep_timestamps >= t-dT/2, prep_timestamps < t-dT/2+episode_length_seconds)] for t in relax_onset_times])
print("walk_episodes: ", walk_episodes.shape, "relax_episodes: ", relax_episodes.shape)
# filtering data
fs_eeg = 250  # Sampling frequency
f_low = 8     # Lower cutoff frequency
f_high = 30   # Upper cutoff frequency

filtered_walk_episodes = filter_episodes(walk_episodes, fs_eeg, f_low, f_high)
filtered_relax_episodes = filter_episodes(relax_episodes, fs_eeg, f_low, f_high)

# Print the shapes of the filtered data to verify
print("Filtered close_episodes shape:", filtered_walk_episodes.shape)
print("Filtered relax_episodes shape:", filtered_relax_episodes.shape)

baseline_power = compute_power(filtered_relax_episodes)  
event_power = compute_power(filtered_walk_episodes) 
erd_ers = (event_power - baseline_power) / baseline_power * 100  
mean_erd_ers = np.mean(erd_ers, axis=0) 
print("erd_ers: ",erd_ers.shape)
plt.figure(figsize=(10, 6))
channel_names = ['F3', 'F4', 'C3', 'C4', 'P3', 'P4', 'F7', 'F8', 'T7', 'T8', 'FZ', 'CZ', 'PZ']
plt.bar(channel_names, mean_erd_ers, color='blue', alpha=0.7)


# Add labels and title
plt.xlabel("Channels")
plt.ylabel("ERD/ERS (%)")
plt.title("Event-Related Desynchronization/Synchronization (ERD/ERS)")
plt.axhline(0, color='black', linestyle='--', linewidth=1)  # Add a horizontal line at 0
plt.grid(True)

# Show the plot
plt.tight_layout()
plt.show()

n_channels = len(channel_names)

# Crear un montaje estándar (10-20)
montage = mne.channels.make_standard_montage('standard_1020')

# Crear un objeto Info
info = mne.create_info(ch_names=channel_names, sfreq=250, ch_types='eeg', montage=montage)

# Crear un objeto Evoked con los datos de ERD/ERS
evoked = mne.EvokedArray(mean_erd_ers[:, np.newaxis], info, tmin=0)

# Dibujar el topoplot
fig, ax = plt.subplots(figsize=(8, 6))
mne.viz.plot_topomap(mean_erd_ers, evoked.info, axes=ax, show=True, cmap='RdBu_r', vmin=-50, vmax=50)
plt.title("Topoplot de ERD/ERS")
plt.show()

print("toopoplot done")

window_index = 4  # Index of the window to plot
filtered_window = filtered_walk_episodes[window_index]  # Shape: (n_samples, n_channels)

# Create a time axis for the window
n_samples = filtered_window.shape[0]
time_axis = np.linspace(0, episode_length_seconds, n_samples)

# Plot the filtered data for each channel in the window
plt.figure(figsize=(10, 6))
for channel_index in range(filtered_window.shape[1]):
    plt.plot(time_axis, filtered_window[:, channel_index], label=f"Channel {channel_index + 1}")

plt.show()
