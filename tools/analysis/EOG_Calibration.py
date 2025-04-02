'''
EOG Analysis

Script to calculate EOG threshold and visualize EOG signals based on Elisa's Script 'EOGCalibrationOffline.py'

update 11/10/2021 by Annalisa:  Also calculate true positives and false positives

update 13/03/2022 by Niels:     Added graphical file selection dialog which allows browsing for files or selecting a
                                recently recorded file

'''

import sys
import os
sys.path.append(os.getcwd())
import numpy as np
import pyxdf
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Qt5Agg')
matplotlib.rcParams['toolbar'] = 'None'

from helpers.analysis_file_selector import select_file_dialog


filepath = None         # set to None to have graphical file selection, set to a path to have that file processed without interruption
trial_len = 2           # length of trials in seconds
thresh_factor = 0.8     # factor which is multiplied with median of trials maxima to determine treshold

show_newest_n_files = 5 # number of recently recorded files that are shown in file selection dialog

if filepath is None:

    # show graphical dialog to pick file
    filepath = select_file_dialog(show_newest_n_files)

    # if filepath is still None -> no file was selected, stop script
    if filepath is None:
        exit()


def convert_to_numpy(name, eog):
    n_trials = len(eog)

    if n_trials == 0:
        return np.array([])

    target_len = int(round(trial_len * BCI_freq))
    cutoff = min([len(e) for e in eog if len(e) >= target_len * 0.9])
    np_eog = np.stack([e[:cutoff] for e in eog if len(e) >= cutoff])

    if n_trials != np_eog.shape[0]:
        print("Attention: Removed ", n_trials - np_eog.shape[0],
              "trial(s) because more than 10% of the #samples were missing.")

    return np_eog


def extract_hov_trials():
    # separate eog data from left and right trials and
    # save trial directions and corresponding boolean indices
    eog_left = []
    eog_right = []
    eog_left_long = []
    eog_right_long = []

    trials = []
    trial_start = 0
    trial_samples = int(float(trial_len) * BCI_freq)

    for ix, cue in enumerate(cues[1:], start=1):
        if cue != cues[ix - 1]:
            if cue == cue_map['HOVLEFT']:
                trials += [(left, ix)]
                eog_left += [eog[(eog_times >= cue_times[ix]) &
                                 (eog_times <= cue_times[ix] + trial_len)]]
            elif cue == cue_map['HOVRIGHT']:
                trials += [(right, ix)]
                eog_right += [eog[(eog_times >= cue_times[ix]) &
                                  (eog_times <= cue_times[ix] + trial_len)]]
            elif cue == cue_map['HOVLEFT_LONG']:
                trials += [(left_long, ix)]
                eog_left_long += [eog[(eog_times >= cue_times[ix]) &
                                      (eog_times <= cue_times[ix] + trial_len)]]
            elif cue == cue_map['HOVRIGHT_LONG']:
                trials += [(right_long, ix)]
                eog_right_long += [eog[(eog_times >= cue_times[ix]) &
                                       (eog_times <= cue_times[ix] + trial_len)]]

    # convert to numpy matrices
    eog_left = convert_to_numpy("left eog", eog_left)
    eog_right = convert_to_numpy("right eog", eog_right)
    eog_left_long = convert_to_numpy("left_long eog", eog_left_long)
    eog_right_long = convert_to_numpy("right long eog", eog_right_long)

    return trials, eog_left, eog_right, eog_left_long, eog_right_long


def get_mean(eog_trials):
    if eog_trials.size == 0:
        return np.ones(eog_trials.shape[-1])*np.nan

    return eog_trials.mean(0)


def plot_hovs(title, xlabel, ylabel, eog, mean, medMax, thresh, color):
    if eog.size > 0:
        plt.title(title)
        if xlabel:
            plt.xlabel(xlabel)
        if ylabel:
            plt.ylabel(ylabel)
        plt.ylim(graphmin, graphmax)

        x_axis = np.linspace(
            0, mean.shape[0]/BCI_freq, mean.shape[0], endpoint=False)
        for y in eog:
            line, = plt.plot(
                x_axis, y, linewidth=trialLineWidth, color=trialColor)
        line.set_label("trials")

        plt.plot(x_axis, mean, color=color, label="mean")
        plt.plot(
            x_axis, np.ones(len(x_axis)) * medMax, "--",
            linewidth=trialLineWidth, color=trialColor, label="median of maxima"
        )
        plt.plot(
            x_axis, np.ones(len(x_axis)) * thresh,
            "--", linewidth=trialLineWidth, color=color, label="threshold"
        )

        plt.legend(loc="upper " + ("left" if "right" in title else "right"))
        # plt.tight_layout()



# Load data from xdf file
# find correct stream (randomly assigned during recording)
streams, fileheader = pyxdf.load_xdf(filepath, dejitter_timestamps=True)
for x in range(len(streams)):
    if streams[x]['info']['name'][0] == 'SourceEEG': #RAW DATA (all channels)
        stream = streams[x]
    if streams[x]['info']['name'][0] == 'TaskOutput': #MARKERS (CLOSE, RELAX)
        marker_stream = streams[x]
    if streams[x]['info']['name'][0] == 'PreprocessedData': #PREPROCESSED DATA (C3, C4 and EOG)
        preprocessed_stream = streams[x]


# get cue mappings
cue_map = dict(zip(
    marker_stream['info']['desc'][0]['mappings'][0]['cues'][0].keys(),
    map(lambda x: int(x[0]),
        marker_stream['info']['desc'][0]['mappings'][0]['cues'][0].values())
))
#
# # extract channel indices from streams
#eog_channel = LSLStreamInfoInterface.find_channel_index(preprocessed_stream, [targets['eog']])
# cue_channel = find_channel_index(task_stream, [targets['cue']])

# extract time series and time stamps
eog = preprocessed_stream['time_series'][:, 0].squeeze() #todo make sure this is always in idx 0!
eog_times = preprocessed_stream['time_stamps']
cues = np.array(marker_stream['time_series'])[:, 0].squeeze().astype(int)
cue_times = marker_stream['time_stamps']

# start timestamps with 0
start_time = min(cue_times[0], eog_times[0])
eog_times -= start_time
cue_times -= start_time

# extract update frequency
BCI_freq = round(preprocessed_stream['info']['effective_srate'])

# define cue sides
left = int(marker_stream['info']['desc'][0]['mappings'][0]['cues'][0]['HOVLEFT'][0])
right = int(marker_stream['info']['desc'][0]['mappings'][0]['cues'][0]['HOVRIGHT'][0])
left_long = int(marker_stream['info']['desc'][0]['mappings'][0]['cues'][0]['HOVLEFT_LONG'][0])
right_long = int(marker_stream['info']['desc'][0]['mappings'][0]['cues'][0]['HOVRIGHT_LONG'][0])

(trials, eog_left, eog_right,
 eog_left_long, eog_right_long) = extract_hov_trials()

# compute mean curves
meanLeft = get_mean(eog_left)
meanRight = get_mean(eog_right)
meanLeftLong = get_mean(eog_left_long)
meanRightLong = get_mean(eog_right_long)

# calculate left and right thresholds
if eog_left.size > 0:
    medMaxLeft = np.median(np.max(eog_left, 1))
    threshLeft = medMaxLeft * thresh_factor
else:
    medMaxLeft = np.nan
    threshLeft = np.nan

if eog_right.size > 0:
    medMaxRight = np.median(np.min(eog_right, 1))
    threshRight = medMaxRight * thresh_factor
else:
    medMaxRight = np.nan
    threshRight = np.nan

try:
    print('Threshold Right (',thresh_factor*100,'%): ', round(threshRight))
except:
    print('No right threshold: no right trials tested')
try:
    print('Threshold Left (',thresh_factor*100,'%): ', round(threshLeft))
except:
    print('No left threshold: no left trials tested')

# test for wrong relations:
if threshLeft <= threshRight:
    print("Error: Left Threshold smaller than or equal to right threshold: left",
          threshLeft, "right", threshRight)

# generate signal that detects when eog exceeds thresholds
detected = np.zeros(eog.shape)
for ix, val in enumerate(eog):
    if val > threshLeft:
        detected[ix] = left
    elif val < threshRight:
        detected[ix] = right

# classify peaks
true_positives = 0
false_positives = 0
false_negatives = 0
wrong_direction = 0
unknown_failure = 0

left_dur = []
right_dur = []
left_dur_long = []
right_dur_long = []

for trial in trials:
    start = 0
    end = 0
    comp_val, trial_start = trial
    #cue_side = np.sign(comp_val) # I think before was eiter positive or negative!
    cue_side = comp_val
    signal = detected[(eog_times >= cue_times[trial_start]) &
                      (eog_times <= cue_times[trial_start] + trial_len)] #it's extracting only the signal during the cue presentation,
    # #but detected is already the classified signal!

    for i in range(1, len(signal)):

        if signal[i - 1] == 0: #if the signal is zero
            if signal[i] == cue_side:
                if start == 0:
                    start = eog_times[i]  # first reaching the threshold
                else:
                    false_positives += 1  # additional start -> false pos

            elif signal[i] != 0 and signal[i] != cue_side:
                wrong_direction += 1  # wrong direction

        elif signal[i - 1] == cue_side: #if the signal is the cue marker (that means > threshold)
            if start != 0 and end == 0 and signal[i] == 0:
                end = eog_times[i]  # first going below threshold
                true_positives += 1

    if start == 0 and end == 0:
        false_negatives += 1
    elif start == 0 and end != 0:
        unknown_failure += 1

    else:
        if comp_val == left:
            left_dur += [end - start]
        elif comp_val == right:
            right_dur += [end - start]
        elif comp_val == left_long:
            left_dur_long += [end - start]
        elif comp_val == right_long:
            right_dur_long += [end - start]

print("Left  durations: {}\nRight durations: {}\nLeft  long durations: {}\nRight long durations: {}"
      .format([round(left, 5) for left in left_dur],
              [round(right, 5) for right in right_dur],
              [round(left, 5) for left in left_dur_long],
              [round(right, 5) for right in right_dur_long])
      )
print("True positives: {}\nFalse negatives: {}\nFalse positives: {}\nWrong direction: {}\nUnknown failure: {}\n"
      .format(true_positives, false_negatives, false_positives, wrong_direction, unknown_failure))

### Plot data ###
colorLeft = "tab:orange"
colorRight = "tab:green"
trialColor = "lightgrey"
trialLineWidth = 0.75

# plot classified bipolar signal and cues
plt.figure("EOG Analysis")
grid = plt.GridSpec(3, 2)
plt.subplot(grid[0, :])
plt.title("Classified Bipolar Signal")
plt.xlabel("time [$s$]")
plt.ylabel("amplitude [$µV$]")

left_done = False
right_done = False

for cue, start in trials:
    span = plt.axvspan(
        cue_times[start], cue_times[start] + trial_len,
        facecolor=colorLeft if cue == 5 else colorRight,
        alpha=0.2
    )
    if not left_done and cue == 5:
        span.set_label("cue: left")
        left_done = True
    elif not right_done and cue == 6:
        span.set_label("cue: right")
        right_done = True

plt.plot(eog_times,
         np.ma.masked_where((detected > 0) & (detected < 0), eog),
         color=trialColor)
plt.plot(eog_times, np.ma.masked_where(detected != left, eog),
         label="class: left", color=colorLeft)
plt.plot(eog_times, np.ma.masked_where(detected != right, eog),
         label="class: right", color=colorRight)
plt.plot(eog_times, np.ones(len(eog_times)) * threshLeft,
         "--", linewidth=0.75, label="threshold: left", color=colorLeft)
plt.plot(eog_times, np.ones(len(eog_times)) * threshRight,
         "--", linewidth=0.75, label="threshold: right", color=colorRight)

plt.legend(loc="right")

# plot trials, trial means, medMax and thresholds
eogs = [eog
        for eog in [eog_left, eog_right, eog_left_long, eog_right_long]
        if eog.size > 0]

if len(eogs) > 0:
    graphmax = max([np.max(eog) for eog in eogs]) * 1.05
    graphmin = min([np.min(eog) for eog in eogs]) * 1.05

if eog_left.size > 0:
    plt.subplot(grid[1, 0])
    plot_hovs(
        "left: Thresh. at {:.0f}µV".format(
            threshLeft), "time [$s$]", "voltage [$µV$]",
        eog_left, meanLeft, medMaxLeft, threshLeft, colorLeft
    )
if eog_right.size > 0:
    plt.subplot(grid[1, 1])
    plot_hovs(
        "right: Thresh. at {:.0f}µV".format(
            threshRight), "time [$s$]", "voltage [$µV$]",
        eog_right, meanRight, medMaxRight, threshRight, colorRight
    )
if eog_left_long.size > 0:
    plt.subplot(grid[2, 0])
    plot_hovs(
        "left long: Thresh. at {:.0f}µV".format(
            threshLeft), "time [$s$]", "voltage [$µV$]",
        eog_left_long, meanLeftLong, medMaxLeft, threshLeft, colorLeft
    )
if eog_right_long.size > 0:
    plt.subplot(grid[2, 1])
    plot_hovs(
        "right long: Thresh. at {:.0f}µV".format(
            threshRight), "time [$s$]", "voltage [$µV$]",
        eog_right_long, meanRightLong, medMaxRight, threshRight, colorRight
    )

plt.subplots_adjust(left=0.05, bottom=0.05, right=0.95,
                    top=0.95, wspace=0.15, hspace=0.4)
figManager = plt.get_current_fig_manager()
figManager.window.showMaximized()
plt.show()