from __future__ import annotations
from schema.player import Player, ROLE_DISPLAY_NAME


def players_to_str(players: list[Player]) -> str:
    """将玩家列表转为可读字符串，如 '玩家1(狼人), 玩家2(村民)'。"""
    items = [f"{p.display_name}({ROLE_DISPLAY_NAME[p.role]})" for p in players]
    return ", ".join(items)


def alive_players_to_str(players: list[Player]) -> str:
    """仅列出存活玩家，不含角色信息。"""
    alive = [p for p in players if p.alive]
    return ", ".join(p.display_name for p in alive)
