from enum import Enum
from pydantic import BaseModel


class MessageType(str, Enum):
    NIGHT_START = "night_start"
    NIGHT_KILL_TARGET = "night_kill_target"
    DAY_ANNOUNCEMENT = "day_announcement"
    SPEECH = "speech"
    VOTE_RESULT = "vote_result"
    ELIMINATION = "elimination"
    GAME_OVER = "game_over"


class GameMessage(BaseModel):
    type: MessageType
    visible_to: list[str]
    content: dict
    round: int

    def is_visible_to(self, player_id: str) -> bool:
        return player_id in self.visible_to
