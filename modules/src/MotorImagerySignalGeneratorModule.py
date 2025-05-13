from threading import Thread
import time
import math
import random
from typing import Callable, List, Optional

from modules.module import Module
from modules.types import ModuleStatus 

import globals
from misc import LSLStreamInfoInterface
from misc.timing import clock
from pylsl import StreamInfo, StreamOutlet

from PyQt5.QtWidgets import QPushButton
from misc.gui import BoldLabel

import logging
logger = logging.getLogger("modules.src.MotorImagerySignalGeneratorModule")

class RingBuffer(object):

    def __init__(self, datatype=float, size: int = 1000, default_value=1.0):

        self.data_type = datatype
        self.size = size
        self.default_value = default_value
        self.buffer: List[datatype] = [default_value] * size

        self.pointer: int = 0

    def movePointer(self, steps:int = 1):

        self.pointer = (self.pointer + steps) % self.size

    def read(self):

        val = self.buffer[self.pointer]
        self.buffer[self.pointer] = self.default_value
        self.movePointer(1)
        return val

    def insert_ahead(self, values: list):

        for i, v in enumerate(values):

            insert_index = (self.pointer + 1 + i) % self.size
            self.buffer[insert_index] = v


class MotorImagerySignalGeneratorModule(Module):

    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME: str = "Motor Imagery Signal Generator"
    MODULE_DESCRIPTION: str = ""

    PARAMETER_DEFINITION = [
        {
            'name': 'setup',
            'displayname': 'Electrode setup',
            'description': '',
            'type': list,
            'unit': ['UpperLimb','LowerLimb','LowerLimb+EOG','bilateral', 'bilateral+EOG', 'unilateralC3', 'unilateralC3+EOG', 'unilateralC4', 'unilateralC4+EOG'],
            'default': 'LowerLimb'
        },
        {
            'name': 'fs',
            'displayname': 'Sample rate',
            'description': '',
            'type': int,
            'unit': 'Hz',
            'default': 512
        },
        {
            'name': 'chunksize',
            'displayname': 'Chunk size',
            'description': '',
            'type': int,
            'unit': 'samples',
            'default': 10
        },
        {
            'name': 'f_smr',
            'displayname': 'SMR frequency',
            'description': '',
            'type': float,
            'unit': 'Hz',
            'default': 11.0
        },
        {
            'name': 'amplitude_smr',
            'displayname': 'SMR amplitude',
            'description': '',
            'type': float,
            'unit': 'uV',
            'default': 2.0
        },
        {
            'name': 'amplitude_noise',
            'displayname': 'Noise amplitude',
            'description': '',
            'type': float,
            'unit': 'uV',
            'default': 1.0
        },
        {
            'name': 'erd_length',
            'displayname': 'ERD length',
            'description': '',
            'type': float,
            'unit': 's',
            'default': 4.0
        },
        {
            'name': 'erd_shape',
            'displayname': 'ERD temporal shape',
            'description': '',
            'type': list,
            'unit': ['squared sine halfwave', 'rectangular'],
            'default': 'squared sine halfwave'
        },
        {
            'name': 'hov_amplitude',
            'displayname': 'HOV amplitude',
            'description': '',
            'type': float,
            'unit': 'uV',
            'default': 750.0
        },
        {
            'name': 'button_erd_c3',
            'displayname': 'ERD C3',
            'description': "",
            'type': Callable,
            'unit': "",
            'default': "button_action_erd_c3"
        },
        {
            'name': 'button_erd_cz',
            'displayname': 'ERD Cz',
            'description': "",
            'type': Callable,
            'unit': "",
            'default': "button_action_erd_cz"
        },
        {
            'name': 'button_erd_c4',
            'displayname': 'ERD C4',
            'description': "",
            'type': Callable,
            'unit': "",
            'default': "button_action_erd_c4"
        },
        {
            'name': 'button_hov_left',
            'displayname': 'HOV left',
            'description': "",
            'type': Callable,
            'unit': "",
            'default': "button_action_hov_left"
        },
        {
            'name': 'button_hov_right',
            'displayname': 'HOV right',
            'description': "",
            'type': Callable,
            'unit': "",
            'default': "button_action_hov_right"
        }
    ]    

    def __init__(self):
        super(MotorImagerySignalGeneratorModule, self).__init__()

        self.set_state(Module.Status.STOPPED)

        self.lsl_streaminfo = None
        self.lsl_outlet = None
        self.num_channels = None
        self.channel_names = None

        self.generator_thread = None

        self.running = False

        self.ringbuffer_c3: Optional[RingBuffer] = None
        self.ringbuffer_c4: Optional[RingBuffer] = None
        self.ringbuffer_cz: Optional[RingBuffer] = None

    def button_action_erd_c3(self):
        if self.get_state() is ModuleStatus.RUNNING:
            self.insertERD(self.ringbuffer_c3, self.get_parameter_value("erd_length"), 0.7)
            self.insertERD(self.ringbuffer_c4, self.get_parameter_value("erd_length"), 0.3)

    def button_action_erd_c4(self):
        if self.get_state() is ModuleStatus.RUNNING:
            self.insertERD(self.ringbuffer_c4, self.get_parameter_value("erd_length"), 0.7)
            self.insertERD(self.ringbuffer_c3, self.get_parameter_value("erd_length"), 0.3)
    
    def button_action_erd_cz(self):
        if self.get_state() is ModuleStatus.RUNNING:
            self.insertERD(self.ringbuffer_cz, self.get_parameter_value("erd_length"), 0.99)

    def button_action_hov_left(self):
        if self.get_state() is ModuleStatus.RUNNING:
            self.insertHOV(self.ringbuffer_eog_left, amount=self.get_parameter_value("hov_amplitude"))

    def button_action_hov_right(self):
        if self.get_state() is ModuleStatus.RUNNING:
            self.insertHOV(self.ringbuffer_eog_right, amount=self.get_parameter_value("hov_amplitude"))
    
    def insertERD(self, buffer: RingBuffer, length: float = 1.0, amount: float = 1.0):

        samples = [buffer.default_value] * int(length * self.get_parameter_value("fs"))

        if self.get_parameter_value("erd_shape") == "rectangular":
        
            for i in range(len(samples)):
                samples[i] -= samples[i]*amount*1

        else:
            T_sine = 2 * length
            f_sine = 1 / T_sine

            for i in range(len(samples)):

                t = T_sine/2 + i * T_sine/2/len(samples)
                samples[i] -= samples[i]*amount*(math.sin(2 * math.pi * f_sine * t)**2)

        buffer.insert_ahead(samples)

    def insertHOV(self, buffer: RingBuffer, length: float = 0.8, amount: float = 700.0):

        samples = [buffer.default_value] * int(length * self.get_parameter_value("fs"))

        T_sine = 2 * length
        f_sine = 1 / T_sine

        for i in range(len(samples)):

            t = T_sine/2 + i * T_sine/2/len(samples)
            samples[i] = samples[i] + amount*(math.sin(2 * math.pi * f_sine * t)**4)

        buffer.insert_ahead(samples)

    def sine_value(self, t: float, f: float, amplitude: float):

        return math.sin(t * 2 * math.pi * f ) * amplitude

    def generateSample(self, t: float):

        sample = []

        for i in range(self.num_channels):

            sample.append(random.random() * self.get_parameter_value('amplitude_noise'))

            # C3 EEG channel
            if "C3" in self.channel_names and i == self.channel_names.index("C3"):
                sample[-1] += self.sine_value(t, self.get_parameter_value('f_smr'), self.ringbuffer_c3.read())

            # C4 EEG channel
            elif "C4" in self.channel_names and i == self.channel_names.index("C4"):
                sample[-1] += self.sine_value(t, self.get_parameter_value('f_smr'), self.ringbuffer_c4.read())

            # Cz EEG channel
            elif "Cz" in self.channel_names and i == self.channel_names.index("Cz"):
                sample[-1] += self.sine_value(t, self.get_parameter_value('f_smr'), self.ringbuffer_cz.read())
            
            # if an EOG-setup is used, insert the EOG signal on its channels
            if self.get_parameter_value("setup").endswith("+EOG"):
                
                # left EOG channel
                if "F7" in self.channel_names and i == self.channel_names.index("F7"):
                    sample[-1] += self.ringbuffer_eog_left.read()
                    
                # right EOG channel
                elif "F8" in self.channel_names and i == self.channel_names.index("F8"):
                    sample[-1] += self.ringbuffer_eog_right.read()
                    
            # if there are no seperate electrodes for EOG, add a portion of the signal to F3 and F4
            else:
                if i == self.channel_names.index("F7"):
                    sample[-1] += 0.5 * self.ringbuffer_eog_left.read()

                elif i == self.channel_names.index("F8"):
                    sample[-1] += 0.5 * self.ringbuffer_eog_right.read()
            
        return sample

    def sendChunk(self, t_last_sample=clock()):

        if self.lsl_outlet is None:
            return

        chunksize = self.get_parameter_value("chunksize")
        delta_T = 1/self.get_parameter_value('fs')
        
        chunk = []
        for i in range(chunksize,0,-1):
            t_sample = t_last_sample - ((i-1) * delta_T)
            chunk.append(self.generateSample(t_sample))



        self.lsl_outlet.push_chunk(chunk, t_last_sample)

    def signal_generator(self):

        start = clock()

        fs: int = self.get_parameter_value('fs')
        delta_T = 1/fs
        chunksize: int = self.get_parameter_value("chunksize")

        samples_sent: int = 0

        sleeptime: float = max(0.001, 1/fs*chunksize/10)

        while self.running:

            time.sleep(sleeptime)

            now = clock()

            time_since_start = now-start

            samples_target_now = math.floor(time_since_start * fs)

            samples_missing = samples_target_now - samples_sent

            if samples_missing >= chunksize:

                time_of_chunks_last_sample = clock() - ( (samples_missing-chunksize) * delta_T )
                self.sendChunk(time_of_chunks_last_sample)
                samples_sent += chunksize

    def start(self):

        if self.get_state() is not Module.Status.STOPPED:
            return

        self.set_state(Module.Status.STARTING)

        # set channel count and channel labels based on which electrode setup was selected
        #channels sponges-based EEG: FP1, FP2, FZ, FC5, FC1, FC2, FC6, T7, C3, CZ, C4, T8, CP5, CP1, CP2, CP6, PZ
        if self.get_parameter_value('setup') == 'LowerLimb':
            self.num_channels = 13
            self.channel_names = ["F3", "F4", "FZ", "C3", "CZ", "C4", "P3", "PZ", "P4", 'F7','F8', 'T7', 'T8']
        
        if self.get_parameter_value('setup') == 'LowerLimb+EOG':

            self.num_channels = 18 
            self.channel_names = ["FP1", "FP2", "F3", "F4", "FC1", "FCz", "FC2", "C3", "C1", "Cz", "C2", "C4", "CP1", "CPz", "CP2", "Pz", 'F7','F8']
                
        if self.get_parameter_value('setup') == 'UpperLimb':

            self.num_channels = 16 
            self.channel_names = ["FP1", "FP2", "FC3", "FCz", "FC4", "C5", "C3", "C1", "Cz", "C2", "C4", "C6", "CP3", "CPz", "CP4", "Pz"]
        
        if self.get_parameter_value('setup') == 'bilateral':

            self.num_channels = 9
            self.channel_names = ["P3", "F3", "C3", "Cz", "T7", "P4", "F4", "C4", "T8"]

        if self.get_parameter_value('setup') == 'bilateral+EOG':

            self.num_channels = 11
            self.channel_names = ["P3", "F3", "C3", "Cz", "T7", "P4", "F4", "C4", "T8", "F7", "F8"]

        elif self.get_parameter_value('setup') == 'unilateralC3':

            self.num_channels = 5
            self.channel_names = ["P3", "F3", "C3", "Cz", "T7"]
        
        elif self.get_parameter_value('setup') == 'unilateralC3+EOG':

            self.num_channels = 7
            self.channel_names = ["P3", "F3", "C3", "Cz", "T7", "F7", "F8"]

        elif self.get_parameter_value('setup') == 'unilateralC4':

            self.num_channels = 5
            self.channel_names = ["Cz", "P4", "F4", "C4", "T8"]
        
        elif self.get_parameter_value('setup') == 'unilateralC4+EOG':

            self.num_channels = 7
            self.channel_names = ["Cz", "P4", "F4", "C4", "T8", "F7", "F8"]

        # generate stream info
        self.lsl_streaminfo = StreamInfo(
            globals.STREAM_NAME_RAW_SIGNAL,
            'EEG',
            self.num_channels,
            float(self.get_parameter_value("fs")),
            'double64',
            'uid'+str(random.randint(100000, 999999))
        )

        # add channel names to stream info
        LSLStreamInfoInterface.add_channel_names(self.lsl_streaminfo, self.channel_names)

        # add parameters to stream info
        LSLStreamInfoInterface.add_parameters(self.lsl_streaminfo, self.parameters)

        # init LSL outlet
        self.lsl_outlet = StreamOutlet(self.lsl_streaminfo, chunk_size=self.get_parameter_value('chunksize'))

        # init ringbuffers
        self.ringbuffer_c3 = RingBuffer(float, size=10*self.get_parameter_value("fs"), default_value=self.get_parameter_value('amplitude_smr'))
        self.ringbuffer_c4 = RingBuffer(float, size=10*self.get_parameter_value("fs"), default_value=self.get_parameter_value('amplitude_smr'))
        self.ringbuffer_cz = RingBuffer(float, size=10*self.get_parameter_value("fs"), default_value=self.get_parameter_value('amplitude_smr'))

        # init ringbuffers for EOG signal with random offset
        self.ringbuffer_eog_left = RingBuffer(float, size=10*self.get_parameter_value("fs"), default_value=(random.random()-0.5)*10000)
        self.ringbuffer_eog_right = RingBuffer(float, size=10*self.get_parameter_value("fs"), default_value=(random.random()-0.5)*10000)

        # start generator thread
        self.running = True
        self.generator_thread = Thread(daemon=True, target=self.signal_generator)
        self.generator_thread.start()

        self.set_state(Module.Status.RUNNING)

    def stop(self):

        if self.get_state() is not Module.Status.RUNNING:
            return

        self.set_state(Module.Status.STOPPING)

        # wait for signal generator thread to stop
        self.running = False
        while self.generator_thread.is_alive():
            time.sleep(0.1)

        time.sleep(0.1)
        self.generator_thread = None
        self.lsl_outlet = None

        self.set_state(Module.Status.STOPPED)

    def restart(self):
        self.stop()
        time.sleep(0.2)
        self.start()
"""
from threading import Thread
import time
import math
import random
from typing import Callable, List, Optional

from modules.module import Module
from modules.types import ModuleStatus 

import globals
from misc import LSLStreamInfoInterface
from misc.timing import clock
from pylsl import StreamInfo, StreamOutlet

from PyQt5.QtWidgets import QPushButton
from misc.gui import BoldLabel

import logging
logger = logging.getLogger("modules.src.MotorImagerySignalGeneratorModule")

class RingBuffer(object):

    def __init__(self, datatype=float, size: int = 1000, default_value=1.0):

        self.data_type = datatype
        self.size = size
        self.default_value = default_value
        self.buffer: List[datatype] = [default_value] * size

        self.pointer: int = 0

    def movePointer(self, steps:int = 1):

        self.pointer = (self.pointer + steps) % self.size

    def read(self):

        val = self.buffer[self.pointer]
        self.buffer[self.pointer] = self.default_value
        self.movePointer(1)
        return val

    def insert_ahead(self, values: list):

        for i, v in enumerate(values):

            insert_index = (self.pointer + 1 + i) % self.size
            self.buffer[insert_index] = v


class MotorImagerySignalGeneratorModule(Module):

    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME: str = "Motor Imagery Signal Generator"
    MODULE_DESCRIPTION: str = ""

    PARAMETER_DEFINITION = [
        {
            'name': 'setup',
            'displayname': 'Electrode setup',
            'description': '',
            'type': list,
            'unit': ['bilateral', 'bilateral+EOG', 'unilateralC3', 'unilateralC3+EOG', 'unilateralC4', 'unilateralC4+EOG'],
            'default': 'bilateral+EOG'
        },
        {
            'name': 'fs',
            'displayname': 'Sample rate',
            'description': '',
            'type': int,
            'unit': 'Hz',
            'default': 500
        },
        {
            'name': 'chunksize',
            'displayname': 'Chunk size',
            'description': '',
            'type': int,
            'unit': 'samples',
            'default': 10
        },
        {
            'name': 'f_smr',
            'displayname': 'SMR frequency',
            'description': '',
            'type': float,
            'unit': 'Hz',
            'default': 11.0
        },
        {
            'name': 'amplitude_smr',
            'displayname': 'SMR amplitude',
            'description': '',
            'type': float,
            'unit': 'uV',
            'default': 2.0
        },
        {
            'name': 'amplitude_noise',
            'displayname': 'Noise amplitude',
            'description': '',
            'type': float,
            'unit': 'uV',
            'default': 1.0
        },
        {
            'name': 'erd_length',
            'displayname': 'ERD length',
            'description': '',
            'type': float,
            'unit': 's',
            'default': 4.0
        },
        {
            'name': 'erd_shape',
            'displayname': 'ERD temporal shape',
            'description': '',
            'type': list,
            'unit': ['squared sine halfwave', 'rectangular'],
            'default': 'squared sine halfwave'
        },
        {
            'name': 'hov_amplitude',
            'displayname': 'HOV amplitude',
            'description': '',
            'type': float,
            'unit': 'uV',
            'default': 750.0
        },
        {
            'name': 'button_erd_c3',
            'displayname': 'ERD C3',
            'description': "",
            'type': Callable,
            'unit': "",
            'default': "button_action_erd_c3"
        },
        {
            'name': 'button_erd_c4',
            'displayname': 'ERD C4',
            'description': "",
            'type': Callable,
            'unit': "",
            'default': "button_action_erd_c4"
        },
        {
            'name': 'button_hov_left',
            'displayname': 'HOV left',
            'description': "",
            'type': Callable,
            'unit': "",
            'default': "button_action_hov_left"
        },
        {
            'name': 'button_hov_right',
            'displayname': 'HOV right',
            'description': "",
            'type': Callable,
            'unit': "",
            'default': "button_action_hov_right"
        }
    ]    

    def __init__(self):
        super(MotorImagerySignalGeneratorModule, self).__init__()

        self.set_state(Module.Status.STOPPED)

        self.lsl_streaminfo = None
        self.lsl_outlet = None
        self.num_channels = None
        self.channel_names = None

        self.generator_thread = None

        self.running = False

        self.ringbuffer_c3: Optional[RingBuffer] = None
        self.ringbuffer_c4: Optional[RingBuffer] = None

    def button_action_erd_c3(self):
        if self.get_state() is ModuleStatus.RUNNING:
            self.insertERD(self.ringbuffer_c3, self.get_parameter_value("erd_length"), 0.7)
            self.insertERD(self.ringbuffer_c4, self.get_parameter_value("erd_length"), 0.3)

    def button_action_erd_c4(self):
        if self.get_state() is ModuleStatus.RUNNING:
            self.insertERD(self.ringbuffer_c4, self.get_parameter_value("erd_length"), 0.7)
            self.insertERD(self.ringbuffer_c3, self.get_parameter_value("erd_length"), 0.3)

    def button_action_hov_left(self):
        if self.get_state() is ModuleStatus.RUNNING:
            self.insertHOV(self.ringbuffer_eog_left, amount=self.get_parameter_value("hov_amplitude"))

    def button_action_hov_right(self):
        if self.get_state() is ModuleStatus.RUNNING:
            self.insertHOV(self.ringbuffer_eog_right, amount=self.get_parameter_value("hov_amplitude"))
    
    def insertERD(self, buffer: RingBuffer, length: float = 1.0, amount: float = 1.0):

        samples = [buffer.default_value] * int(length * self.get_parameter_value("fs"))

        if self.get_parameter_value("erd_shape") == "rectangular":
        
            for i in range(len(samples)):
                samples[i] -= samples[i]*amount*1

        else:
            T_sine = 2 * length
            f_sine = 1 / T_sine

            for i in range(len(samples)):

                t = T_sine/2 + i * T_sine/2/len(samples)
                samples[i] -= samples[i]*amount*(math.sin(2 * math.pi * f_sine * t)**2)

        buffer.insert_ahead(samples)

    def insertHOV(self, buffer: RingBuffer, length: float = 0.8, amount: float = 700.0):

        samples = [buffer.default_value] * int(length * self.get_parameter_value("fs"))

        T_sine = 2 * length
        f_sine = 1 / T_sine

        for i in range(len(samples)):

            t = T_sine/2 + i * T_sine/2/len(samples)
            samples[i] = samples[i] + amount*(math.sin(2 * math.pi * f_sine * t)**4)

        buffer.insert_ahead(samples)

    def sine_value(self, t: float, f: float, amplitude: float):

        return math.sin(t * 2 * math.pi * f ) * amplitude

    def generateSample(self, t: float):

        sample = []

        for i in range(self.num_channels):

            sample.append(random.random() * self.get_parameter_value('amplitude_noise'))

            # C3 EEG channel
            if "C3" in self.channel_names and i == self.channel_names.index("C3"):
                sample[-1] += self.sine_value(t, self.get_parameter_value('f_smr'), self.ringbuffer_c3.read())

            # C4 EEG channel
            elif "C4" in self.channel_names and i == self.channel_names.index("C4"):
                sample[-1] += self.sine_value(t, self.get_parameter_value('f_smr'), self.ringbuffer_c4.read())
            
            # if an EOG-setup is used, insert the EOG signal on its channels
            if self.get_parameter_value("setup").endswith("+EOG"):
                
                # left EOG channel
                if "F7" in self.channel_names and i == self.channel_names.index("F7"):
                    sample[-1] += self.ringbuffer_eog_left.read()

                # right EOG channel
                elif "F8" in self.channel_names and i == self.channel_names.index("F8"):
                    sample[-1] += self.ringbuffer_eog_right.read()

            # if there are no seperate electrodes for EOG, add a portion of the signal to F3 and F4
            else:
                if i == self.channel_names.index("F3"):
                    sample[-1] += 0.5 * self.ringbuffer_eog_left.read()
                elif i == self.channel_names.index("F4"):
                    sample[-1] += 0.5 * self.ringbuffer_eog_right.read()


        return sample

    def sendChunk(self, t_last_sample=clock()):

        if self.lsl_outlet is None:
            return

        chunksize = self.get_parameter_value("chunksize")
        delta_T = 1/self.get_parameter_value('fs')
        
        chunk = []
        for i in range(chunksize,0,-1):
            t_sample = t_last_sample - ((i-1) * delta_T)
            chunk.append(self.generateSample(t_sample))



        self.lsl_outlet.push_chunk(chunk, t_last_sample)

    def signal_generator(self):

        start = clock()

        fs: int = self.get_parameter_value('fs')
        delta_T = 1/fs
        chunksize: int = self.get_parameter_value("chunksize")

        samples_sent: int = 0

        sleeptime: float = max(0.001, 1/fs*chunksize/10)

        while self.running:

            time.sleep(sleeptime)

            now = clock()

            time_since_start = now-start

            samples_target_now = math.floor(time_since_start * fs)

            samples_missing = samples_target_now - samples_sent

            if samples_missing >= chunksize:

                time_of_chunks_last_sample = clock() - ( (samples_missing-chunksize) * delta_T )
                self.sendChunk(time_of_chunks_last_sample)
                samples_sent += chunksize

    def start(self):

        if self.get_state() is not Module.Status.STOPPED:
            return

        self.set_state(Module.Status.STARTING)

        # set channel count and channel labels based on which electrode setup was selected
        if self.get_parameter_value('setup') == 'bilateral':

            self.num_channels = 9
            self.channel_names = ["P3", "F3", "C3", "Cz", "T7", "P4", "F4", "C4", "T8"]

        if self.get_parameter_value('setup') == 'bilateral+EOG':

            self.num_channels = 11
            self.channel_names = ["P3", "F3", "C3", "Cz", "T7", "P4", "F4", "C4", "T8", "F7", "F8"]

        elif self.get_parameter_value('setup') == 'unilateralC3':

            self.num_channels = 5
            self.channel_names = ["P3", "F3", "C3", "Cz", "T7"]
        
        elif self.get_parameter_value('setup') == 'unilateralC3+EOG':

            self.num_channels = 7
            self.channel_names = ["P3", "F3", "C3", "Cz", "T7", "F7", "F8"]

        elif self.get_parameter_value('setup') == 'unilateralC4':

            self.num_channels = 5
            self.channel_names = ["Cz", "P4", "F4", "C4", "T8"]
        
        elif self.get_parameter_value('setup') == 'unilateralC4+EOG':

            self.num_channels = 7
            self.channel_names = ["Cz", "P4", "F4", "C4", "T8", "F7", "F8"]

        # generate stream info
        self.lsl_streaminfo = StreamInfo(
            globals.STREAM_NAME_RAW_SIGNAL,
            'EEG',
            self.num_channels,
            float(self.get_parameter_value("fs")),
            'double64',
            'uid'+str(random.randint(100000, 999999))
        )

        # add channel names to stream info
        LSLStreamInfoInterface.add_channel_names(self.lsl_streaminfo, self.channel_names)

        # add parameters to stream info
        LSLStreamInfoInterface.add_parameters(self.lsl_streaminfo, self.parameters)

        # init LSL outlet
        self.lsl_outlet = StreamOutlet(self.lsl_streaminfo, chunk_size=self.get_parameter_value('chunksize'))

        # init ringbuffers
        self.ringbuffer_c3 = RingBuffer(float, size=10*self.get_parameter_value("fs"), default_value=self.get_parameter_value('amplitude_smr'))
        self.ringbuffer_c4 = RingBuffer(float, size=10*self.get_parameter_value("fs"), default_value=self.get_parameter_value('amplitude_smr'))

        # init ringbuffers for EOG signal with random offset
        self.ringbuffer_eog_left = RingBuffer(float, size=10*self.get_parameter_value("fs"), default_value=(random.random()-0.5)*10000)
        self.ringbuffer_eog_right = RingBuffer(float, size=10*self.get_parameter_value("fs"), default_value=(random.random()-0.5)*10000)

        # start generator thread
        self.running = True
        self.generator_thread = Thread(daemon=True, target=self.signal_generator)
        self.generator_thread.start()

        self.set_state(Module.Status.RUNNING)

    def stop(self):

        if self.get_state() is not Module.Status.RUNNING:
            return

        self.set_state(Module.Status.STOPPING)

        # wait for signal generator thread to stop
        self.running = False
        while self.generator_thread.is_alive():
            time.sleep(0.1)

        time.sleep(0.1)
        self.generator_thread = None
        self.lsl_outlet = None

        self.set_state(Module.Status.STOPPED)

    def restart(self):
        self.stop()
        time.sleep(0.2)
        self.start()
"""