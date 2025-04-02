from ..module import Module
from threading import Thread
import time
import globals
from misc import enums
import random

from pylsl import resolve_byprop, StreamInlet, StreamOutlet, StreamInfo, IRREGULAR_RATE, cf_int32
from misc.LSLStreamInfoInterface import add_channel_names, add_mappings, add_parameters
from misc.timing import clock


# is meant to provide the general structures of all task modules
class TaskModule(Module):


    # properties of lsl outlet. to be overwritten by subclasses
    TYPE_OUTPUT_STREAM: str= 'mixed'
    NUM_OUTPUT_CHANNELS: int = 0
    OUTPUT_CHANNEL_FORMAT = cf_int32
    OUTPUT_CHANNEL_NAMES: list = []


    def __init__(self):
        super(TaskModule, self).__init__()
    
        self.set_state(Module.Status.STOPPED)

        self.taskthread = None
        self.datathread = None
        self.running = False

        self.lsl_inlet = None
        self.lsl_outlet = None
        self.lsl_streaminfo = None


    def start(self):

        # do not start up the LSL LabRecorder App is not available
        if not globals.LSLAvailable:
            return

        # do not start up the module if it was already started
        if self.state != Module.Status.STOPPED:
            return

        # set status
        self.set_state(Module.Status.STARTING)
        
        # fetch necessary lsl stream
        streams = resolve_byprop("name", globals.STREAM_NAME_CLASSIFIED_SIGNAL, minimum=1, timeout=30)

        if len(streams) < 1:
            self.set_state(Module.Status.STOPPED)
            print("Could not start", self.MODULE_NAME, "because of missing stream:", globals.STREAM_NAME_CLASSIFIED_SIGNAL)
            return

        # init LSL inlet
        self.lsl_inlet = StreamInlet(streams[0], max_buflen=360, max_chunklen=1, recover=True)

        # create stream info for lsl outlet
        self.lsl_stream_info = StreamInfo(
            globals.STREAM_NAME_TASK_EVENTS,
            self.TYPE_OUTPUT_STREAM,
            self.NUM_OUTPUT_CHANNELS,
            self.lsl_inlet.info().nominal_srate(),
            self.OUTPUT_CHANNEL_FORMAT,
            'uid' + str(random.randint(100000, 999999))
        )

        # add channel names and mappings to stream info
        add_channel_names(self.lsl_stream_info, self.OUTPUT_CHANNEL_NAMES)
        add_mappings(self.lsl_stream_info, ['cues', 'exo_states'], [enums.Cue, enums.WalkExo])
        add_parameters(self.lsl_stream_info, self.parameters)

        # init LSL outlet
        self.lsl_outlet = StreamOutlet(self.lsl_stream_info, chunk_size=1) #TODO check if it is necessary

        # set running true to signal threads to continue running
        self.running = True

        # create thread to handle lsl input
        self.datathread = Thread(target=self.handle_input, daemon=True)
        self.datathread.start()

        # create thread to run the task
        self.taskthread = Thread(target=self.run, daemon=True)
        self.taskthread.start()

        # set status
        self.set_state(Module.Status.RUNNING)



    def onStop(self):
        pass

    def stop(self):

        # do not try to stop if not even running
        if self.get_state() != Module.Status.RUNNING:
            return


        self.set_state(Module.Status.STOPPING)


        # call onStop Method
        self.onStop()

        
        # set the running flag to false which signals threads to stop
        self.running = False
        
        # stop taskthread
        print(self.MODULE_NAME + ': Waiting for task thread to terminate... ')
        while self.taskthread is not None and self.taskthread.is_alive():
            time.sleep(0.1)
        print("done.")


        # stop data thread
        print(self.MODULE_NAME + ': Waiting for data handling thread to terminate... ')
        while self.datathread is not None and self.datathread.is_alive():
            time.sleep(0.1)
        print("done.")


        # clear reference to threads
        self.taskthread = None
        self.datathread = None

        # close lsl connections
        if self.lsl_inlet is not None:
            self.lsl_inlet.close_stream()
        self.lsl_inlet = None
        self.lsl_outlet = None

        # set status
        self.set_state(Module.Status.STOPPED)


    # executed by a separate thread, continously pulling samples from the lsl inlet
    def handle_input(self):
        
        while self.running:

            in_sample, in_timestamp = self.lsl_inlet.pull_sample(timeout=1)

            if in_sample is not None:

                out_sample, out_timestamp = self.process_data(in_sample, in_timestamp)

                if out_sample is not None:

                    if globals.OUTPUT_TRUE_TIMESTAMPS:
                        self.lsl_outlet.push_sample(out_sample)
                    else:
                        self.lsl_outlet.push_sample(out_sample, out_timestamp)


    # method for event-generating task to execute
    def run(self):

        # first run the task
        self.run_task()

        # when finished, stop the module
        stopThread = Thread(target=self.stop, daemon=True)
        stopThread.start()
        


    # this method should be overwritten by subclasses to implement specific tasks
    def run_task(self):
        pass



    # this method should be overwritten by subclass to implement the specific data handling
    # it is called every time a lsl sample is received and is expected to return an output sample
    def process_data(self, sample, timestamp):
        return (None, None)

    
    def wait(self, seconds: float):

        end = clock() + seconds

        toWait = end - clock()

        while toWait > 0.0001:
            
            if not self.running:
                return

            if toWait < 0.2:
                time.sleep(toWait)
                return
            
            time.sleep(0.1)
            toWait = end - clock()

            

