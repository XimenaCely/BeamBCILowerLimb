from time import sleep
from typing import cast, Any, List, Dict, Optional, Type
from importlib import import_module
from multiprocessing import Pipe, Process

from modules.module import AbstractModule

from modules.ModuleProcess import ModuleProcess, WrappedModule
from modules.ModuleOrchestrator import ModuleProcessProtocol

from misc.log2 import getLogger
from modules.types import ModuleConfig, ModuleRequest, ModuleRequestType, ModuleResponse, ModuleResponseStatus, ModuleStatus

class ModuleProcessModuleWrapper(AbstractModule):

    def __init__(self, module_class_name: str, module_path: str, module_type: str = "misc"):
       
        self.module_class_name = module_class_name
        self.module_path = module_path

        self.module_config = ModuleConfig(
            class_name=module_class_name,
            path=module_path,
            type=module_type,
            params={}
        )

        module = self._import_module(module_class_name, module_path)
        self.MODULE_NAME = module.MODULE_NAME
        self.MODULE_DESCRIPTION = module.MODULE_DESCRIPTION
        self.PARAMETER_DEFINITION = module.PARAMETER_DEFINITION

        self.logger = getLogger(__name__)

        self._start_and_connect_process()

        self._load_module()

    @property
    def wrapped_module(self) -> WrappedModule:
        return WrappedModule(self.module_config.class_name, self.process, self.conn)
    
    def _import_module(self, module_class_name: str, module_path: str) -> Optional[Type]:
        try:
            module_import = import_module(module_path)
            module = getattr(module_import, module_class_name)
            return module
        except ImportError as e:
            self.logger.info(f"Module import failed: {e}")
        except AttributeError as e:
            self.logger.info(f"Class not found in module: {e}")

    def _start_and_connect_process(self):  
        module_process = ModuleProcess()
        self.conn, child_conn = Pipe()
        self.process = Process(target=module_process.connect, args=(child_conn,), daemon=True)
        
        try:
            self.process.start()
            child_conn.close()  # need the child connection only in the ModuleProcess process
            self.logger.success(f"Wrapper process for {self.module_class_name} started.")
        
        except Exception as e:
            self.logger.error(f"Failed to start wrapper process for {self.module_class_name}: {e}")
            return

    def _load_module(self):
        ModuleProcessProtocol.forward_request(
            {
                "type": ModuleRequestType.LOAD_MODULE,
                "body": self.module_config
            },
            self.wrapped_module,
            self.logger
        )
        ModuleProcessProtocol.receive_response(
            self.wrapped_module,
            self.logger
        )

    def _send_request(self, request: Dict[str, Any]) -> ModuleResponse:
        return ModuleProcessProtocol.forward_request(
            request, self.wrapped_module, self.logger
        )

    def _recv_response(self) -> ModuleResponse:
        return ModuleProcessProtocol.receive_response(
            self.wrapped_module, self.logger
        )

    def _send_and_recv(self, request: Dict[str, Any]) -> ModuleResponse:
        send_response = self._send_request(request)
        if send_response.status is ModuleResponseStatus.OK:
            return self._recv_response()
        else:
            return send_response

    def _terminate_process(self):
        
        """ Gracefully stops the module and shuts down the process. """

        self.stop()

        re = self._send_and_recv({
            "type": ModuleRequestType.STOP
        })
        self.logger.info(f"STOP RESPONSE: {re}")

        self.process.join()

        self.logger.info(f"STOPPED")
        
    def _kill_process(self):

        """ Forcefully terminates the module and its process. """
        self.process.kill()

    def get_name(self) -> str:
        return self.MODULE_NAME

    def get_description(self) -> str:
        return self.MODULE_DESCRIPTION

    def get_parameter_definition(self) -> list:
        return self.PARAMETER_DEFINITION

    def start(self):
        self._send_and_recv({
            "type": ModuleRequestType.START_MODULE
        })

    def stop(self):
        self._send_and_recv({
            "type": ModuleRequestType.STOP_MODULE
        })

    def restart(self):
        self.stop()
        sleep(0.2)
        self.start()
        
    def get_available_parameters(self) -> List[str]:
        raise NotImplementedError

    def get_parameter_value(self, key: str) -> Any:
        raise NotImplementedError

    def set_parameter_value(self, key: str, value) -> bool:
        raise NotImplementedError

    def get_state(self) -> ModuleStatus:
        response = self._send_and_recv({
            "type": ModuleRequestType.GET_STATUS
        })
        if response.is_ok:
            return cast(ModuleStatus, response.body)
        
        return ModuleStatus.UNKNOWN
        
