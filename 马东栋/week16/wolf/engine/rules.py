from __future__ import annotations
from schema.state import GameState
from schema.player import Player, Faction


def check_win(state: GameState) -> str | None:
    """返回获胜阵营，无人获胜返回 None。"""
    alive = [p for p in state.players if p.alive]
    werewolves = [p for p in alive if p.faction == Faction.WEREWOLF]
    villagers = [p for p in alive if p.faction == Faction.VILLAGER]

    if len(werewolves) == 0:
        return Faction.VILLAGER.value
    if len(werewolves) >= len(villagers):
        return Faction.WEREWOLF.value
    return None


def tally_votes(state: GameState) -> str | None:
    """计票，返回得票最高的 player_id。平票返回 None。"""
    if not state.votes:
        return None

    count: dict[str, int] = {}
    for target_id in state.votes.values():
        count[target_id] = count.get(target_id, 0) + 1

    max_votes = max(count.values())
    top = [pid for pid, c in count.items() if c == max_votes]

    return top[0] if len(top) == 1 else None


def get_alive_players(state: GameState) -> list[Player]:
    return [p for p in state.players if p.alive]


def get_werewolves(state: GameState) -> list[Player]:
    return [p for p in state.players if p.faction == Faction.WEREWOLF and p.alive]
