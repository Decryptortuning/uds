# state/abstract_server_state.py
from abc import ABC, abstractmethod
from enum import Enum
from typing import List

class ServerStateEnum(Enum):
    """
    Predefined server state identifiers for UDS diagnostic sessions. Placeholders for correct state logic.
    """
    DEFAULT_SESSION = 0x01
    EXTENDED_DIAGNOSTIC = 0x03
    PROGRAMMING_SESSION = 0x02
    SECURITY_ACCESS_GRANTED = 0x04
    SECURITY_ACCESS_DENIED = 0x05

class AbstractServerState(ABC):
    """
    Abstract base class representing a diagnostic server state.
    """
    def __init__(self, name: str, state_id: ServerStateEnum):
        self.name: str = name
        self.state_id: ServerStateEnum = state_id

    def on_enter(self) -> None:
        """
        Hook method called when entering this state.
        """
        pass

    def on_exit(self) -> None:
        """
        Hook method called when exiting this state.
        """
        pass

    @abstractmethod
    def allowed_services(self) -> List[int]:
        """
        Abstract method to list which UDS services are allowed in this state.
        """
        raise NotImplementedError("Subclasses must implement allowed_services()")

    def is_service_allowed(self, service_id: int) -> bool:
        """
        Checks if a given service is allowed in the current state.
        """
        return service_id in self.allowed_services()

