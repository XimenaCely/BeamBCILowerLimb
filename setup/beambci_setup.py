MIN_PYTHON = (3, 11)
import sys
if sys.version_info < MIN_PYTHON:
    print("This script requires Python 3.11 or newer. However, you are currently running Python " + str(sys.version_info.major) + "." + str(sys.version_info.minor) + ". Terminating.")
    sys.exit(0)

from typing import Any, Tuple
import urllib.request
import socket
import platform
import tomllib
import pathlib
import os
import subprocess
import shutil
import time
import zipfile
import hashlib

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def md5_of_file(fpath: pathlib.Path) -> str:

    if not fpath.exists() or not fpath.is_file():
        return ""

    try:

        with open(fpath, 'rb') as fh:

            return hashlib.md5(fh.read()).hexdigest()

    except:

        return ""


def download_file(url: str, out_file: str|pathlib.Path, chunk_size=1024*128, report: bool = True):
    response = urllib.request.urlopen(url, timeout=10);
    total_size = response.getheader('Content-Length').strip()
    total_size = int(total_size)
    bytes_so_far = 0

    def report_fn(bytes_so_far, chunk_size, total_size):
        bar_width = 50
        completed = float(bytes_so_far) / total_size
        #percent = round(percent*100, 2)
        sys.stdout.write("Downloading: [%s%s]  %.01f/%.01f MB (%0.1f%%)\r" % 
            ("#"*int(bar_width*completed), 
             "_"*(bar_width-int(bar_width*completed)), 
             bytes_so_far / 1024**2, 
             total_size / 1024**2, 
             completed*100))

        if bytes_so_far >= total_size:
            sys.stdout.write('\n')

    with open(out_file, "wb") as fh:
        while 1:
            chunk = response.read(chunk_size)
            bytes_so_far += fh.write(chunk) #len(chunk)

            if not chunk:
                break

            if report:
                report_fn(bytes_so_far, chunk_size, total_size)


def on_windows() -> bool:
    return platform.system().lower() == "windows"


def set_file_executable(file_path: str | pathlib.Path):
    if not on_windows():
        subprocess.run(["chmod", "a+x", str(file_path)])


def load_config() -> Tuple[str, Any]:
    
    build_identifier = [platform.system().lower(), platform.machine().lower()]

    with open(SETUP_DIR / "urls.toml", "rb") as fh:
        urls = tomllib.load(fh)

    config_name = None
    for config_name, config in urls.items():

        if build_identifier in config.get("platforms", []):
            return config_name, config

    print(bcolors.FAIL + "Error: Could not find an installation configuration for this type of system: %s/%s" % (build_identifier[0], build_identifier[1]))
    sys.exit(0)


def cancel_setup():

    print(bcolors.FAIL + "Setup cancelled. Deleting temporary files and partly completed installation." + bcolors.ENDC)

    if TMP_DIR.exists():
        shutil.rmtree(TMP_DIR)

    if MICROMAMBA_DIR.exists():
        shutil.rmtree(MICROMAMBA_DIR)

    if LABRECORDER_EXECUTABLE_CONFIG_FILE.exists():
        LABRECORDER_EXECUTABLE_CONFIG_FILE.unlink()

    if LABRECORDER_EXTRACT_DIR.exists():
        shutil.rmtree(LABRECORDER_EXTRACT_DIR)

    if LSLVIEWER_DIR.exists():
        shutil.rmtree(LSLVIEWER_DIR)
    
    print(bcolors.OKGREEN + "Done." + bcolors.ENDC)

    sys.exit(0)


def setup_python_environment(config: dict):

    # remove old installation if present
    if MICROMAMBA_DIR.exists():
        shutil.rmtree(MICROMAMBA_DIR)

    # set micromamba root dir, where environments and everything related is stored
    MICROMAMBA_ROOT = MICROMAMBA_DIR / "root"
    MICROMAMBA_ROOT.mkdir(parents=True, exist_ok=True)

    # download micromamba
    MICROMAMBA_URL = config.get("micromamba", {}).get("url", "")
    MICROMAMBA_EXECUTABLE_NAME = "micromamba.exe" if on_windows() else "micromamba" #MINIFORGE_URL.split("/")[-1]
    MICROMAMBA_EXECUTABLE_FILE_PATH = MICROMAMBA_DIR / MICROMAMBA_EXECUTABLE_NAME
    download_file(MICROMAMBA_URL, MICROMAMBA_EXECUTABLE_FILE_PATH)
   
    # check hash of downloaded file
    if md5_of_file(MICROMAMBA_EXECUTABLE_FILE_PATH) != config.get("micromamba", {}).get("md5", ""):
        print(bcolors.FAIL + "ERROR: MD5 hash '{}' of downloaded file does not match expected '{}'.".format(
            md5_of_file(MICROMAMBA_EXECUTABLE_FILE_PATH), config.get("micromamba", {}).get("md5", "")
        ), bcolors.ENDC)
        cancel_setup()

    # test micromamba by letting it output its version and comparing it against the stored one
    set_file_executable(MICROMAMBA_EXECUTABLE_FILE_PATH)
    test_run_result = subprocess.run([str(MICROMAMBA_EXECUTABLE_FILE_PATH), "--version"], capture_output=True)
    if bytes(config.get("micromamba", {}).get("version", "XXXXXXXXXX"), "ASCII") not in test_run_result.stdout:
        print(bcolors.FAIL + "ERROR: MicroMamba can not be executed.")
        cancel_setup()


    print("Setting up Python environment - please wait.")
    subprocess.run([
        str(MICROMAMBA_EXECUTABLE_FILE_PATH),
        "create",
        "--root-prefix", '{}'.format(str(MICROMAMBA_ROOT)),
        "-f", '{}'.format(str(SETUP_DIR / "environment.yml")),
        "--yes",
        "-c", "conda-forge"
    ])


def setup_labrecorder_cli(config: dict):
    LABRECORDER_URL = config.get("labrecorder_cli", {}).get("url")
    LABRECORDER_DOWNLOAD_FILE_NAME = LABRECORDER_URL.split("/")[-1]
    LABRECORDER_DOWNLOAD_FILE_PATH = TMP_DIR / LABRECORDER_DOWNLOAD_FILE_NAME

    if LABRECORDER_DOWNLOAD_FILE_PATH.exists():
        LABRECORDER_DOWNLOAD_FILE_PATH.unlink()
    
    download_file(LABRECORDER_URL, LABRECORDER_DOWNLOAD_FILE_PATH)
    # ToDo: check MD5

    if LABRECORDER_EXTRACT_DIR.exists():
        shutil.rmtree(LABRECORDER_EXTRACT_DIR)

    LABRECORDER_EXTRACT_DIR.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(LABRECORDER_DOWNLOAD_FILE_PATH, "r") as zip_handle:
        zip_handle.extractall(LABRECORDER_EXTRACT_DIR)

    LABRECORDER_EXECUTABLE_REL_PATH: str = config.get("labrecorder_cli", {}).get("executable")
    LABRECORDER_EXECUTABLE_FULL_PATH = LABRECORDER_EXTRACT_DIR / LABRECORDER_EXECUTABLE_REL_PATH

    set_file_executable(LABRECORDER_EXECUTABLE_FULL_PATH)


    with open(LABRECORDER_EXECUTABLE_CONFIG_FILE, "w") as fh:
        fh.write("labrecorder_executable = \"%s\"\n" % str(LABRECORDER_EXECUTABLE_FULL_PATH.relative_to(LABRECORDER_DIR)).replace("\\", "\\\\"))
        fh.write("downloaded = \"%s\"\n" % time.asctime(time.localtime()))


def setup_lslviewer(config: dict):
    LSLVIEWER_URL = config.get("lslviewer").get("url")
    LSLVIEWER_DOWNLOAD_FILE_NAME = LSLVIEWER_URL.split("/")[-1]
    LSLVIEWER_DOWNLOAD_FILE_PATH = TMP_DIR / LSLVIEWER_DOWNLOAD_FILE_NAME

    if LSLVIEWER_DOWNLOAD_FILE_PATH.exists():
        LSLVIEWER_DOWNLOAD_FILE_PATH.unlink()
    
    download_file(LSLVIEWER_URL, LSLVIEWER_DOWNLOAD_FILE_PATH)
    # ToDo: check MD5

    FINAL_LSLVIEWER_PATH = LSLVIEWER_DIR / LSLVIEWER_DOWNLOAD_FILE_NAME

    FINAL_LSLVIEWER_PATH.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(LSLVIEWER_DOWNLOAD_FILE_PATH, FINAL_LSLVIEWER_PATH)
    set_file_executable(FINAL_LSLVIEWER_PATH)

    with open(LSLVIEWER_EXECUTABLE_TOML_PATH, "w") as fh:
        fh.write("lslviewer_executable = \"%s\"\n" % LSLVIEWER_DOWNLOAD_FILE_NAME)
        fh.write("downloaded = \"%s\"\n" % time.asctime(time.localtime()))


if __name__ == '__main__':

    if on_windows():
        os.system("color")

    print(bcolors.OKCYAN, bcolors.BOLD, r"""
   ___                     ___   _____ ____
  / _ ) ___  ___ _ __ _   / _ ) / ___//  _/
 / _  |/ -_)/ _ `//  ' \ / _  |/ /__ _/ /  
/____/ \__/ \_,_//_/_/_//____/ \___//___/  
                                           
    """, bcolors.ENDC)

    print(
        bcolors.BOLD, "Welcome to the BeamBCI setup!\n\n", bcolors.ENDC,
        "This script will setup everything you need to run the BeamBCI software.\n",
        "In order to do so, it will automatically download the MicroMamba Python distribution,\n",
        "install it locally in the folder and download all the necessary python packages to run the software.\n",
        "Furthermore, it will download the correct versions of the LabRecorder and LslViewer for your operating system.\n",
        "Both these applications are required by the BeamBCI software to record data and visualize data during the experiment.\n",
        "All these components are stored locally in the BeamBCI directory and will not be installed globally on\n"
        "your computer and do not modify your existing Python installation or environment.\n\n", sep=""
    )

    if input(bcolors.OKGREEN+"Do you want to continue?"+bcolors.ENDC+" [y/n]: ").strip() != "y":
        print("\n", bcolors.FAIL, "Cancelled.", bcolors.ENDC, "\n")
        sys.exit(0)

    # the socket timeout affects urllib, too, so we use socket's settimeout function to set it to a finite value
    socket.setdefaulttimeout(10)

    SETUP_DIR = pathlib.Path(os.path.split(os.path.abspath(__file__))[0])
    BEAMBCI_DIR = SETUP_DIR.parent
    TMP_DIR = SETUP_DIR / "TMP"
    TMP_DIR.mkdir(exist_ok=True)

    
    config_name, config = load_config()
    
    MICROMAMBA_DIR = BEAMBCI_DIR / "micromamba"

    LABRECORDER_DIR = BEAMBCI_DIR / "LabRecorder"
    LABRECORDER_EXTRACT_DIR = LABRECORDER_DIR / ("%s" % config_name)
    LABRECORDER_EXECUTABLE_CONFIG_FILE = LABRECORDER_DIR / "executable.toml"
   
    LSLVIEWER_DIR = BEAMBCI_DIR / "tools" / "lslviewer"
    LSLVIEWER_EXECUTABLE_TOML_PATH = LSLVIEWER_DIR / "executable.toml"
    

    print(bcolors.BOLD, bcolors.OKGREEN, "\n\nStep 1 of 4: Downloading MicroMamba and required python packages:\n"+bcolors.ENDC, sep="")
    time.sleep(1)

    setup_python_environment(config)
    # sys.exit(0)

    print(bcolors.BOLD, bcolors.OKGREEN, "\n\nStep 2 of 4: Downloading LabRecorder CLI:\n"+bcolors.ENDC, sep="")
    time.sleep(1)
    setup_labrecorder_cli(config)
    
    print(bcolors.BOLD, bcolors.OKGREEN, "\n\nStep 3 of 4: Downloading LslViewer:\n"+bcolors.ENDC, sep="")
    time.sleep(1)

    setup_lslviewer(config)

    print(bcolors.BOLD, bcolors.OKGREEN, "\n\nStep 4 of 4: Removing temporary files:\n"+bcolors.ENDC, sep="")
    time.sleep(1)

    shutil.rmtree(TMP_DIR)

    print(bcolors.BOLD, bcolors.OKGREEN, "\n\nBeamBCI setup completed.\n\n", bcolors.ENDC, sep="")

        
    
