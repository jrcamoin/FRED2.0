"""Top-level robot coordinator shell."""

from dataclasses import dataclass

from .state import RobotState


@dataclass(slots=True)
class Robot:
    """Minimal state holder to be extended as hardware ports are introduced."""

    state: RobotState = RobotState.IDLE

    def set_state(self, state: RobotState) -> None:
        if not isinstance(state, RobotState):
            raise TypeError("state must be a RobotState")
        self.state = state
