from typing import Dict, Union, List
from typeguard import typechecked

@typechecked()
def find_stream(xdf_data, stream_names: List[str]) -> Dict[str, dict]:
    """Return dictionary of format stream_name: (index, stream)
        if stream_name is found in xdf data."""
    try:
        streams = {stream['info']['name'][0]: stream
                   for (ix, stream) in enumerate(xdf_data)
                   if stream['info']['name'][0] in stream_names}

        if len(stream_names) > len(streams):
            raise KeyError("""Error in {}. Could not find {} in streams."""
                           .format(find_stream.__name__, *(set(stream_names) - set(streams.keys()))))

        return streams

    except TypeError:
        raise TypeError("""Error in {}. 
            Could not find streams in xdf_data[ix]['info']['name']"""
                        .format(find_stream.__name__))


@typechecked()
def find_channel_index(stream, channel_names: List[str]) -> List[int]:
    """Find channels by name and return indices for accessing slices of
        time series data."""
    try:
        channel_list = stream['info']['desc'][0]['channels'][0]['channel']
        channels = [channel_list[c]['label'][0] for c in range(len(channel_list))]

        # throws a ValueError if requested channel name is not in stream channels
        indices = list(map(channels.index, channel_names))
        return indices

    except TypeError:
        raise TypeError("""Error in {}. 
            Could not find channels in stream['info']['desc'][0]['channels'][0]['channel']"""
                        .format(find_channel_index.__name__))


@typechecked()
def get_channel_labels_from_xdf_stream(xdf_stream) -> List[str]:

    labels: List[str] = []

    try:
        for chan in xdf_stream['info']['desc'][0]['channels'][0]['channel']:

            for k in chan.keys():

                try:
                    if str(k).strip().lower() == 'label':
                        val = chan[k][0]
                        labels.append(str(val))

                except Exception:
                    pass
    except Exception:
        pass

    return labels


@typechecked()
def get_parameters_from_xdf_stream(xdf_stream) -> Dict[str, Union[str, int, float, bool]]:
    """
        Extract parameters as a dict from metadata of an XDF data object.

        Parameters:
            xdf_stream: Stream object loaded by pyxdf

        Returns:
            Dict of <parameter name> => <parameter value>
    """

    parameters = {}

    if 'parameters' not in xdf_stream['info']['desc'][0].keys():
        return {}

    if xdf_stream['info']['desc'][0]['parameters'][0] is None:
        return {}

    keys = list(xdf_stream['info']['desc'][0]['parameters'][0].keys())

    for k in keys:
        parameters[k] = xdf_stream['info']['desc'][0]['parameters'][0][k][0]

    return parameters
