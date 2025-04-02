import pathlib
import os
import sys
import time
from typing import List, Union
import subprocess
import random

from pylsl import resolve_streams, IRREGULAR_RATE, StreamInfo, cf_float32

import globals
from modules.classification.BasicClassificationModule import BasicClassificationModule


class ThresholdClassificationModule(BasicClassificationModule):

    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME: str = "Threshold Classification Module"
    MODULE_DESCRIPTION: str = """Classifies signals based on simple thresholds.
    Input channels:
    Output channels:
        - NormOutC3
        - NormOutC4
        - HOVleft
        - HOVright
        - lowMuC3
        - lowMuC4
    """
    MODULE_PATH = pathlib.Path(os.path.split(os.path.abspath(__file__))[0])

    NUM_OUTPUT_CHANNELS: int = 6
    OUTPUT_CHANNEL_FORMAT = cf_float32
    OUTPUT_CHANNEL_NAMES: list = ['NormOutC3', 'NormOutC4', 'HOVleft', 'HOVright', 'lowMuC3', 'lowMuC4']

    # overwrite parameter definition which is empty by superclass
    PARAMETER_DEFINITION = [
        {
            'name': 'ReferenceC3',
            'displayname': 'Reference value C3',
            'description': '',
            'type': float,
            'unit': '',
            'default': 15.0
        },
        {
            'name': 'ReferenceC4',
            'displayname': 'Reference value C4',
            'description': '',
            'type': float,
            'unit': '',
            'default': 15.0
        },
        {
            'name': 'ThresholdC3',
            'displayname': 'Threshold value C3',
            'description': '',
            'type': float,
            'unit': '',
            'default': 0.2
        },
        {
            'name': 'ThresholdC4',
            'displayname': 'Threshold value C4',
            'description': '',
            'type': float,
            'unit': '',
            'default': 0.2
        },
        {
            'name': 'ThresholdEOGleft',
            'displayname': 'Threshold left EOG',
            'description': '',
            'type': int,
            'unit': 'uV',
            'default': 1000
        },
        {
            'name': 'ThresholdEOGright',
            'displayname': 'Threshold right EOG',
            'description': '',
            'type': int,
            'unit': 'uV',
            'default': -1000
        }
    ]


    def __init__(self):
        super(ThresholdClassificationModule, self).__init__()

        


    # mu-power normalization function
    def normalize_mu_power(self, mu_power, rv):

        return (float(mu_power) / float(rv)) - 1.0

    # overwrite the process data method to implement the classification
    def process_data(self, sample, timestamp):

        # extract single values
        sample_eog = sample[0]
        sample_c3 = sample[1]
        sample_c4 = sample[2]
        

        # normalize mu-power signals
        sample_c3_norm = self.normalize_mu_power(sample_c3, self.parameters['ReferenceC3'].getValue()) # self.PARAM_MU_NORM_RV_C3)
        sample_c4_norm = self.normalize_mu_power(sample_c4, self.parameters['ReferenceC4'].getValue()) # self.PARAM_MU_NORM_RV_C4)

        # classify mu-power signals
        lowMuC3 = 1.0 if sample_c3_norm < -self.parameters['ThresholdC3'].getValue() else 0.0
        lowMuC4 = 1.0 if sample_c4_norm < -self.parameters['ThresholdC4'].getValue() else 0.0

        # classify EOG signal
        HOVleft = 1.0 if sample_eog > self.parameters['ThresholdEOGleft'].getValue() else 0.0
        HOVright = 1.0 if sample_eog < self.parameters['ThresholdEOGright'].getValue() else 0.0

        # build output sample
        outsample = [sample_c3_norm, sample_c4_norm, HOVleft, HOVright, lowMuC3, lowMuC4]

        # return the output sample with the input timestamp
        return (outsample, timestamp)
