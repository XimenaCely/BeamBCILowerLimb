import logging
import os
import time
from threading import Thread
from typing import List, Optional, cast, Callable
import random
from functools import reduce

import numpy as np
import pylsl
import pyxdf

from modules.module import Module
from modules.types import ModuleStatus

logger = logging.getLogger("pythonbci.modules.src.XDFPlayerModule")

# from PyQt5 import QtCore, QtGui, QtWidgets

from misc import LSLStreamInfoInterface

class XDFPlayerModule(Module):

    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME: str = "XDF Player Module"
    MODULE_DESCRIPTION: str = ""

    PARAMETER_DEFINITION = [
        {
            "name": "xdf_file",
            "displayname": "XDF File",
            "description": "",
            "type": str,
            "unit": "",
            "default": "",
        },
        {
            'name': 'button_load_file',
            'displayname': 'Load XDF file',
            'description': "",
            'type': Callable,
            'unit': "",
            'default': "load_file"
        }
    ]

    def __init__(self):
        super(XDFPlayerModule, self).__init__()

        self.set_state(Module.Status.STOPPED)

        self.player: Optional[XDFPlayer] = None

        self.file_loaded = False

        self.check_player_running_thread: Thread = Thread(target=self.check_player_running, daemon=True)
        self.check_player_running_thread.start()

    def check_player_running(self):
        time.sleep(3)

        while True:
            time.sleep(0.1)
            if self.get_state() is ModuleStatus.RUNNING and not self.player.running:
                self.stop()

    def load_file(self):
        if self.get_parameter_value("xdf_file") is None or cast(str, self.get_parameter_value("xdf_file")).strip() == "":
            logger.error("Please select a file before loading")
            self.file_loaded = False
            return

        streams = pyxdf.resolve_streams(self.get_parameter_value("xdf_file"))
        
        logger.info(f"Loaded {os.path.basename(cast(str, self.get_parameter_value('xdf_file')))} containing {len(streams)} streams:")
        logger.info(f"{[s["name"] for s in streams]}")

        self.file_loaded = True

    def start(self):

        self.set_state(Module.Status.STARTING)

        if self.get_parameter_value("xdf_file") is None or self.get_parameter_value("xdf_file") == "":
            logger.error("Please select and load an xdf-file first")
            self.set_state(Module.Status.STOPPED)
            return

        if self.get_parameter_value("xdf_file") is not None and not self.file_loaded:
            logger.info(
                "Automatically loading selected .xdf-file. Playing all contained streams"
            )
            self.load_file()

        if not self.file_loaded:
            logger.info("Automatic loading failed. Please select correct file")

        """
        channel_mask = [
            self.stream_select_box.itemChecked(i)
            for i in range(self.stream_select_box.count())
        ]
        """
        channel_mask = None

        self.player = XDFPlayer(
            self.get_parameter_value("xdf_file"),
            channel_mask
        )

        self.player.start()

        self.set_state(Module.Status.RUNNING)
        logger.success(
            f"XDFPlayer running with streams {[stream['info']['name'][0] for stream in self.player.streams]}"
        )

    def stop(self):

        self.set_state(Module.Status.STOPPING)

        self.player.stop()

        self.set_state(Module.Status.STOPPED)

    def restart(self):

        self.stop()
        time.sleep(0.5)
        self.start()


class XDFPlayer(object):

    def __init__(
        self,
        xdf_path,
        channel_mask=None,
        f_update: int = 100,
    ):

        self.xdf_path = xdf_path
        self.f_update: int = f_update
        self.start_clock = 0
        self.worker: Optional[Thread] = None
        self.running = False
        self.streamers: List[StreamPlayer] = []

        self.streams, self.header = pyxdf.load_xdf(
            self.xdf_path, dejitter_timestamps=True
        )

        # remove streams that are not selected by channel mask
        if channel_mask is not None:

            selected_streams = []

            for i in range(len(channel_mask)):

                if channel_mask[i]:
                    selected_streams.append(self.streams[i])

            self.streams = selected_streams

        # collect the first timestamp of all streams which contain at least 1 timestamp
        first_timestamps = []
        for s in self.streams:
            if len(s["time_stamps"]) > 0:
                first_timestamps.append(s["time_stamps"][0])

        # set the lowest timestamp as the offset for all timestamps
        offset = np.min(first_timestamps)

        # offset all timestamps
        for s in self.streams:
            s["time_stamps"] -= offset

    def start(self):

        self.streamers = []
        for s in self.streams:
            self.streamers.append(StreamPlayer(s))

        self.start_clock = pylsl.local_clock()

        self.worker = Thread(target=self.work_func, daemon=True)
        self.running = True
        self.worker.start()

    def stop(self):

        self.running = False
        time.sleep(2.0 / self.f_update)
        self.streamers = []

    def work_func(self):

        while self.running:

            clock_now = pylsl.local_clock() - self.start_clock

            for player in self.streamers:

                player.update(clock_now, self.start_clock)

            # logger.info(f"{[sp.finished for sp in self.streamers]}, {reduce(lambda a, b: a and b, [sp.finished for sp in self.streamers])}")

            if reduce(lambda a, b: a and b, [sp.finished for sp in self.streamers]):
                logger.success(f"XDF file replay completed.")
                self.stop()

            time.sleep(1.0 / self.f_update)


class StreamPlayer(object):

    def __init__(self, stream):

        self.time_stamps = stream["time_stamps"]
        self.time_series = stream["time_series"]
        self.n_samples: int = len(self.time_stamps)
        self.finished: bool = self.n_samples == 0

        stream_name = stream["info"]["name"][0]
        stream_type = stream["info"]["type"][0]
        channel_count = int(stream["info"]["channel_count"][0])
        nominal_srate = float(stream["info"]["nominal_srate"][0])
        source_id = stream["info"]["source_id"][0]
        channel_format = stream["info"]["channel_format"][0]
        chunk_size = int(nominal_srate / 50)

        if source_id is None or (isinstance(source_id, str) and len(source_id) == 0):
            source_id = 'uid'+str(random.randint(100000, 999999))

        info = pylsl.StreamInfo(
            stream_name,
            stream_type,
            channel_count,
            nominal_srate,
            channel_format,
            source_id,
        )

        # add manufacturer information
        try:
            manufacturer = stream["info"]["desc"][0]["manufacturer"][0]
            info.desc().append_child_value("manufacturer", manufacturer)
        except TypeError:
            logger.debug(
                f"Manufacturer info not available in description of stream '{stream_name}'"
            )
        except Exception:
            logger.debug(f"Manufacturer info not available in description of stream '{stream_name}'.")

        # add channels information
        try:
            chns = info.desc().append_child("channels")

            for chan in stream["info"]["desc"][0]["channels"][0]["channel"]:

                ch = chns.append_child("channel")

                for k in chan.keys():

                    try:
                        val = chan[k][0]
                        ch.append_child_value(k, val)

                    except Exception:
                        # will fail for non-single values, e.g. localtions of electrodes: list of x, y, z
                        pass

        except Exception:
            print("Could not add channels metadata to stream '" + stream_name + "'.")

        # add parameters
        parameters_dict = LSLStreamInfoInterface.get_parameters_from_xdf_stream(stream)
        desc = info.desc()
        parameters_xml = desc.append_child("parameters")

        for name, parameter in parameters_dict.items():
            parameters_xml.append_child_value(name, str(parameter))

        self.outlet: pylsl.StreamOutlet = pylsl.StreamOutlet(
            info, chunk_size=chunk_size, max_buffered=360
        )

        self.next_index = 0

        if self.n_samples == 0:
            self.finished = True

    def update(self, clock, clock_offset=0):

        while not self.finished and clock >= self.time_stamps[self.next_index]:

            self.outlet.push_sample(
                self.time_series[self.next_index],
                self.time_stamps[self.next_index] + clock_offset,
            )
            self.next_index += 1

            if self.next_index >= self.n_samples:
                self.finished = True
                del self.outlet
