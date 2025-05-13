
import random

import globals
from misc.enums import WalkExo, Cue, RelaxFeedbackState

from .TaskModule import TaskModule
from pylsl import IRREGULAR_RATE

from misc import log

logger = log.getLogger("EEGCalibrationLowerLimbTaskModule")


class EEGCalibrationLowerLimbTaskModule(TaskModule):

    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME = "EEG Calibration Lower Limb Task Module"
    MODULE_DESCRIPTION = ""

    REQUIRED_LSL_STREAMS = []

    TYPE_OUTPUT_STREAM: str= 'Markers'
    NUM_OUTPUT_CHANNELS: int = 5
    OUTPUT_CHANNEL_FORMAT: str = 'string'
    OUTPUT_CHANNEL_NAMES: list = ['Cue', 'WalkExoState', 'RelaxFeedbackState', 'Cue_marker','Cue_Exo_marker']

    # overwrite parameter definition which is empty by superclass
    PARAMETER_DEFINITION = [
        {
            'name': 'num_cues',
            'displayname': 'Number of Cues:',
            'description': 'How many walk and relax cues (each) will be displayed.',
            'type': int,
            'unit': '',
            'default': 10
        },
        {
            'name': 'cue_length',
            'displayname': 'Cue length',
            'description': 'How long the walk/relax cues will be displayed.',
            'type': float,
            'unit': 's',
            'default': 10.0
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
        },
        {
            'name': 'KFB_locked_time',
            'displayname': 'KFB locked time (s)',
            'description': 'How long the robot will be paused after obtaining the ERD',
            'type': float,
            'unit': 's',
            'default': 1.0
        }
    ]

    def __init__(self):
        super(EEGCalibrationLowerLimbTaskModule, self).__init__()

        # outputs
        self.cue = Cue.EMPTY

        self.state_exo = WalkExo.HIDE_STOP
        self.state_relax_fb = RelaxFeedbackState.HIDE_STOP

        self.control_by_eeg = False

        self.lsl_outlet_sampling_rate = IRREGULAR_RATE
        

    # overwrite run method
    def run_task(self):

        # fetch parameters for ITI length and calculate the amount of ITI which will be randomly determined
        min_iti_length: float = self.parameters['iti_min'].getValue()
        max_iti_length: float = self.parameters['iti_max'].getValue()
        feedback_locked_time: float = self.parameters['KFB_locked_time'].getValue()
        cue_length: float = self.parameters['cue_length'].getValue()

        iti_random_amount: float = max(0, max_iti_length-min_iti_length)
        
        self.wait(10)

        self.cue = Cue.STARTEXO
        self.wait(2.5)

        self.cue = Cue.STARTIN5
        self.wait(2.5)

        self.cue = Cue.EMPTY
        self.wait(2.5)

        # create a list of Hovleft / Hovright cues in alternating order
        cues = [Cue.WALK, Cue.RELAX] * self.parameters['num_cues'].getValue()

        # if the user selected to pseudo-randomize the order of cues, shuffle the cue-list
        if self.parameters['random_order'].getValue():
            random.shuffle(cues)

        # play cues
        for c in cues:

            # display the cue
            self.cue = c

            # if this is a close cue, enable EEG control
            if c == Cue.WALK:
                self.state_exo = WalkExo.PAUSE
                self.wait(feedback_locked_time)
                self.control_by_eeg = True
                self.wait(cue_length - feedback_locked_time)
            else:
                self.wait(cue_length)
            #################### check if needed
            # self.control_by_eeg = True
            # self.wait(self.parameters['cue_length'].getValue())

            # disabled EEG control after Cue
            self.control_by_eeg = False

            # display no cue = ITI
            self.cue = Cue.EMPTY

            self.state_exo = WalkExo.RESET
            self.state_relax_fb = RelaxFeedbackState.RESET

            self.wait(0.1)

            self.state_exo = WalkExo.HIDE_STOP
            self.state_relax_fb = RelaxFeedbackState.HIDE_STOP
            
            self.wait(min_iti_length + random.random()*iti_random_amount)


        self.state_exo = WalkExo.STOP
        self.cue = Cue.END
        self.wait(2)

        self.cue = Cue.EMPTY
        self.wait(3)


    
    # overwrite process_data input method
    def process_data(self, sample, timestamp):
        
        # copy inputs
        # self.norm_out_cz = sample[0]
        # self.low_mu_cz = sample[1] > 0.5
        
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
            
            if self.cue == Cue.WALK:
                if self.low_mu_cz:
                    self.state_exo = WalkExo.WALK
                else:
                    self.state_exo = WalkExo.PAUSE

            elif self.cue == Cue.RELAX:
                if self.low_mu_cz:
                    self.state_relax_fb = RelaxFeedbackState.STOP
                else:
                    self.state_relax_fb = RelaxFeedbackState.INCREASE

        #Sending command to the robot
        if self.state_exo == WalkExo.WALK and self.state_exo != self.last_state_exo:
            Cue_ExoMarkers = 'CONTINUE'
        elif self.state_exo == WalkExo.PAUSE and self.state_exo != self.last_state_exo:
            Cue_ExoMarkers = 'PAUSE'
        else:
            Cue_ExoMarkers = 'none'
        
        self.last_state_exo = self.state_exo
        
        # Send a string marker to analyze the data
        if self.cue == Cue.RELAX and self.cue != self.last_cue:
            Cue_Markers = 'RELAX'
            Cue_ExoMarkers = 'RELAX'
        elif self.cue == Cue.WALK and self.cue != self.last_cue:
            Cue_Markers = 'WALK'
        elif self.cue == Cue.STARTEXO and self.cue != self.last_cue:
            Cue_Markers = 'START_EXO'
            Cue_ExoMarkers = 'START_EXO'
        elif self.cue == Cue.STARTIN5 and self.cue != self.last_cue:
            Cue_Markers = 'START'
            Cue_ExoMarkers = 'RELAX'        #This will pause the robot after activating walking, but not inside the cue
        elif self.cue == Cue.END and self.cue != self.last_cue:
            Cue_Markers = 'END'
            Cue_ExoMarkers = 'END'
        else:
            Cue_Markers = 'none'
            
        self.last_cue = self.cue

        # print("exo?: ",Cue_ExoMarkers)
        out_sample = [str(self.cue.value), str(self.state_exo.value), str(self.state_relax_fb.value), Cue_Markers, Cue_ExoMarkers]
        return (out_sample, timestamp)

