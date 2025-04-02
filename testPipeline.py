import time
import globals
from pylsl import resolve_byprop, StreamInlet, local_clock
from misc import LSLStreamInfoInterface
import numpy as np

from misc.PreprocessingFramework import ProcessingPipeline
from misc.PreprocessingFramework import IIRFilterNode, BurgSpectrumNode, SpatialFilterNode, LSLStreamNode, BufferNode, \
    ChannelSelectorNode, SinglePoleFilterNode

streams = resolve_byprop("name", globals.STREAM_NAME_RAW_SIGNAL, minimum=1, timeout=20)

lsl_inlet = StreamInlet(streams[0], max_buflen=360, max_chunklen=1, recover=True)

# set sampling frequency and channel count from streaminfo
fs = streams[0].nominal_srate()
channel_count = streams[0].channel_count()

# read channel labels
inlet_channel_labels = LSLStreamInfoInterface.get_channel_labels(lsl_inlet.info())

# load preprocessing pipeline from json
# with open(globals.PYTHONBCI_PATH / 'SMR-ERD-Pipeline.json', 'r') as fp:
#    settings = json.load(fp)

# pipeline = ProcessingPipeline(inlet_channel_labels, **settings)

laplace_output_channel_labels = ['bipolar EOG', 'C3', 'C4']
laplace_output_channel_count = len(laplace_output_channel_labels)

# spatial filter weight matrix: weights[out_index, in_index]
laplace_weights = np.zeros([laplace_output_channel_count, channel_count])

# EOG channel
laplace_weights[laplace_output_channel_labels.index('bipolar EOG'), inlet_channel_labels.index('C3')] = 1
laplace_weights[laplace_output_channel_labels.index('bipolar EOG'), inlet_channel_labels.index('C4')] = -1

# C3 Laplace
laplace_weights[laplace_output_channel_labels.index('C3'), inlet_channel_labels.index('C3')] = 1
# laplace_weights[laplace_output_channel_labels.index('C3'), inlet_channel_labels.index('F3')] = -0.33
# laplace_weights[laplace_output_channel_labels.index('C3'), inlet_channel_labels.index('P3')] = -0.33
# laplace_weights[laplace_output_channel_labels.index('C3'), inlet_channel_labels.index('Cz')] = -0.33

# C4 Laplace
laplace_weights[laplace_output_channel_labels.index('C4'), inlet_channel_labels.index('C4')] = 1
# laplace_weights[laplace_output_channel_labels.index('C4'), inlet_channel_labels.index('F4')] = -0.33
# laplace_weights[laplace_output_channel_labels.index('C4'), inlet_channel_labels.index('P4')] = -0.33
# laplace_weights[laplace_output_channel_labels.index('C4'), inlet_channel_labels.index('Cz')] = -0.33

#print(inlet_channel_labels)
#print(laplace_weights)
#sys.exit()

node_01_highpass = IIRFilterNode.IIRFilterNode(inlet_channel_labels, sfreq=fs, order=1, ftype="butter", btype="highpass", fpass=0.1, fstop=0.05, gpass=3, gstop=50)
node_02_lowpass = IIRFilterNode.IIRFilterNode(inlet_channel_labels, sfreq=fs, order=2, ftype="butter", btype="lowpass", fpass=70, fstop=71, gpass=3, gstop=50)
node_03_notch = IIRFilterNode.IIRFilterNode(inlet_channel_labels, sfreq=fs, order=3, ftype="cheby1", btype="bandstop", fpass=[44, 56], fstop=[45, 55], gpass=0.1, gstop=50)
node_04_notch = IIRFilterNode.IIRFilterNode(inlet_channel_labels, sfreq=fs, order=3, ftype="cheby1", btype="bandstop", fpass=[44, 56], fstop=[45, 55], gpass=0.1, gstop=50)
node_05_laplace = SpatialFilterNode.SpatialFilterNode(inlet_channel_labels, weights=laplace_weights, out_channel_labels=laplace_output_channel_labels)
node_06_channel_select_eeg = ChannelSelectorNode.ChannelSelectorNode(laplace_output_channel_labels, ['C3', 'C4'])
node_07_bandpass = IIRFilterNode.IIRFilterNode(node_06_channel_select_eeg.out_channel_labels, sfreq=fs, order=3, ftype="butter", btype="bandpass", fpass=[1, 30], fstop=[0.5, 31], gpass=3.0, gstop=50)
node_08_buffer = BufferNode.BufferNode(node_06_channel_select_eeg.out_channel_labels, buffer_length=int(0.4 * fs), shift=int(0.05 * fs))
node_09_burg = BurgSpectrumNode.BurgSpectrumNode(node_06_channel_select_eeg.out_channel_labels, sfreq=fs, foi=11.0)
node_10_singlepole = SinglePoleFilterNode.SinglePoleFilterNode(node_06_channel_select_eeg.out_channel_labels, time_const=0.5, sfreq=20)

pipeline_nodes = [
    node_01_highpass,
    LSLStreamNode.LSLStreamNode(inlet_channel_labels, "debug1", nominal_srate=fs),
    node_02_lowpass,
    LSLStreamNode.LSLStreamNode(inlet_channel_labels, "debug2", nominal_srate=fs),
    node_03_notch,
    LSLStreamNode.LSLStreamNode(inlet_channel_labels, "debug3", nominal_srate=fs),
    node_04_notch,
    LSLStreamNode.LSLStreamNode(inlet_channel_labels, "debug4", nominal_srate=fs),
    node_05_laplace,
    LSLStreamNode.LSLStreamNode(laplace_output_channel_labels, "debug5", nominal_srate=fs),
    node_06_channel_select_eeg,
    node_07_bandpass,
    LSLStreamNode.LSLStreamNode(node_06_channel_select_eeg.out_channel_labels, "debug7", nominal_srate=fs),
    node_08_buffer,
    node_09_burg,
    LSLStreamNode.LSLStreamNode(node_06_channel_select_eeg.out_channel_labels, "debug9", nominal_srate=20),
    node_10_singlepole,
    [LSLStreamNode.LSLStreamNode(node_06_channel_select_eeg.out_channel_labels, "debug10", nominal_srate=20),
    LSLStreamNode.LSLStreamNode(node_06_channel_select_eeg.out_channel_labels, "debug11", nominal_srate=20)]
]


pipeline_nodes[0].out_channel_labels = inlet_channel_labels

pipeline = ProcessingPipeline.ProcessingPipeline(inlet_channel_labels, pipeline_nodes)



t_start = local_clock()

while local_clock() < (t_start+600):

    samples, timestamps = lsl_inlet.pull_chunk(timeout=0.005)

    if len(samples) == 0:
        continue

    #print("SAMPLES", samples)
    #print("TIMESTAMPS", timestamps)

    n_times = len(timestamps)
    n_channels = len(samples[0])

    # shape (n_times, n_channels)
    data = np.array(samples)

    # -> shape: n_channels, n_times
    data = np.moveaxis(data, 0, -1)

    # -> shape: n_trials, n_channels, ...features, n_times
    data = data.reshape([1, n_channels, n_times])

    t1 = local_clock()
    out_samples, out_timestamps = pipeline.process(data, timestamps)
    t2 = local_clock()

    if out_samples is not None:
        print(out_samples.shape, len(out_timestamps), round((t2-t1)*1000, 1), "ms")
    #else:
        #print("None")
    # out_samples = out_samples.reshape([n_channels, n_times])
    # out_samples = np.moveaxis(out_samples, 0, -1)

time.sleep(3)