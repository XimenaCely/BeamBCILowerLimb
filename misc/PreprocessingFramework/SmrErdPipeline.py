from typing import List, Tuple, Optional
import numpy as np

from misc.PreprocessingFramework import IIRFilterNode, BufferNode, ReductionNode, SpatialFilterNode, BurgSpectrumNode, \
    ChannelSelectorNode, SinglePoleFilterNode, LSLStreamNode, ProcessingPipeline


def create_smr_erd_pipeline(
        input_channel_labels: List[str],
        fs: float,
        foi: float = 11.0,
        fs_out: float = 25.0,
        f_highpass: float = 0.1,
        f_lowpass: float = 70.0,
        f_notch: float = 50.0,
        spatial_filter_output_labels: List[str] = ['bipolar EOG', 'C3', 'C4','CZ'],
        spatial_filter_weight_matrix: Optional[np.ndarray] = None,
        f_eeg_bandpass: List[float] = [1, 30],
        f_eog_lowpass: float = 5.0,
        sliding_window_seconds: float = 0.4,
        single_pole_time_const: float = 0.5,
        enable_debugging_streams: bool = False,
        channels_eeg_processing=['C3', 'C4', 'CZ']
) -> Tuple:
    inlet_channel_labels = input_channel_labels
    channel_count: int = len(input_channel_labels)

    buffer_length_samples: int = int(fs * sliding_window_seconds)
    buffer_shift_samples: int = round(fs / fs_out)
    if (fs / fs_out) % 1 > 1e-2:
        fs_out_new: float = fs / buffer_shift_samples
        print((
                          "WARNING: Pipeline output sample rate of {:.5f}Hz is not compatible with input sampling rate of {:.5f}Hz. " +
                          "Using closest possible output frequency of {:.5f} instead.").format(fs_out, fs, fs_out_new))
        fs_out = fs_out_new

    # numer of output channels of the spatial filter
    spatial_filter_output_channel_count = len(spatial_filter_output_labels)

    # spatial filter weight matrix: weights[out_index, in_index]
    if spatial_filter_weight_matrix is None:
        raise Exception("spatial_filter_weight_matrix [out_channels x in_channels] needs to be set.")

    node_01_highpass = IIRFilterNode.IIRFilterNode(inlet_channel_labels, sfreq=fs, order=1, ftype="butter",
                                                   btype="highpass", fpass=f_highpass, fstop=f_highpass / 2, gpass=3,
                                                   gstop=50)

    node_02_lowpass = IIRFilterNode.IIRFilterNode(inlet_channel_labels, sfreq=fs, order=2, ftype="butter",
                                                  btype="lowpass", fpass=f_lowpass, fstop=f_lowpass + 1, gpass=3,
                                                  gstop=50)

    node_03_notch = IIRFilterNode.IIRFilterNode(inlet_channel_labels, sfreq=fs, order=3, ftype="cheby1",
                                                btype="bandstop", fpass=[f_notch - 6, f_notch + 6],
                                                fstop=[f_notch - 5, f_notch + 5], gpass=0.1, gstop=50)

    node_04_notch = IIRFilterNode.IIRFilterNode(inlet_channel_labels, sfreq=fs, order=3, ftype="cheby1",
                                                btype="bandstop", fpass=[f_notch - 6, f_notch + 6],
                                                fstop=[f_notch - 5, f_notch + 5], gpass=0.1, gstop=50)

    node_05_laplace = SpatialFilterNode.SpatialFilterNode(inlet_channel_labels, weights=spatial_filter_weight_matrix,
                                                          out_channel_labels=spatial_filter_output_labels)

    node_06_channel_select_eeg = ChannelSelectorNode.ChannelSelectorNode(spatial_filter_output_labels, channels_eeg_processing)

    node_07_bandpass = IIRFilterNode.IIRFilterNode(node_06_channel_select_eeg.out_channel_labels, sfreq=fs, order=3,
                                                   ftype="butter", btype="bandpass", fpass=f_eeg_bandpass,
                                                   fstop=[f_eeg_bandpass[0] / 2, f_eeg_bandpass[1] + 1],
                                                   gpass=3.0, gstop=50)

    node_08_buffer = BufferNode.BufferNode(node_06_channel_select_eeg.out_channel_labels,
                                           buffer_length=buffer_length_samples, shift=buffer_shift_samples)

    node_09_burg = BurgSpectrumNode.BurgSpectrumNode(node_06_channel_select_eeg.out_channel_labels, sfreq=fs, foi=foi)

    node_10_singlepole = SinglePoleFilterNode.SinglePoleFilterNode(node_06_channel_select_eeg.out_channel_labels,
                                                                   time_const=single_pole_time_const, sfreq=fs_out)

    node_11_channel_select_eog = ChannelSelectorNode.ChannelSelectorNode(spatial_filter_output_labels, ['bipolar EOG'])

    node_12_lowpass_eog = IIRFilterNode.IIRFilterNode(['bipolar EOG'], sfreq=fs, order=2, ftype="butter",
                                                      btype="lowpass",
                                                      fpass=f_eog_lowpass, fstop=f_eog_lowpass + 1, gpass=3, gstop=50)

    node_13_buffer_eog = BufferNode.BufferNode(['bipolar EOG'], buffer_length=buffer_length_samples,
                                               shift=buffer_shift_samples)

    node_14_reduction = ReductionNode.ReductionNode(['bipolar EOG'], functions=[
        dict(module='numpy', name='take', args=dict(indices=-1, axis=-1)),
        dict(module='numpy', name='expand_dims', args=dict(axis=-1))])

    common_pipeline_nodes = [
        node_01_highpass,
        LSLStreamNode.LSLStreamNode(inlet_channel_labels, "debug1", nominal_srate=fs,
                                    skip=not enable_debugging_streams),
        node_02_lowpass,
        LSLStreamNode.LSLStreamNode(inlet_channel_labels, "debug2", nominal_srate=fs,
                                    skip=not enable_debugging_streams),
        node_03_notch,
        LSLStreamNode.LSLStreamNode(inlet_channel_labels, "debug3", nominal_srate=fs,
                                    skip=not enable_debugging_streams),
        node_04_notch,
        LSLStreamNode.LSLStreamNode(inlet_channel_labels, "debug4", nominal_srate=fs,
                                    skip=not enable_debugging_streams),
        node_05_laplace,
        LSLStreamNode.LSLStreamNode(spatial_filter_output_labels, "debug5", nominal_srate=fs,
                                    skip=not enable_debugging_streams)
    ]

    eeg_pipeline_nodes = [
        node_06_channel_select_eeg,
        node_07_bandpass,
        LSLStreamNode.LSLStreamNode(node_06_channel_select_eeg.out_channel_labels, "debug7", nominal_srate=fs,
                                    skip=not enable_debugging_streams),
        node_08_buffer,
        LSLStreamNode.LSLStreamNode(node_06_channel_select_eeg.out_channel_labels, "debug14", nominal_srate=fs_out,
                                    skip=not enable_debugging_streams),
        node_09_burg,
        LSLStreamNode.LSLStreamNode(node_06_channel_select_eeg.out_channel_labels, "debug9", nominal_srate=fs_out,
                                    skip=not enable_debugging_streams),
        node_10_singlepole,
        LSLStreamNode.LSLStreamNode(node_06_channel_select_eeg.out_channel_labels, "debug10", nominal_srate=fs_out,
                                    skip=not enable_debugging_streams)
    ]

    eog_pipeline_nodes = [
        node_11_channel_select_eog,
        LSLStreamNode.LSLStreamNode(['bipolar EOG'], "debug11", nominal_srate=fs, skip=not enable_debugging_streams),
        node_12_lowpass_eog,
        LSLStreamNode.LSLStreamNode(['bipolar EOG'], "debug12", nominal_srate=fs, skip=not enable_debugging_streams),
        node_13_buffer_eog,
        LSLStreamNode.LSLStreamNode(['bipolar EOG'], "debug15", nominal_srate=fs_out,
                                    skip=not enable_debugging_streams),
        node_14_reduction,
        LSLStreamNode.LSLStreamNode(['bipolar EOG'], "debug13", nominal_srate=fs_out, skip=not enable_debugging_streams)
    ]

    common_pipeline = ProcessingPipeline.ProcessingPipeline(inlet_channel_labels, common_pipeline_nodes)
    eeg_pipeline = ProcessingPipeline.ProcessingPipeline(spatial_filter_output_labels, eeg_pipeline_nodes)
    eog_pipeline = ProcessingPipeline.ProcessingPipeline(spatial_filter_output_labels, eog_pipeline_nodes)

    return common_pipeline, eeg_pipeline, eog_pipeline, fs_out