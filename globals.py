from typing import List
import pathlib
import sys
import os

# =========================================================================== #
# Global settings (constant)                                                  #
# =========================================================================== #

# Location of the default config file
BASE_PATH = os.getcwd()
DEFAULT_CONFIG_FILEPATH = os.path.join(BASE_PATH, 'defaultConfig.json')

# Absolute path to this software
PYTHONBCI_PATH = pathlib.Path(os.path.split(os.path.abspath(__file__))[0])

# configuration of LSL stream names
STREAM_NAME_RAW_SIGNAL: str = 'SourceEEG'
STREAM_NAME_PREPROCESSED_SIGNAL: str = 'PreprocessedData'
STREAM_NAME_CLASSIFIED_SIGNAL: str = 'ClassifierOutput'
STREAM_NAME_TASK_EVENTS: str = 'TaskOutput'
STREAM_NAME_FEEDBACK_STATES: str = 'FeedbackStates'


# Path where to store experiment data
DATA_PATH = PYTHONBCI_PATH / 'data'

# streams which will be recorded by LabRecorder
RECORD_STREAMS: List[str] = [
    STREAM_NAME_RAW_SIGNAL,
    STREAM_NAME_PREPROCESSED_SIGNAL,
    STREAM_NAME_CLASSIFIED_SIGNAL,
    STREAM_NAME_TASK_EVENTS,
    STREAM_NAME_FEEDBACK_STATES
]

# rate in Hz in which to render the feedback screen
FEEDBACK_FRAMERATE: int = 60

# if true, modules will sent true timestamps instead of those of the processed sample, which gives information about delays but hardens later analysis
OUTPUT_TRUE_TIMESTAMPS: bool = False


# =========================================================================== #
# Global variables                                                            #
# =========================================================================== #

# availability flag for LabStreamingLayer
LSLAvailable: bool = False
try:
    import pylsl
    pylsl.local_clock()
    LSLAvailable = True
except ImportError:
    pass
