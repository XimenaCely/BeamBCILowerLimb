import random

from misc.enums import ExoState, Cue

from .EEGCalibrationTaskModule import EEGCalibrationTaskModule


class EEGCalibrationTaskWithHRVModule(EEGCalibrationTaskModule):

    MODULE_NAME = "EEG Calibration Task Module + HRV"

    def __init__(self):
        super().__init__()

        # change number of cues, iti min and max automatically
        self.setParameter('num_cues', 30)
        self.setParameter('iti_min', 4.0)
        self.setParameter('iti_max', 6.0)
        self.setParameter('random_order', True)

    # overwrite run method
    def run_task(self):

        # fetch parameters for ITI length and calculate the amount of ITI which will be randomly determined
        min_iti_length: float = self.parameters['iti_min'].getValue()
        max_iti_length: float = self.parameters['iti_max'].getValue()
        iti_random_amount: float = max(0, max_iti_length-min_iti_length)

        self.wait(10)

        # wait until HRV becomes available
        self.cue = Cue.RELAX
        self.state_left_exo = ExoState.HIDE_OPEN
        self.state_right_exo = ExoState.HIDE_OPEN
        self.wait(120)

        self.cue = Cue.STARTIN5
        self.wait(2.5)

        self.cue = Cue.EMPTY
        self.wait(2.5)

        # randomize cues only within blocks
        # NOT handling cue numbers not divisible by 5
        cues_per_block = 5
        n_blocks = self.parameters['num_cues'].getValue()//cues_per_block
        
        for n in range(n_blocks):
            # create a list of Hovleft / Hovright cues in alternating order
            cues = [Cue.CLOSE, Cue.RELAX] * cues_per_block

            # if the user selected to pseudo-randomize the order of cues, shuffle the cue-list
            if self.parameters['random_order'].getValue():
                random.shuffle(cues)

            # play cues
            for c in cues:

                # display the cue
                self.cue = c

                # enable EEG control
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
