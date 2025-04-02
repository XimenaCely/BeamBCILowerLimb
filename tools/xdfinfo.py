import pyxdf
import sys


def xdfinfo(path):

    data, header = pyxdf.load_xdf(path, dejitter_timestamps=True, verbose=True)

    print("\n\n\nFile:\t", path)
    print("="*(len(path)+10))

    print("\nStreams:\n")

    print("Index    Name                    Channels   Nominal s. rate   Eff. s. rate    Type    Format")

    for i,c in enumerate(data):

        info = c["info"]

        print("{:02d}:\t {:25.25s} {:6d} {:17.1f} {:14.2f} {:>7s} {:>9s}".format(
            i, 
            info["name"][0], 
            int(info["channel_count"][0]), 
            float(info["nominal_srate"][0]), 
            float(info["effective_srate"]),
            info["type"][0],
            info["channel_format"][0]
        ))

    print()


    for i,c in enumerate(data):

        info = c["info"]

        print("\n\nStream:", info["name"][0])
        print("------------------------------")

        print("Channels:")
        channels = info["desc"][0]["channels"][0]["channel"]
        for c in channels:
            print("\t -", c["label"][0])

        print("Parameters:")

        if "parameters" in info["desc"][0].keys():
            parameter_keys = info["desc"][0]["parameters"][0]["keys"]
            parameter_values = info["desc"][0]["parameters"][0]["values"]
            for k, v in zip(parameter_keys, parameter_values):
                print("\t -", k, "=", v)
        else:
            print("\t none")


    print("\n\n") 


if __name__ == "__main__":

    path = sys.argv[1]
    
    xdfinfo(path)