# state/extended_session_state.py
class ExtendedSessionState(AbstractServerState):
    """
    Extended Diagnostic Session state (0x03).
    """
    def __init__(self):
        super().__init__(name="Extended Session", state_id=ServerStateEnum.EXTENDED_DIAGNOSTIC)
    
    def allowed_services(self) -> List[int]:
        return [0x10, 0x11, 0x27, 0x3E, 0x31, 0x22, 0x2E]  # Example extended session service IDs

    def on_enter(self) -> None:
        print("Entering Extended Diagnostic Session")

    def on_exit(self) -> None:
        print("Exiting Extended Diagnostic Session")