import sys

if sys.path[0].endswith("tools"):
    sys.path.append(sys.path[0][:-6])

from pylsl import resolve_stream, StreamInfo, StreamInlet, resolve_byprop
from typeguard import typechecked


from misc.LSLStreamInfoInterface import get_channel_labels

@typechecked()
def info(stream_name: str) -> None:

    print("Looking for stream '"+stream_name+"'...")

    s = resolve_byprop("name", stream_name, minimum=1, timeout=3)

    if len(s) < 1:
        return

    inlet = StreamInlet(s[0])

    print("Fetching info...")
    info = inlet.info(5)

    print("\n", "STREAM INFO: {}, {} Ch, Type: {}, fs: {} Hz, Host: {}".format(info.name(), info.channel_count(), info.type(), info.nominal_srate(), info.hostname()))
    print("CHANNELS:")
    for l in get_channel_labels(info):
        print("    * "+l)



if __name__ == "__main__":

    stream_name = sys.argv[1]

    info(stream_name)