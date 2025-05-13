import random

import globals
from misc.enums import ExoState, Cue

from .TaskModule import TaskModule
from pylsl import IRREGULAR_RATE

from misc import log

logger = log.getLogger("EEGCalibrationTaskModule")


class EEGCalibrationTaskModule(TaskModule):

    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME = "EEG Calibration Task Module"
    MODULE_DESCRIPTION = ""

    REQUIRED_LSL_STREAMS = []

    TYPE_OUTPUT_STREAM: str= 'Markers'
    NUM_OUTPUT_CHANNELS: int = 4
    OUTPUT_CHANNEL_FORMAT: str = 'string'
    OUTPUT_CHANNEL_NAMES: list = ['Cue', 'leftExoState', 'rightExoState', 'Cue_marker']

    # overwrite parameter definition which is empty by superclass
    PARAMETER_DEFINITION = [
        {
            'name': 'num_cues',
            'displayname': 'Number of Cues:',
            'description': 'How many close and relax cues (each) will be displayed.',
            'type': int,
            'unit': '',
            'default': 10
        },
        {
            'name': 'cue_length',
            'displayname': 'Cue length',
            'description': 'How long the close/relax cues will be displayed.',
            'type': float,
            'unit': 's',
            'default': 5.0
        },
        {
            'name': 'random_order',
            'displayname': 'Pseudo-random Order',
            'description': 'Whether to pseudo-randomize the order of cues or display them alternating.',
            'type': bool,
            'unit': '',
            'default': False
        },
        {
            'name': 'iti_min',
            'displayname': 'Min ITI length',
            'description': 'How long the ITI (inter trial interval) will last at least',
            'type': float,
            'unit': 's',
            'default': 1.0
        },
        {
            'name': 'iti_max',
            'displayname': 'Max ITI length',
            'description': 'How long the ITI (inter trial interval) will last at most',
            'type': float,
            'unit': 's',
            'default': 3.0
        }
    ]

    def __init__(self):
        super(EEGCalibrationTaskModule, self).__init__()

        # outputs
        self.cue = Cue.EMPTY

        self.state_left_exo = ExoState.HIDE_STOP
        self.state_right_exo = ExoState.HIDE_STOP

        self.control_by_eeg = False

        self.lsl_outlet_sampling_rate = IRREGULAR_RATE
        

    # overwrite run method
    def run_task(self):

        # fetch parameters for ITI length and calculate the amount of ITI which will be randomly determined
        min_iti_length: float = self.parameters['iti_min'].getValue()
        max_iti_length: float = self.parameters['iti_max'].getValue()
        iti_random_amount: float = max(0, max_iti_length-min_iti_length)
        
        self.wait(10)

        self.cue = Cue.STARTIN5
        self.wait(2.5)

        self.cue = Cue.EMPTY
        self.wait(2.5)

        # create a list of Hovleft / Hovright cues in alternating order
        cues = [Cue.CLOSE, Cue.RELAX] * self.parameters['num_cues'].getValue()

        # if the user selected to pseudo-randomize the order of cues, shuffle the cue-list
        if self.parameters['random_order'].getValue():
            random.shuffle(cues)

        # play cues
        for c in cues:

            # display the cue
            self.cue = c

            # if this is a close cue, enable EEG control
            if c == Cue.CLOSE:
                self.control_by_eeg = True

            self.wait(self.parameters['cue_length'].getValue())

            # disabled EEG control after Cue
            self.control_by_eeg = False

            # display no cue = ITI
            self.cue = Cue.EMPTY

            # reopen the Exo
            self.state_left_exo = ExoState.HIDE_OPEN
            self.state_right_exo = ExoState.HIDE_OPEN
            
            self.wait(min_iti_length + random.random()*iti_random_amount)


        self.cue = Cue.END
        self.wait(2)

        self.cue = Cue.EMPTY
        self.wait(3)


    
    # overwrite process_data input method
    def process_data(self, sample, timestamp):
        
        # copy inputs
        self.norm_out_c3 = sample[0]
        self.norm_out_c4 = sample[1]
        self.norm_out_cz = sample[2]
        self.HOV_left = sample[3] > 0.5
        self.HOV_right = sample[4] > 0.5
        self.low_mu_c3 = sample[5] > 0.5
        self.low_mu_c4 = sample[6] > 0.5
        self.low_mu_cz = sample[7] > 0.5


        # set some outputs
        if self.control_by_eeg:

            if self.low_mu_c3:
                self.state_right_exo = ExoState.CLOSE
            else:
                self.state_right_exo = ExoState.STOP
            
            if self.low_mu_c4:
                self.state_left_exo = ExoState.CLOSE
            else:
                self.state_left_exo = ExoState.STOP
            
            if self.low_mu_cz:
                self.state_left_exo = ExoState.CLOSE
            else:
                self.state_left_exo = ExoState.STOP

        # Send a string marker to analyze the data
        if self.cue == Cue.CLOSE and self.cue != self.last_cue:
            Cue_Markers = 'CLOSE'
        elif self.cue == Cue.RELAX and self.cue != self.last_cue:
            Cue_Markers = 'RELAX'
        elif self.cue == Cue.STARTIN5 and self.cue != self.last_cue:
            Cue_Markers = 'START'
        elif self.cue == Cue.END and self.cue != self.last_cue:
            Cue_Markers = 'END'
        else:
            Cue_Markers = 'none'

        self.last_cue = self.cue

        out_sample = [str(self.cue.value), str(self.state_left_exo.value), str(self.state_right_exo.value),Cue_Markers]
        return (out_sample, timestamp)
