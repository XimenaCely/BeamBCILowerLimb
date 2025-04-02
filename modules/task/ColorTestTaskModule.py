import random

import globals
from misc.enums import ExoState, Cue

from .TaskModule import TaskModule
from pylsl import IRREGULAR_RATE

from misc import log

logger = log.getLogger("EEGCalibrationTaskModule")


class ColorTestTaskModule(TaskModule):
    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME = "Color Test Task Module"
    MODULE_DESCRIPTION = ""

    REQUIRED_LSL_STREAMS = []

    TYPE_OUTPUT_STREAM: str = 'Markers'
    NUM_OUTPUT_CHANNELS: int = 4
    OUTPUT_SAMPLING_RATE: float = IRREGULAR_RATE
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
            'default': 2.0
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
        super().__init__()

        # outputs
        self.cue = Cue.EMPTY
        self.last_cue = self.cue

        self.state_left_exo = ExoState.HIDE_STOP
        self.state_right_exo = ExoState.HIDE_STOP

    # overwrite run method
    def run_task(self):

        self.wait(3)

        self.cue = Cue.STARTIN5
        self.wait(2)

        self.cue = Cue.EMPTY
        self.wait(1)

        # create a list of Hovleft / Hovright cues in alternating order
        cues = [Cue.EXO_INACTIVE, Cue.EXO_READY, Cue.EXO_ACTIVE, Cue.EXO_BLOCKED] * self.parameters['num_cues'].getValue()

        # play cues
        for c in cues:

            # display the cue
            self.cue = c
            logger.info("CUE: " + c.name)
            self.wait(self.parameters['cue_length'].getValue())

            # display no cue = ITI
            self.cue = Cue.EMPTY

            self.wait(self.parameters['cue_length'].getValue())

        self.cue = Cue.END
        self.wait(2)

        self.cue = Cue.EMPTY
        self.wait(3)

    # overwrite process_data input method
    def process_data(self, sample, timestamp):

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
            # Cue_Markers = self.cue.name.upper()

        self.last_cue = self.cue

        out_sample = [str(self.cue.value), str(self.state_left_exo.value), str(self.state_right_exo.value), Cue_Markers]
        return (out_sample, timestamp)