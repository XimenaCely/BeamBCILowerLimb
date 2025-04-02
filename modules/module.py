import math
import time
from abc import ABC, abstractmethod
from enum import Enum
from threading import Thread, currentThread
from typing import Any, Callable, Dict, List, Optional, Union
from pylsl import resolve_streams

from misc import log
from misc.timing import clock
from modules.Parameter import Parameter
from modules.types import ModuleStatus

logger = log.getLogger("ModuleBaseClass")


class AbstractModule(ABC):

    @abstractmethod
    def get_name(self) -> str:
        pass

    @abstractmethod
    def get_description(self) -> str:
        pass

    @abstractmethod
    def get_parameter_definition(self) -> list:
        pass

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def restart(self):
        pass

    @abstractmethod
    def get_state(self) -> ModuleStatus:
        pass

    @abstractmethod
    def get_parameter_value(self, key: str) -> Any:
        pass

    @abstractmethod
    def set_parameter_value(self, key: str, value) -> bool:
        pass

    @abstractmethod
    def get_all_parameters(self) -> Dict[str, Any]:
        pass

    @abstractmethod
    def get_available_parameters(self) -> List[str]:
        pass

    def setParameters(self, config: Dict[str, Parameter]):
        for param_name in self.get_available_parameters():
            if param_name in config:
                self.set_parameter_value(param_name, config[param_name])


class Module(AbstractModule):
    # whether this is a runnable module or only a blueprint to create runnable module from by extension
    MODULE_RUNNABLE: bool = False

    MODULE_NAME: str = "ModuleBaseClass"
    MODULE_DESCRIPTION: str = "-"

    PARAMETER_DEFINITION: List[dict] = []

    REQUIRED_LSL_STREAMS: List[str] = []

    # reference classes Parameter and ModuleStatus here for compatibility reasons: definitions of these two
    # classes previously were located here under the names 'Status' and 'Parameter'
    Status = ModuleStatus
    Parameter = Parameter

    def __init__(self):

        self.state: ModuleStatus = ModuleStatus.DEFAULT
        self.parameters: Dict[str, Module.Parameter] = {}
        self.running_since: float = clock()

        # initiate parameters
        for p in self.PARAMETER_DEFINITION:
            self.parameters[p["name"]] = Module.Parameter(
                p["name"],
                p["displayname"],
                p["type"],
                p["default"],
                p["unit"],
                p["description"],
            )

        # observe required streams
        d = Thread(daemon=True, target=self.stopIfStreamMissingDaemon)
        d.start()

    def get_name(self) -> str:
        return self.MODULE_NAME

    def get_description(self) -> str:
        return self.MODULE_DESCRIPTION

    def get_parameter_definition(self) -> list:
        return self.PARAMETER_DEFINITION

    def start(self):
        pass

    def stop(self):
        pass

    def restart(self):
        pass

    def get_state(self):
        return self.state

    def set_state(self, status):

        self.state = status

        if status is Module.Status.RUNNING:
            self.running_since = clock()

    def get_available_parameters(self):
        return list(self.parameters.keys())

    def get_parameter_value(self, key: str) -> Optional[Parameter.TYPES]:
        try:
            return self.parameters[key].getValue()
        except KeyError:
            return None

    def set_parameter_value(self, key: str, val: Any) -> bool:

        # don't change parameters while the module is running
        if self.get_state() == Module.Status.RUNNING:
            return False

        # don't set any parameters that don't exist
        if not key in self.parameters.keys():
            return False

        # set value
        return self.parameters[key].setValue(val)

    def get_all_parameters(self) -> Dict[str, Any]:
        return {
            param: self.get_parameter_value(param) for param in self.parameters.keys()
        }

    # function to be run by a daemon which checks every few seconds whether a specified lsl stream
    # is available, else it stops the module
    def stopIfStreamMissingDaemon(self):
        while True:
            if (
                self.get_state() is Module.Status.RUNNING
                and len(self.REQUIRED_LSL_STREAMS) > 0
            ):
                if not self.lslStreamsAvailable(
                    self.REQUIRED_LSL_STREAMS, wait_time=2.0
                ):
                    if self.get_state() is Module.Status.RUNNING:
                        logger.error(
                            f"Stopping module {self.MODULE_NAME} because of missing LSL streams: {self.REQUIRED_LSL_STREAMS}"
                        )
                        self.stop()

            else:
                time.sleep(2)

            time.sleep(3)

    # checks whether lsl streams with given names are available
    def lslStreamsAvailable(self, stream_names: List[str], wait_time=1.0):

        streams = resolve_streams(wait_time=wait_time)
        names = list(map(lambda x: x.name(), streams))

        for name in stream_names:

            if not name in names:
                return False

        return True
