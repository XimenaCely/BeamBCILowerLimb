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


class LowerLimbClassificationModule(BasicClassificationModule):

    # make this a runnable descendant of the module-class
    MODULE_RUNNABLE: bool = True

    MODULE_NAME: str = "Lower limb Classification Module"
    MODULE_DESCRIPTION: str = """Classifies signals based on simple thresholds for lower limb.
    Input channels:
    Output channels:
        - NormOutCz
        - lowMuCz
    """
    MODULE_PATH = pathlib.Path(os.path.split(os.path.abspath(__file__))[0])

    NUM_OUTPUT_CHANNELS: int = 2
    OUTPUT_CHANNEL_FORMAT = cf_float32
    OUTPUT_CHANNEL_NAMES: list = ['NormOutCz', 'lowMuCz']

    # overwrite parameter definition which is empty by superclass
    PARAMETER_DEFINITION = [
        {
            'name': 'ReferenceCz',
            'displayname': 'Reference value Cz',
            'description': '',
            'type': float,
            'unit': '',
            'default': 15.0
        },
        {
            'name': 'ThresholdCz',
            'displayname': 'Threshold value Cz',
            'description': '',
            'type': float,
            'unit': '',
            'default': 0.2
        },
        {
            'name': 'ThresholdEOGtrigger',
            'displayname': 'Threshold EOG trigger',
            'description': '',
            'type': int,
            'unit': 'uV',
            'default': 1000
        }
    ]


    def __init__(self):
        super(LowerLimbClassificationModule, self).__init__()

        


    # mu-power normalization function
    def normalize_mu_power(self, mu_power, rv):

        return (float(mu_power) / float(rv)) - 1.0

    # overwrite the process data method to implement the classification
    def process_data(self, sample, timestamp):

        sample_cz = sample[0]
        # sample_c4 = sample[2]
        

        # normalize mu-power signals
        sample_cz_norm = self.normalize_mu_power(sample_cz, self.parameters['ReferenceCz'].getValue()) # self.PARAM_MU_NORM_RV_C3)
        # sample_c3_norm = self.normalize_mu_power(sample_c3, self.parameters['ReferenceC3'].getValue()) # self.PARAM_MU_NORM_RV_C3)
        # sample_c4_norm = self.normalize_mu_power(sample_c4, self.parameters['ReferenceC4'].getValue()) # self.PARAM_MU_NORM_RV_C4)

        # classify mu-power signals
        lowMuCz = 1.0 if sample_cz_norm < -self.parameters['ThresholdCz'].getValue() else 0.0
        # lowMuC4 = 1.0 if sample_c4_norm < -self.parameters['ThresholdC4'].getValue() else 0.0

        # classify EOG signal
        # HOVtrigger = 1.0 if sample_eog > self.parameters['ThresholdEOGtrigger'].getValue() else 0.0

        # build output sample
        outsample = [sample_cz_norm, lowMuCz]
        # print("class: ",outsample)
        # return the output sample with the input timestamp
        return (outsample, timestamp)
