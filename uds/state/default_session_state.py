# state/default_session_state.py
class DefaultSessionState(AbstractServerState):
    """
    Diagnostic Default Session state (0x01).
    """
    def __init__(self):
        super().__init__(name="Default Session", state_id=ServerStateEnum.DEFAULT_SESSION)
    
    def allowed_services(self) -> List[int]:
        return [0x10, 0x11, 0x3E, 0x22, 0x19]  # Example service IDs for default session

    def on_enter(self) -> None:
        print("Entering Default Session")

    def on_exit(self) -> None:
        print("Exiting Default Session")