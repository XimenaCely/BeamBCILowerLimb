from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ModuleStatus(Enum):
    DEFAULT = "default"
    RUNNING = "running"
    STARTING = "starting"
    STOPPED = "stopped"
    STOPPING = "stopping"
    UNKNOWN = "unknown"


class ModuleRequestType(Enum):
    STOP = "stop"
    START_MODULE = "start_module"
    STOP_MODULE = "stop_module"
    RESTART_MODULE = "restart_module"
    GET_CONFIG = "get_config"
    SET_CONFIG = "set_config"
    GET_STATUS = "get_status"
    GET_PARAMETER_DEFINITIONS = "get_parameter_definitions"
    GET_ALL_PARAMETERS = "get_all_parameters"
    GET_PARAMETER = "get_parameter"
    SET_PARAMETER = "set_parameter"
    LOAD_MODULE = "load_module"
    UNKNOWN = "unknown"


class ModuleResponseStatus(str, Enum):
    OK = "ok"
    STOPPED = "stopped"
    ERROR = "error"


class ModuleConfig(BaseModel):
    class_name: str
    path: str
    type: str
    params: Dict[str, Any]


class Config(BaseModel):
    modules: List[ModuleConfig]


class ModuleRequest(BaseModel):
    type: ModuleRequestType
    body: Optional[Any] = None


class ModuleResponse(BaseModel):
    status: ModuleResponseStatus
    body: Optional[Any] = None

    @property
    def is_ok(self):
        return self.status is ModuleResponseStatus.OK

    @staticmethod
    def OK(message: Optional[str] = None):
        return ModuleResponse(status=ModuleResponseStatus.OK, body={"message": message})

    @staticmethod
    def ERROR(error_message: str):
        return ModuleResponse(
            status=ModuleResponseStatus.ERROR, body={"message": error_message}
        )
