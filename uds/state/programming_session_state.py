# state/programming_session_state.py
class ProgrammingSessionState(AbstractServerState):
    """
    Programming Session state (0x02).
    """
    def __init__(self):
        super().__init__(name="Programming Session", state_id=ServerStateEnum.PROGRAMMING_SESSION)
    
    def allowed_services(self) -> List[int]:
        return [0x10, 0x11, 0x34, 0x36, 0x37, 0x31]  # Example programming session service IDs

    def on_enter(self) -> None:
        print("Entering Programming Session: Security required for Flash Programming.")

    def on_exit(self) -> None:
        print("Exiting Programming Session")