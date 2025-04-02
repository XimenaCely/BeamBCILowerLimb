import globals
from misc.enums import ExoState, Cue

from .TaskModule import TaskModule


class ExampleTaskModule(TaskModule):

    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME = "Example Task Module"
    MODULE_DESCRIPTION = " - "

    REQUIRED_LSL_STREAMS = [globals.STREAM_NAME_CLASSIFIED_SIGNAL]


    NUM_OUTPUT_CHANNELS: int = 3
    OUTPUT_CHANNEL_FORMAT: str = 'int32'
    OUTPUT_CHANNEL_NAMES: list = []


    def __init__(self):
        super(ExampleTaskModule, self).__init__()

        # internal states
        self.control_by_eeg = False

        # inputs
        self.norm_out_c3 = None
        self.norm_out_c4 = None
        self.HOV_left = None
        self.HOV_right = None
        self.low_mu_c3 = None
        self.low_mu_c4 = None


        # outputs
        self.cue_id = Cue.EMPTY
        self.state_left_exo = ExoState.STOP
        self.state_right_exo = ExoState.STOP


    # overwrite run method
    def run_task(self):
        
        self.wait(10)

        self.cue_id = Cue.STARTIN5

        self.wait(2.5)

        self.cue_id = Cue.EMPTY

        self.wait(2.5)

        for i in range(5):

            self.cue_id = Cue.HOVLEFT

            self.wait(2)

            self.cue_id = Cue.EMPTY

            self.wait(3)

            self.cue_id = Cue.HOVRIGHT

            self.wait(2)

            self.cue_id = Cue.EMPTY

            self.wait(3)

        self.wait(5)

        self.cue_id = Cue.STARTIN5

        self.wait(2)

        self.cue_id = Cue.EMPTY

        self.wait(3)

        for i in range(10):

            self.cue_id = Cue.CLOSE

            self.wait(5)

            self.cue_id = Cue.EMPTY

            self.wait(3)

            self.cue_id = Cue.RELAX

            self.wait(5)

            self.cue_id = Cue.EMPTY

            self.wait(3)


        self.wait(2)

        self.cue_id = Cue.END

        self.wait(2)

        self.cue_id = Cue.EMPTY

        self.wait(3)


    
    # overwrite process_data input method
    def process_data(self, sample, timestamp):

        # copy inputs
        self.norm_out_c3 = sample[0]
        self.norm_out_c4 = sample[1]
        self.HOV_left = sample[2] > 0.5
        self.HOV_right = sample[3] > 0.5
        self.low_mu_c3 = sample[4] > 0.5
        self.low_mu_c4 = sample[5] > 0.5

        # set some outputs
        if self.control_by_eeg:

            if self.low_mu_c3:
                self.state_right_exo = ExoState.CLOSE
            
            if self.low_mu_c4:
                self.state_left_exo = ExoState.CLOSE

        out_sample = list(map(lambda x: x.value, [self.cue_id, self.state_left_exo, self.state_right_exo]))
        return (out_sample, timestamp)
