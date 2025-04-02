import random

import globals
from misc.enums import ExoState, Cue

from .TaskModule import TaskModule

from misc import log

logger = log.getLogger("EEGCalibrationTaskModule")




class EOGCalibrationTaskModule(TaskModule):

    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME = "EOG Calibration Task Module"
    MODULE_DESCRIPTION = ""

    REQUIRED_LSL_STREAMS = []

    NUM_OUTPUT_CHANNELS: int = 3
    OUTPUT_CHANNEL_FORMAT: str = 'int32'
    OUTPUT_CHANNEL_NAMES: list = ['Cue', 'leftExoState', 'rightExoState']

    # direction constants
    DIRECTIONS_LEFT_AND_RIGHT: str = 'left and right'
    DIRECTIONS_ONLY_LEFT: str = 'only left'
    DIRECTIONS_ONLY_RIGHT: str = 'only right'


    # overwrite parameter definition which is empty by superclass
    PARAMETER_DEFINITION = [
        {
            'name': 'num_cues',
            'displayname': 'Number of Cues each',
            'description': 'How many cues for each direction will be displayed.',
            'type': int,
            'unit': '',
            'default': 5
        },
        {
            'name': 'directions',
            'displayname': 'Directions',
            'description': '',
            'type': list,
            'unit': [DIRECTIONS_LEFT_AND_RIGHT, DIRECTIONS_ONLY_LEFT, DIRECTIONS_ONLY_RIGHT],
            'default': DIRECTIONS_LEFT_AND_RIGHT
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
            'name': 'cue_length',
            'displayname': 'Cue display time',
            'description': 'How long (seconds) a cue is displayed',
            'type': float,
            'unit': 's',
            'default': 2.0
        },
        {
            'name': 'iti_min',
            'displayname': 'Min ITI length',
            'description': 'How long the ITI (inter trial interval) will last at least',
            'type': float,
            'unit': 's',
            'default': 2.5
        },
        {
            'name': 'iti_max',
            'displayname': 'Max ITI length',
            'description': 'How long the ITI (inter trial interval) will last at most',
            'type': float,
            'unit': 's',
            'default': 4.5
        }
    ]

    def __init__(self):
        super(EOGCalibrationTaskModule, self).__init__()

        # outputs
        self.cue = Cue.EMPTY
        

    # overwrite run method
    def run_task(self):
        
        self.wait(10)

        self.cue = Cue.STARTIN5
        self.wait(2.5)

        self.cue = Cue.EMPTY
        self.wait(2.5)


        # select, whether cues will be to both sides or only left/right
        cues = [Cue.HOVLEFT, Cue.HOVRIGHT]

        if self.get_parameter_value('directions') == self.DIRECTIONS_ONLY_LEFT:
            cues = [Cue.HOVLEFT]
        elif self.get_parameter_value('directions') == self.DIRECTIONS_ONLY_RIGHT:
            cues = [Cue.HOVRIGHT]

        # multiply cues by number of cues to display (each)
        cues = cues * self.parameters['num_cues'].getValue()

        # if the user selected to pseudo-randomize the order of cues, shuffle the cue-list
        if self.parameters['random_order'].getValue():
            random.shuffle(cues)

        # play cues
        for c in cues:

            self.cue = c
            self.wait(self.get_parameter_value('cue_length'))

            # do ITI: wait for   iti_min <= wait-time <= iti_max   seconds
            self.cue = Cue.EMPTY
            self.wait(self.get_parameter_value('iti_min') + random.random() * (self.get_parameter_value('iti_max') - self.get_parameter_value('iti_min') ))

        self.cue = Cue.END
        self.wait(2)

        self.cue = Cue.EMPTY
        self.wait(3)


    
    # overwrite process_data input method
    def process_data(self, sample, timestamp):

        out_sample = [self.cue.value, ExoState.STOP.value, ExoState.STOP.value]
        return (out_sample, timestamp)
