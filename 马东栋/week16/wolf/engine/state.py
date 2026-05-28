from __future__ import annotations
from schema.state import GameState, Phase
from schema.player import Player, Role, Faction


def create_game(game_id: str, player_ids: list[str], werewolf_ids: list[str]) -> GameState:
    players = [
        Player(id=pid, role=Role.WEREWOLF if pid in werewolf_ids else Role.VILLAGER)
        for pid in player_ids
    ]
    return GameState(game_id=game_id, players=players, phase=Phase.NIGHT, round=1)


def transition_phase(state: GameState, new_phase: Phase) -> GameState:
    return state.model_copy(update={"phase": new_phase})


def apply_kill(state: GameState, target_id: str) -> GameState:
    """标记夜间击杀目标。不改变存活状态，等天亮公告时统一处理。"""
    return state.model_copy(update={"night_kill_target": target_id})


def apply_day_death(state: GameState) -> GameState:
    """天亮后，将夜间击杀目标的 alive 置为 False。"""
    if state.night_kill_target is None:
        return state

    players = [
        p.model_copy(update={"alive": False}) if p.id == state.night_kill_target else p
        for p in state.players
    ]
    eliminated = [*state.eliminated_players, state.night_kill_target]

    return state.model_copy(update={
        "players": players,
        "eliminated_players": eliminated,
        "night_kill_target": None,
    })


def apply_elimination(state: GameState, target_id: str) -> GameState:
    """投票放逐目标。"""
    players = [
        p.model_copy(update={"alive": False}) if p.id == target_id else p
        for p in state.players
    ]
    eliminated = [*state.eliminated_players, target_id]

    return state.model_copy(update={
        "players": players,
        "eliminated_players": eliminated,
        "votes": {},
        "vote_reasons": {},
    })


def record_votes(state: GameState, votes: dict[str, str], reasons: dict[str, str]) -> GameState:
    return state.model_copy(update={
        "votes": votes,
        "vote_reasons": reasons,
    })


def record_speech(state: GameState, player_id: str, content: str) -> GameState:
    speeches = {**state.speeches, player_id: content}
    return state.model_copy(update={"speeches": speeches})


def advance_round(state: GameState) -> GameState:
    return state.model_copy(update={
        "round": state.round + 1,
        "speeches": {},
        "votes": {},
        "vote_reasons": {},
    })


def get_visible_state(state: GameState, player_id: str) -> dict:
    """信息隔离核心：返回该玩家角色有权知晓的状态子集。"""
    player = next(p for p in state.players if p.id == player_id)
    base = {
        "game_id": state.game_id,
        "phase": state.phase.value,
        "round": state.round,
        "my_id": player_id,
        "my_role": player.role.value,
        "alive_players": [p.id for p in state.players if p.alive],
        "eliminated_players": state.eliminated_players,
        "history": state.history,
    }

    if player.faction == Faction.WEREWOLF:
        base["werewolf_teammates"] = [
            p.id for p in state.players
            if p.faction == Faction.WEREWOLF and p.id != player_id
        ]

    if state.phase == Phase.DAY_SPEECH or state.phase == Phase.DAY_VOTE:
        base["speeches"] = state.speeches

    return base


def set_winner(state: GameState, winner: str) -> GameState:
    return state.model_copy(update={"phase": Phase.ENDED, "winner": winner})
