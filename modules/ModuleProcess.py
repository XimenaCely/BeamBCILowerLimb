from dataclasses import dataclass
from importlib import import_module
from multiprocessing import Process
from multiprocessing.connection import Connection
from threading import Thread
from typing import cast, Dict, Optional, Type
import time

from pydantic import ValidationError

from misc import log
from misc.timing import clock
from modules.module import Module
from modules.types import (
    ModuleConfig,
    ModuleRequest,
    ModuleRequestType,
    ModuleResponse,
    ModuleResponseStatus,
)

type ModuleName = str
type ModuleType = str # TODO: make union

@dataclass
class WrappedModule:
    module_name: ModuleName
    type: ModuleType
    process: Process
    conn: Connection


class ModuleProcessProtocol:

    @staticmethod
    def forward_request(req: Dict, wrapped_module: WrappedModule, logger: log.BeamBciLogger) -> ModuleResponse:
        
        """Forward a request to the associated ModuleProcess."""
        
        if not wrapped_module:
            return ModuleResponse(
                status=ModuleResponseStatus.ERROR,
                body={"message": "Missing module. Aborting request."},
            )

        try:
            type = req["type"] if "type" in req else None
            body = req["body"] if "body" in req else None
            req_obj = ModuleRequest(type=cast(ModuleRequestType, type), body=body)
            logger.debug(f"Created ModuleRequest object: {req_obj}")
        except ValidationError:
            logger.error(
                f"Failed to create ModuleRequest object from {req}. Aborting."
            )
            return ModuleResponse(
                status=ModuleResponseStatus.ERROR, body={"message":"Invalid request format"}
            )

        logger.debug(
            f"Sending request {req_obj.type} to wrapped {wrapped_module.module_name}, containing: {req_obj.body}"
        )
        wrapped_module.conn.send(req_obj)

        # return ModuleProcessController.receive_response(wrapped_module, logger)
        return ModuleResponse(status=ModuleResponseStatus.OK)

    @staticmethod
    def receive_response(wrapped_module: WrappedModule, logger: log.BeamBciLogger) -> ModuleResponse:
        
        """Listen to the queue for incoming messages."""
        
        logger.debug(
            f"Listening for response from {wrapped_module.module_name}..."
        )
        try:
            res = wrapped_module.conn.recv()
            logger.debug(f"Received response: {res}")
            return res
        except EOFError:
            logger.error("Connection closed unexpectedly.")
            return ModuleResponse(
                status=ModuleResponseStatus.ERROR, body={"message": "Connection closed unexpectedly"}
            )


class ModuleProcessInterface:
    def start(self, module_config: Dict, conn: Connection) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def _listen_for_requests(self) -> None:
        raise NotImplementedError

    def _handle_request(self, req: Dict) -> None:
        raise NotImplementedError

    def _start_module(self, module_config: ModuleConfig) -> ModuleResponse:
        raise NotImplementedError

    def _stop_module(self) -> ModuleResponse:
        raise NotImplementedError

    def _restart_module(self, module_config: ModuleConfig) -> ModuleResponse:
        raise NotImplementedError

    def _get_status(self) -> ModuleResponse:
        raise NotImplementedError

    def _get_parameter_definitions(self) -> ModuleResponse:
        raise NotImplementedError

    def _get_all_parameters(self) -> ModuleResponse:
        raise NotImplementedError

    def _get_parameter(self, parameter_name: str) -> ModuleResponse:
        raise NotImplementedError

    def _set_parameter(self, parameter_name: str, value: str) -> ModuleResponse:
        raise NotImplementedError


class ModuleProcess(ModuleProcessInterface):
    """
    Wrapper class for a module.
    The ModuleWrapper will be started as a separate process by the ModuleOrchestrator.
    The actual module will be created and started by the ModuleWrapper after process start.
    This avoids transmission of non-pickable data.
    """

    def __init__(self):
        self.module_config: Optional[ModuleConfig] = None
        self.module: Optional[Module] = None
        self.conn: Optional[Connection] = None
        self.logger = None

        self.handlers = {
            ModuleRequestType.STOP: self.stop,
            ModuleRequestType.START_MODULE: self._start_module,
            ModuleRequestType.STOP_MODULE: self._stop_module,
            ModuleRequestType.RESTART_MODULE: self._restart_module,
            ModuleRequestType.GET_STATUS: self._get_module_status,
            ModuleRequestType.GET_PARAMETER_DEFINITIONS: self._get_parameter_definitions,
            ModuleRequestType.GET_ALL_PARAMETERS: self._get_all_parameters,
            ModuleRequestType.LOAD_MODULE: self.load_module
        }

    def connect(self, conn: Connection) -> bool:
        """
        Connect to the orchestrator and start listening for requests.
        At this point, there is no module yet.

        Args:
            conn (Connection): The connection to the orchestrator

        Returns:
            bool: True if the connection was successful, False otherwise
        """
        if self.conn is not None:
            self.logger.warning(
                f"Already connected to ModuleOrchestrator! Can only start once. Aborting.."
            )
            return False

        START_CLOCK = clock()
        log.initialize_logger(START_CLOCK, level=log.DEBUG)
        self.logger = log.getLogger(__name__)

        self.conn = conn
        listen_thread = Thread(target=self._listen_for_requests)
        listen_thread.start()
        return True

    def stop(self) -> ModuleResponse:
        """
        Stop and detach the module to prepare for termination.
        """
        self.logger.debug("Stopping and detaching module...")
        stop_response = self._stop_module()
        if stop_response.status == ModuleResponseStatus.OK:
            self.module = None
        else:
            self.logger.error("Failed to stop the module.")

        response = ModuleResponse(
            status=ModuleResponseStatus.STOPPED,
            body={"message": "Module stopped and detached successfully."},
        )
        return response

    def load_module(self, module_config: Optional[ModuleConfig] = None) -> ModuleResponse:
        
        if not self.module_config and not module_config:
            return ModuleResponse(
                status=ModuleResponseStatus.ERROR,
                body={"message": "Failed to load module: ModuleConfig missing."}
            )

        if module_config:
            try:
                self.module_config = ModuleConfig(**dict(module_config))
            except ValidationError:
                return ModuleResponse(
                    status=ModuleResponseStatus.ERROR,   
                    body={"message": "load_module failed: Invalid module config."}
                )

        if not self._initialize_module():
            return ModuleResponse(
                status=ModuleResponseStatus.ERROR,
                body={"message": f"load_module failed: Error in _initialize_module ({self.module_config.class_name})."}
            )
        
        return ModuleResponse.OK(f"Module loaded successfully: {self.module_config.class_name}")


    def _start_module(self, module_config: Optional[ModuleConfig] = None) -> ModuleResponse:
        """
        Start the module based on the configuration.
        """
        self.logger.debug(
            f"Starting module in ModuleWrapper with config {module_config}..."
        )

        if self.module is not None:
            module_status = self._get_module_status()["status"]
            if module_status == Module.Status.RUNNING:
                self.logger.warning(f"{self.module.MODULE_NAME} already running.")
                return ModuleResponse(
                    status=ModuleResponseStatus.ERROR,
                    body={"message": "Module already running."},
                )

            self.module.start()
            self.logger.success(f"Started {self.module.MODULE_NAME}.")
            return ModuleResponse(
                status=ModuleResponseStatus.OK,
                body={"message": "Module started successfully."},
            )

        if not module_config:
            self.logger.error("No module configuration provided.")
            return ModuleResponse(
                status=ModuleResponseStatus.ERROR,
                body={"message": "No module configuration provided."},
            )

        try:
            self.module_config = module_config
            self._initialize_module()
            self._configure_module(self.module_config)
            self.module.start()
            self.logger.success(f"Started {self.module.MODULE_NAME}.")
            return ModuleResponse(
                status=ModuleResponseStatus.OK,
                body={"message": "Module started successfully."},
            )
        except ValidationError as e:
            self.logger.error(f"Invalid module configuration: {e}")
            return ModuleResponse(
                status=ModuleResponseStatus.ERROR,
                body={"message": f"Invalid module configuration: {str(e)}"},
            )
        except Exception as e:
            self.logger.error(f"Failed to start the module: {e}")
            return ModuleResponse(
                status=ModuleResponseStatus.ERROR,
                body={"message": f"Failed to start the module: {str(e)}"},
            )

    def _stop_module(self) -> ModuleResponse:
        """
        Stop the running module.
        """
        self.logger.debug("Stopping module in ModuleWrapper...")

        if self.module is None:
            self.logger.warning("No module to stop.")
            return ModuleResponse(
                status=ModuleResponseStatus.ERROR, body={"message": "No module to stop."}
            )

        try:
            self.module.stop()
            self.logger.success(f"Stopped {self.module.MODULE_NAME}.")
            return ModuleResponse(
                status=ModuleResponseStatus.OK,
                body={"message": "Module stopped successfully."},
            )
        except Exception as e:
            self.logger.info(f"Failed to stop the module: {e}")
            return ModuleResponse(
                status=ModuleResponseStatus.ERROR,
                body={"message": "Failed to stop the module."},
            )

    def _restart_module(self, module_config: ModuleConfig) -> ModuleResponse:
        """
        Restart the module based on the configuration.
        """
        self.logger.debug(
            f"Restarting module in ModuleWrapper with config {module_config}..."
        )

        try:
            module_config = ModuleConfig(**module_config)
        except ValidationError as e:
            self.logger.error(f"Invalid module configuration: {e}")
            return ModuleResponse(
                status=ModuleResponseStatus.ERROR,
                body={"message": "Invalid module configuration."},
            )

        stop_response = self._stop_module()
        if stop_response.status != ModuleResponseStatus.OK:
            return stop_response

        return self._start_module(module_config)

    def _get_module_status(self) -> ModuleResponse:
        """
        Get the status of the module.
        """
        self.logger.debug("Getting status of module in ModuleWrapper...")
        try:
            status = self.module.get_state()
            lsl_available = self.module.lslStreamsAvailable(self.module.REQUIRED_LSL_STREAMS, wait_time=2.0)
            return ModuleResponse(
                status=ModuleResponseStatus.OK, body={"status": status, "lsl_available": lsl_available}
            )
        except Exception as e:
            self.logger.info(f"Failed to get status of the module: {e}")
            return ModuleResponse(status=ModuleResponseStatus.ERROR, body={"message": str(e)})

    def _get_parameter_definitions(self) -> ModuleResponse:
        """
        Get the parameter definitions of the module.
        """
        self.logger.debug("Getting parameter definitions of module in ModuleWrapper...")
        try:
            return ModuleResponse(
                status=ModuleResponseStatus.OK,
                body=self.module.get_parameter_definition(),
            )
        except Exception as e:
            self.logger.info(f"Failed to get parameter definitions of the module: {e}")
            return ModuleResponse(status=ModuleResponseStatus.ERROR, body={"message": str(e)})
        
    def _get_all_parameters(self) -> ModuleResponse:
        """
        Get all parameters of the module.
        """
        self.logger.debug("Getting all parameter values of module in ModuleWrapper...")
        try:
            return ModuleResponse(
                status=ModuleResponseStatus.OK, body=self.module.get_all_parameters()
            )
        except Exception as e:
            self.logger.info(f"Failed to get all parameters of the module: {e}")
            return ModuleResponse(status=ModuleResponseStatus.ERROR, body={"message": str(e)})

    def _initialize_module(self) -> bool:
        """
        Dynamically import and instantiate the module.
        """
        module_path, module_class_name = (
            self.module_config.path,
            self.module_config.class_name,
        )
        module = self._import_module(module_class_name, module_path)

        if module:
            self.module = module()
            return True
        else:
            self.logger.warn(f"Module {module_class_name} could not be initialized.")

        return False
    
    def _import_module(self, module_class_name: str, module_path: str) -> Optional[Type]:
        try:
            module_import = import_module(module_path)
            module = getattr(module_import, module_class_name)
            return module
        except ImportError as e:
            self.logger.info(f"Module import failed: {e}")
        except AttributeError as e:
            self.logger.info(f"Class not found in module: {e}")

    def _configure_module(self, module_config: ModuleConfig) -> None:
        """Configure the module with the provided parameters."""
        module_params = module_config.params
        self.logger.info(f"Setting module parameters: {module_params}")
        try:
            self.module.setParameters(module_params)
        except Exception as e:
            self.logger.info(f"Failed to set module parameters: {e}")

    def _listen_for_requests(self) -> None:
        """Listen to the IPC connection for incoming requests."""
        while True:
            self.logger.debug(f"Listening for requests...")
            try:
                req: ModuleRequest = self.conn.recv()
                self.logger.debug(f"Received request: {req}")
                self._handle_request(req)
                if req.type == ModuleRequestType.STOP:
                    self.conn.close()
                    self.conn = None
                    break
            except EOFError:
                self.logger.error("Connection closed.")
                break

    def _handle_request(self, req: ModuleRequest) -> None:
        """Handle a request received via IPC connection."""
        response = self._process_request(req)
        self.conn.send(response)

    def _process_request(self, req: ModuleRequest) -> ModuleResponse:
        """Process the incoming request and return the response."""
        handler = self.handlers.get(req.type)
        if handler:
            return handler(req.body) if req.body else handler()
        else:
            return ModuleResponse(
                status=ModuleResponseStatus.ERROR,
                body={"message": f"Unknown command type: {req.type}"},
            )
            
