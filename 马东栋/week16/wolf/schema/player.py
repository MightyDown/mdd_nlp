from enum import Enum
from pydantic import BaseModel


class Role(str, Enum):
    WEREWOLF = "werewolf"
    VILLAGER = "villager"


class Faction(str, Enum):
    WEREWOLF = "werewolf"
    VILLAGER = "villager"


ROLE_FACTION: dict[Role, Faction] = {
    Role.WEREWOLF: Faction.WEREWOLF,
    Role.VILLAGER: Faction.VILLAGER,
}

ROLE_DISPLAY_NAME: dict[Role, str] = {
    Role.WEREWOLF: "狼人",
    Role.VILLAGER: "村民",
}

FACTION_GOAL: dict[Faction, str] = {
    Faction.WEREWOLF: "消灭所有村民，使狼人数量 ≥ 存活村民数量",
    Faction.VILLAGER: "找出并放逐所有狼人",
}


class Player(BaseModel):
    id: str
    role: Role
    alive: bool = True

    @property
    def faction(self) -> Faction:
        return ROLE_FACTION[self.role]

    @property
    def display_name(self) -> str:
        return f"玩家{self.id.split('_')[-1]}"
