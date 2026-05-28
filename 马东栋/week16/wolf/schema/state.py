from enum import Enum
from pydantic import BaseModel, Field
from schema.player import Player


class Phase(str, Enum):
    NIGHT = "night"
    DAY_SPEECH = "day_speech"
    DAY_VOTE = "day_vote"
    ENDED = "ended"


class GameState(BaseModel):
    """对局状态。引擎内部使用，部分字段对 Agent 不可见。"""
    game_id: str
    players: list[Player]
    phase: Phase = Phase.NIGHT
    round: int = 0
    night_kill_target: str | None = None
    night_kill_protected: bool = False
    votes: dict[str, str] = Field(default_factory=dict)
    speeches: dict[str, str] = Field(default_factory=dict)
    vote_reasons: dict[str, str] = Field(default_factory=dict)
    history: list[dict] = Field(default_factory=list)
    winner: str | None = None
    eliminated_players: list[str] = Field(default_factory=list)
