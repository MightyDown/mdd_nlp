from pydantic import BaseModel


class NightAction(BaseModel):
    actor_id: str
    action_type: str  # "kill"
    target_id: str
    reasoning: str = ""


class Vote(BaseModel):
    voter_id: str
    target_id: str
    reason: str = ""


class Speech(BaseModel):
    player_id: str
    content: str
    round: int
