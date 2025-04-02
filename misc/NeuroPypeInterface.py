#=============================================================================#
# Imports                                                                     #
#=============================================================================#

import requests
import pathlib
import subprocess
import time
import psutil
import time
import signal
import sys
import os
import globals

from typing import Union, Dict

NEUROPYPE_TICK_RATE: float = 25.0

#=============================================================================#
# Parameters                                                                  #
#=============================================================================#

# With the standard Windows installation, these should be fix.
NEUROPYPE_PATH = pathlib.Path('C:\\Intheon\\NeuroPype Academic Suite\\NeuroPype\\') 
ENGINE_START_PATH = NEUROPYPE_PATH / 'bin\\serve.cmd'
ENGINE_STOP_PATH = NEUROPYPE_PATH / 'bin\\stop.cmd'
ENGINE_EXE_PATH = NEUROPYPE_PATH / 'python\\pythonw.exe'

HOST = 'http://127.0.0.1:6937'
EXE_HOST = HOST + '/executions'

# defines, whether the app used for signal processing (e.g. NeuroPype) is available
SignalProcessingAppAvailable: bool = NEUROPYPE_PATH.exists()
NeuroPypeAvailable: bool = NEUROPYPE_PATH.exists()

#=============================================================================#
# Methods                                                                     #
#=============================================================================#

def neuropype_api_available(exe_host = EXE_HOST):
    # check whether NeuroPype API is available
    try:
        # try to connect to the API
        r = requests.get(EXE_HOST, timeout=3)
        c = r.status_code
        if c == 200:
            # Neuropype API is available if the request was successful
            return True
    except requests.exceptions.ConnectionError:
        pass

    return False


def neuropype_running(engine_exe_path = ENGINE_EXE_PATH):
    # Check if the Neuropype server is running

    running = False

    for p in psutil.process_iter():
        try:
            working_dir = str(p.as_dict(attrs=['cwd'])['cwd'])
            if pathlib.Path(working_dir, 'pythonw.exe') == engine_exe_path:
                running = True
                break
        except psutil.AccessDenied:
            pass

    return running


def close_neuropype(url, engine_stop_path = ENGINE_STOP_PATH):
    print("NeuroPype: Closing pipeline and server...")
    set_state(url, {'running': False, 'paused': True})
    requests.delete(url)
    subprocess.run(engine_stop_path)


def start_neuropype(engine_exe_path = ENGINE_EXE_PATH, engine_start_path = ENGINE_START_PATH):
    # Check if the Neuropype server is already running: if not start it.
    running = neuropype_running(engine_exe_path)

    if not running:
        print("NeuroPype: Starting NeuroPype server...")
        subprocess.run(str(engine_start_path))

    else:
        print("NeuroPype: NeuroPype server already running!")


def get_executions(exe_host = EXE_HOST):
    # Continue trying to query for running executions while
    # the Neuropype server is starting up.
    executions = []
    connected = False
    trys = 0

    while not connected and trys <= 10:
        try:
            executions = requests.get(exe_host).json()
            connected = True

        except (requests.exceptions.ConnectionError):
            # If the NeuroPype server hasn't yet started, retry at most 10x.
            trys += 1
            time.sleep(1)

    return executions


def load_pipeline(url, pipeline_path):
    print("NeuroPype: Loading pipeline {}...".format(pipeline_path))
    response = requests.post(url + '/actions/load',
                            json={'file': str(pipeline_path), 'what': 'graph'})
    response.raise_for_status()


# change any of these states: running, paused, completed, calibrating, needs_keepalive
def set_state(url: str, states: Dict[str, bool], exe_host: str = EXE_HOST):
    for state in states.items():
        requests.patch(url + '/state', json=dict([state])).json()


# creates a new execution with specified tickrate and log-level
def create_execution(tickrate: float = 25.0, loglevel: int = 20, exe_host: str = EXE_HOST):
    execution_id = int(requests.post(exe_host, json={'info': {'log_level': loglevel, 'tickrate': tickrate}}).json()['id'])
    return execution_id


# deletes an execution specified by its id
def delete_execution(execution_id: int, exe_host: str = EXE_HOST):
    url = exe_host + '/' + str(execution_id)
    requests.delete(url)


# deletes all existing get_executions
def delete_all_executions(exe_host: str = EXE_HOST):

    executions = get_executions(exe_host)
    for e in executions:
        delete_execution(e['id'], exe_host)


# sets an execution running
def run_execution(execution_id: int, exe_host: str = EXE_HOST):
    url = exe_host + '/' + str(execution_id)
    set_state(url, {'completed': False, 'running': True, 'paused': False})


# stops a running execution
def stop_execution(execution_id: int, exe_host: str = EXE_HOST):
    url = exe_host + '/' + str(execution_id)
    set_state(url, {'completed': False, 'running': False, 'paused': False})


# ends a running execution
def end_execution(execution_id: int, exe_host: str = EXE_HOST):
    url = exe_host + '/' + str(execution_id)
    set_state(url, {'completed': True, 'running': False, 'paused': False})


# loads a specified pipeline into the execution's graph
def load_execution_pipeline(execution_id: int, pipeline_path: Union[str, pathlib.Path], exe_host: str = EXE_HOST):
    url = exe_host + '/' + str(execution_id)
    load_pipeline(url, pipeline_path)


# returns a list of all the nodes in the pipelines graph
def get_execution_nodes(execution_id: int, exe_host: str = EXE_HOST):
    url = exe_host + '/' + str(execution_id) + '/graph/nodes'
    return requests.get(url).json()


# return a singe node out of the pipelines graph
def get_execution_node(execution_id: int, node_id: int, exe_host: str = EXE_HOST):
    url = exe_host + '/' + str(execution_id) + '/graph/nodes/' + str(node_id)
    node = requests.get(url)
    return node.json()


# retuns all fields of a nodes parameter as a dict
def get_execution_node_parameter(execution_id: int, node_id: int, parameter_id: str, exe_host: str = EXE_HOST):
    url = exe_host + '/' + str(execution_id) + '/graph/nodes/' + str(node_id) + '/parameters/' + parameter_id
    return requests.get(url).json()


# changes values of a nodes parameter
def update_execution_node_parameter(execution_id: int, node_id: int, parameter_id: str, data: dict, exe_host: str = EXE_HOST):
    url = exe_host + '/' + str(execution_id) + '/graph/nodes/' + str(node_id) + '/parameters/' + parameter_id
    return requests.patch(url, json=data).json()


def set_execution_node_parameter_value(execution_id: int, node_id: int, parameter_id: str, new_value: Union[str, list, bool, int, float], exe_host: str = EXE_HOST):
    param_node = get_execution_node_parameter(execution_id, node_id, parameter_id, exe_host)
    param_node['value'] = new_value
    update_execution_node_parameter(execution_id, node_id, parameter_id, param_node, exe_host)


# add an edge to the graph on the fly
def add_edge(execution_id: int, source_id: int, target_id: int,
             source_port: str = 'data', target_port: str = 'data',
             exe_host: str = EXE_HOST):
    url = exe_host + '/' + str(execution_id)
    new_edge = {'source_node': source_id, 'source_port': source_port,
                'target_node': target_id, 'target_port': target_port}
    return requests.post(url + '/graph/edges', json=new_edge).json()


# add a node to the graph on the fly
def add_node(execution_id: int, new_node: dict, exe_host: str = EXE_HOST):
    url = exe_host + '/' + str(execution_id)
    return requests.post(url + '/graph/nodes', json=new_node).json()


# delete a node on the fly
def delete_node(execution_id: int, node_id: int, exe_host: str = EXE_HOST):
    url = exe_host + '/' + str(execution_id)
    return requests.delete(url + '/graph/nodes/' + str(node_id)).json()


# return the logs of an execution
def get_execution_logs(execution_id: int, exe_host: str = EXE_HOST):
    url = exe_host + '/' + str(execution_id) + '/logs'
    return requests.get(url).json()
