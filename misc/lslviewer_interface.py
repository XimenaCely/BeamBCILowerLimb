import subprocess
import tomllib
from typing import cast

from platform import system, machine
from globals import PYTHONBCI_PATH

LSL_VIEWER_DIR = PYTHONBCI_PATH / "tools" / "lslviewer"
LSL_VIEWER_CONFIG_FILE = LSL_VIEWER_DIR / "executable.toml"

def determine_executable_path() -> str:
    
    if not LSL_VIEWER_CONFIG_FILE.exists():
        raise Exception("LslViewer executable config file is missing in {}".format(LSL_VIEWER_CONFIG_FILE))

    executable_config = None

    try:
        with open(LSL_VIEWER_CONFIG_FILE, "rb") as fh:
            executable_config = tomllib.load(fh)
    except Exception as e:
        raise Exception("Error loading the LslViewer executable config file in {}: {}".format(LSL_VIEWER_CONFIG_FILE, e))

    if type(executable_config) is not dict or type(executable_config.get("lslviewer_executable")) is not str:
        raise Exception("Error: Invalid information in LslViewer executable config file: {}".format(LSL_VIEWER_CONFIG_FILE))

    EXECUTABLE_PATH = LSL_VIEWER_DIR / cast(str, executable_config.get("lslviewer_executable"))

    if not EXECUTABLE_PATH.exists():
        raise Exception("Error: LslViewer executable file does not exist: {}.".format(EXECUTABLE_PATH))

    return str(EXECUTABLE_PATH)

def start_lsl_viewer(args: list):

    # convert to str: if pyth is not give as string but as Path-Object -> conversion is necessary
    process_args = [determine_executable_path()] + args

    # start the subprocess
    process = subprocess.Popen(process_args, shell=False)

    return process

