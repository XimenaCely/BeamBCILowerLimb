"""
Parsing of command line arguments and/or loading default configuration
Can be imported globally using
`import base_parser
args = base_parser.args
`. Then args.<argument> can be accessed.
Before that, the following needs to be called once (in MainProgram.py)
`import base_parser
base_parser.parse_args()
args = base_parser.args
`
"""

import argparse
from misc import log
import json
import os
from types import SimpleNamespace as Namespace
from pathlib import Path

from globals import DEFAULT_CONFIG_FILEPATH

logger = log.getLogger(__name__)


def load_default_config():
    """
    Generate and return a namespace according to the default configuration
    This is so we can override it with parsed arguments if given
    """
    if not os.path.isfile(DEFAULT_CONFIG_FILEPATH):
        raise FileNotFoundError(f"The config file at {DEFAULT_CONFIG_FILEPATH} cannot be found")
    with open(DEFAULT_CONFIG_FILEPATH, 'r') as fp:
        config = json.load(fp, object_hook=lambda d: Namespace(**d))

    return config


def parse_args():
    global args

    default_config = load_default_config()

    parser = argparse.ArgumentParser(description='PythonBCI Operator GUI')
    parser.add_argument('-X', '--dev_mode', action='store_true',
                        help='Start in Developer mode')
    parser.add_argument('-exp', '--experiment_config', type=Path,
                        default=None,
                        help='Provide path to an experiment configuration which should be loaded at startup')
    args = parser.parse_args(namespace=default_config)

    logger.info(f"Parsed arguments from command line and config: {args}")
    return args

