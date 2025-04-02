from modules.task.TaskModule import TaskModule

from misc.enums import Cue, ExoState, Side
import globals

from misc.timing import clock

from misc import log

logger = log.getLogger("AsyncExoTaskModule")

class AsyncExoTaskModule(TaskModule):


    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME = "Async Exo control Task Module"
    MODULE_DESCRIPTION = "Allows to close exo by EEG and open it EOG."

    REQUIRED_LSL_STREAMS = [globals.STREAM_NAME_CLASSIFIED_SIGNAL]

    NUM_OUTPUT_CHANNELS: int = 3
    OUTPUT_CHANNEL_FORMAT: str = 'int32'
    OUTPUT_CHANNEL_NAMES: list = ['Cue', 'leftExoState', 'rightExoState']

    # overwrite parameter definition which is empty by superclass
    PARAMETER_DEFINITION = [
        {
            'name': 'exo_side',
            'displayname': 'Side of exoskeleton:',
            'description': '',
            'type': list,
            'unit': ['right', 'left'],
            'default': 'right'
        },
        {
            'name': 'close_erd_length',
            'displayname': 'ERD close length',
            'description': '',
            'type': float,
            'unit': 's',
            'default': 2.0
        },
        {
            'name': 'fasten_erd_length',
            'displayname': 'ERD fasten grip length',
            'description': '',
            'type': float,
            'unit': 's',
            'default': 1.0
        },

        {
            'name': 'send_close_length',
            'displayname': 'Send close command for',
            'description': '',
            'type': float,
            'unit': 's',
            'default': 2.0
        },
        {
            'name': 'send_fasten_length',
            'displayname': 'Send fasten grip command for',
            'description': '',
            'type': float,
            'unit': 's',
            'default': 1.0
        },
        {
            'name': 'send_open_length',
            'displayname': 'Send open command for',
            'description': '',
            'type': float,
            'unit': 's',
            'default': 8.0
        }
    ]


    STATE_INACTIVE = 0
    STATE_EEG_SENS = 1
    STATE_EEG_EOG_SENS = 2
    STATE_SEND_CLOSE = 3
    STATE_SEND_OPEN = 4
    STATE_SEND_FASTEN = 5

    STATE_NAMES = {
        STATE_INACTIVE: "not active",
        STATE_EEG_SENS: "EEG sensitive (exo open)",
        STATE_EEG_EOG_SENS: "EEG and EOG sensitive (exo closed)",
        STATE_SEND_CLOSE: "sending CLOSE",
        STATE_SEND_FASTEN: "sending FASTEN",
        STATE_SEND_OPEN: "sending OPEN"
    }

    def __init__(self):
        super(AsyncExoTaskModule, self).__init__()

        self.cue = Cue.EMPTY
        self.left_exo_state = ExoState.STOP
        self.right_exo_state = ExoState.STOP

        self.statemachine_state = self.STATE_INACTIVE
        self.entered_state = clock()
        self.eeg_start = None
    
        # placeholders
        self.norm_out_c3 = None
        self.norm_out_c4 = None
        self.HOV_left = None
        self.HOV_right = None
        self.low_mu_c3 = None
        self.low_mu_c4 = None
        self.low_mu = None
        self.HOV = None

       

    def run_task(self):
        logger.info("10s to start")
        self.wait(5)
        logger.info("5s to start")
        self.wait(5)
        self.statemachine_state = self.STATE_EEG_SENS
        self.entered_state = clock()
        logger.info(f"Changed state to {self.statemachine_state} {self.STATE_NAMES[self.statemachine_state]}")
        self.wait(60*120)

    def process_data(self, sample, timestamp):

        # copy inputs
        self.norm_out_c3 = sample[0]
        self.norm_out_c4 = sample[1]
        self.HOV_left = sample[2] > 0.5
        self.HOV_right = sample[3] > 0.5
        self.low_mu_c3 = sample[4] > 0.5
        self.low_mu_c4 = sample[5] > 0.5

        # select relevant EEG signal
        self.low_mu = self.low_mu_c3
        if Side(self.get_parameter_value("exo_side")) is Side.LEFT:
            self.low_mu = self.low_mu_c4

        # create non-directional EOG signal, which is True as soon as any directional signal is True
        self.HOV = self.HOV_left or self.HOV_right


        # state machine

        # inactive state
        if self.statemachine_state == self.STATE_INACTIVE:
            pass


        # close exo state
        elif self.statemachine_state == self.STATE_SEND_CLOSE:

            # if exo had time to close for 2s, stop sending close command and switch state
            if clock()-self.entered_state >= self.get_parameter_value("send_close_length"):

                self.statemachine_state = self.STATE_EEG_EOG_SENS
                self.entered_state = clock()
                logger.info(f"Change state to {self.statemachine_state} {self.STATE_NAMES[self.statemachine_state]}")

                self.left_exo_state = ExoState.STOP
                self.right_exo_state = ExoState.STOP

        # open exo state
        elif self.statemachine_state == self.STATE_SEND_OPEN:

            # if exo had time to open for 2s, stop sending open command and switch state
            if clock()-self.entered_state >= self.get_parameter_value("send_open_length"):

                self.statemachine_state = self.STATE_EEG_SENS
                self.entered_state = clock()
                logger.info(f"Change state to {self.statemachine_state} {self.STATE_NAMES[self.statemachine_state]}")


                self.left_exo_state = ExoState.STOP
                self.right_exo_state = ExoState.STOP

        # fasten grip / close further state
        elif self.statemachine_state == self.STATE_SEND_FASTEN:

            # if exo had time to close further for 1s, stop sending open command and switch state
            if clock()-self.entered_state >= self.get_parameter_value("send_fasten_length"):

                self.statemachine_state = self.STATE_EEG_EOG_SENS
                self.entered_state = clock()
                logger.info(f"Change state to {self.statemachine_state} {self.STATE_NAMES[self.statemachine_state]}")


                self.left_exo_state = ExoState.STOP
                self.right_exo_state = ExoState.STOP

        # exo is open and resting state
        elif self.statemachine_state == self.STATE_EEG_SENS:
            
            # if ERD is starting:
            if self.eeg_start is None and self.low_mu:
                self.eeg_start = clock()

            # if ERD is ongoing
            elif self.eeg_start is not None and self.low_mu:
                
                # if ERD exceeded 2s -> close exo
                if clock()-self.eeg_start >= self.get_parameter_value("close_erd_length"):

                    self.statemachine_state = self.STATE_SEND_CLOSE
                    self.entered_state = clock()
                    logger.info(f"Change state to {self.statemachine_state} {self.STATE_NAMES[self.statemachine_state]}")

                    if Side(self.get_parameter_value("exo_side")) is Side.RIGHT:
                        self.right_exo_state = ExoState.CLOSE
                    elif Side(self.get_parameter_value("exo_side")) is Side.LEFT:
                        self.left_exo_state = ExoState.CLOSE

                    self.eeg_start = None

            # if ERD ended
            elif self.eeg_start is not None and not self.low_mu:

                self.eeg_start = None


        # exo is open and resting state
        elif self.statemachine_state == self.STATE_EEG_EOG_SENS:
            
            # if EOG is positive -> opening is required
            if self.HOV:

                # stop any EEG counting
                self.eeg_start = None

                # change to send open command state
                self.statemachine_state = self.STATE_SEND_OPEN
                self.entered_state = clock()
                logger.info(f"Change state to {self.statemachine_state} {self.STATE_NAMES[self.statemachine_state]}")


                # set exo state for active exo
                if Side(self.get_parameter_value("exo_side")) == Side.RIGHT:
                    self.right_exo_state = ExoState.OPEN
                elif Side(self.get_parameter_value("exo_side")) == Side.LEFT:
                    self.left_exo_state = ExoState.OPEN

            # if ERD is starting:
            elif self.eeg_start is None and self.low_mu:
                self.eeg_start = clock()

            # if ERD is ongoing
            elif self.eeg_start is not None and self.low_mu:
                
                # if ERD exceeded 1s -> fasten / further close exo grip
                if clock()-self.eeg_start >= self.get_parameter_value("fasten_erd_length"):

                    self.statemachine_state = self.STATE_SEND_FASTEN
                    self.entered_state = clock()
                    logger.info(f"Change state to {self.statemachine_state} {self.STATE_NAMES[self.statemachine_state]}")

                    if Side(self.get_parameter_value("exo_side")) is Side.RIGHT:
                        self.right_exo_state = ExoState.CLOSE
                    elif Side(self.get_parameter_value("exo_side")) is Side.LEFT:
                        self.left_exo_state = ExoState.CLOSE

                    self.eeg_start = None

            # if ERD ended
            elif self.eeg_start is not None and not self.low_mu:

                self.eeg_start = None


        # create output sample and return
        out_sample = [self.cue.value, self.left_exo_state.value, self.right_exo_state.value]
        return (out_sample, timestamp)


    def onStop(self):

        if (
            self.statemachine_state == self.STATE_SEND_CLOSE or 
            self.statemachine_state == self.STATE_SEND_FASTEN or 
            self.statemachine_state == self.STATE_EEG_EOG_SENS
        ):

            wait_time = 3
            logger.info(f"Exo is not opened. Exo will open in {wait_time}s")

            self.statemachine_state = self.STATE_INACTIVE
            
            self.wait(wait_time)

            # set exo state for active exo
            if Side(self.get_parameter_value("exo_side")) == Side.RIGHT:
                self.right_exo_state = ExoState.OPEN
            elif Side(self.get_parameter_value("exo_side")) == Side.LEFT:
                self.left_exo_state = ExoState.OPEN
        
            self.wait(3)

        self.right_exo_state = ExoState.STOP
        self.left_exo_state = ExoState.STOP
        self.wait(1)
