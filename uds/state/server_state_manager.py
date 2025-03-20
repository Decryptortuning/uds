# state/server_state_manager.py
from typing import Callable, List

class ServerStateManager:
    """
    Manages the server's current state and notifies observers on state changes.
    """
    def __init__(self, initial_state: AbstractServerState):
        self.current_state: AbstractServerState = initial_state
        self._observers: List[Callable[[AbstractServerState], None]] = []

    def add_observer(self, observer_fn: Callable[[AbstractServerState], None]) -> None:
        """
        Register an observer callback to be notified when state changes.
        """
        self._observers.append(observer_fn)

    def remove_observer(self, observer_fn: Callable[[AbstractServerState], None]) -> None:
        """
        Remove an observer from the notification list.
        """
        if observer_fn in self._observers:
            self._observers.remove(observer_fn)

    def set_state(self, new_state: AbstractServerState) -> None:
        """
        Transition to a new state and notify observers.
        """
        if self.current_state.state_id == new_state.state_id:
            return  # Avoid redundant state changes

        self.current_state.on_exit()
        self.current_state = new_state
        self.current_state.on_enter()

        for callback in self._observers:
            callback(new_state)

    def get_current_state(self) -> AbstractServerState:
        """
        Returns the current server state.
        """
        return self.current_state