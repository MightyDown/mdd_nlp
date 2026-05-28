from __future__ import annotations
from collections.abc import Callable, Awaitable
from schema.state import GameState, Phase
from schema.player import Player, Faction
from schema.actions import NightAction, Vote, Speech
from schema.messages import GameMessage, MessageType
from engine.state import (
    create_game, transition_phase, apply_kill, apply_day_death,
    apply_elimination, record_votes, record_speech, advance_round,
    get_visible_state, set_winner,
)
from engine.rules import check_win, tally_votes, get_alive_players, get_werewolves


OnNight = Callable[[dict, list[str]], Awaitable[dict | NightAction]]
OnSpeech = Callable[[dict], Awaitable[str]]
OnVote = Callable[[dict, list[str]], Awaitable[dict | Vote]]


def _to_night_action(raw: dict | NightAction) -> NightAction:
    if isinstance(raw, NightAction):
        return raw
    return NightAction(**raw)


def _to_vote(raw: dict | Vote) -> Vote:
    if isinstance(raw, Vote):
        return raw
    return Vote(**raw)


class AgentProxy:
    """引擎与 Agent 的中间层。包装各角色的异步方法，统一接口。"""
    def __init__(self, player_id: str, on_night: OnNight | None, on_speech: OnSpeech, on_vote: OnVote):
        self.player_id = player_id
        self._on_night = on_night
        self._on_speech = on_speech
        self._on_vote = on_vote

    async def night_act(self, visible: dict, alive: list[str]) -> NightAction | None:
        if self._on_night is None:
            return None
        raw = await self._on_night(visible, alive)
        if raw is None:
            return None
        return _to_night_action(raw)

    async def speak(self, visible: dict) -> str:
        return await self._on_speech(visible)

    async def vote(self, visible: dict, candidates: list[str]) -> Vote:
        return _to_vote(await self._on_vote(visible, candidates))


async def run(
    game_id: str,
    proxies: dict[str, AgentProxy],
    player_ids: list[str],
    werewolf_ids: list[str],
    on_message: Callable[[GameMessage], Awaitable[None]] | None = None,
) -> GameState:
    """主循环。返回终局 GameState。"""
    state = create_game(game_id, player_ids, werewolf_ids)

    while state.phase != Phase.ENDED:
        # ---- 夜晚 ----
        await _emit(on_message, GameMessage(
            type=MessageType.NIGHT_START,
            visible_to=[],
            content={"round": state.round},
            round=state.round,
        ))

        state = await _night_phase(state, proxies, on_message)

        if state.phase == Phase.ENDED:
            break

        # ---- 天亮公告 ----
        state, death_id = _resolve_day_announcement(state)
        await _emit(on_message, GameMessage(
            type=MessageType.DAY_ANNOUNCEMENT,
            visible_to=[p.id for p in state.players],
            content={"dead_player": death_id} if death_id else {"dead_player": None},
            round=state.round,
        ))

        if state.phase == Phase.ENDED:
            break

        # ---- 发言 ----
        state = transition_phase(state, Phase.DAY_SPEECH)
        state = await _speech_phase(state, proxies, on_message)

        # ---- 投票 ----
        state = transition_phase(state, Phase.DAY_VOTE)
        state = await _vote_phase(state, proxies, on_message)

        # ---- 放逐 ----
        state, eliminated = _resolve_votes(state)
        await _emit(on_message, GameMessage(
            type=MessageType.ELIMINATION,
            visible_to=[p.id for p in state.players],
            content={"eliminated": eliminated} if eliminated else {"eliminated": None},
            round=state.round,
        ))

        # ---- 胜负检查 ----
        winner = check_win(state)
        if winner:
            state = set_winner(state, winner)

        if state.phase != Phase.ENDED:
            state = advance_round(state)

    await _emit(on_message, GameMessage(
        type=MessageType.GAME_OVER,
        visible_to=[p.id for p in state.players],
        content={"winner": state.winner},
        round=state.round,
    ))

    return state


async def _night_phase(state, proxies, on_message) -> GameState:
    """狼人夜间击杀：狼1提议 → 狼2最终决定。"""
    werewolves = get_werewolves(state)
    alive_ids = [p.id for p in get_alive_players(state)]

    # 狼1 提议
    wolf1 = werewolves[0]
    visible = get_visible_state(state, wolf1.id)
    action = await proxies[wolf1.id].night_act(visible, alive_ids)

    if action is None:
        return state

    # 狼2 收到提议后决定
    if len(werewolves) >= 2:
        wolf2 = werewolves[1]
        visible = get_visible_state(state, wolf2.id)
        visible["teammate_proposal"] = {
            "target_id": action.target_id,
            "reasoning": action.reasoning,
        }
        action = await proxies[wolf2.id].night_act(visible, alive_ids)

    if action is None:
        return state

    state = apply_kill(state, action.target_id)

    await _emit(on_message, GameMessage(
        type=MessageType.NIGHT_KILL_TARGET,
        visible_to=[w.id for w in werewolves],
        content={"target_id": action.target_id, "reasoning": action.reasoning},
        round=state.round,
    ))

    return state


def _resolve_day_announcement(state) -> tuple[GameState, str | None]:
    """天亮后处理死亡。"""
    death_id = state.night_kill_target
    if death_id is None:
        return state, None

    state = apply_day_death(state)

    winner = check_win(state)
    if winner:
        state = set_winner(state, winner)

    return state, death_id


async def _speech_phase(state, proxies, on_message) -> GameState:
    """所有存活玩家依次发言。"""
    alive = get_alive_players(state)

    for player in alive:
        visible = get_visible_state(state, player.id)
        content = await proxies[player.id].speak(visible)
        state = record_speech(state, player.id, content)

        await _emit(on_message, GameMessage(
            type=MessageType.SPEECH,
            visible_to=[p.id for p in state.players],
            content={"player_id": player.id, "content": content},
            round=state.round,
        ))

    return state


async def _vote_phase(state, proxies, on_message) -> GameState:
    """所有存活玩家投票。"""
    alive = get_alive_players(state)
    candidates = [p.id for p in alive]
    votes: dict[str, str] = {}
    reasons: dict[str, str] = {}

    for player in alive:
        visible = get_visible_state(state, player.id)
        vote = await proxies[player.id].vote(visible, candidates)
        votes[player.id] = vote.target_id
        reasons[player.id] = vote.reason

    state = record_votes(state, votes, reasons)

    await _emit(on_message, GameMessage(
        type=MessageType.VOTE_RESULT,
        visible_to=[p.id for p in state.players],
        content={"votes": votes, "reasons": reasons},
        round=state.round,
    ))

    return state


def _resolve_votes(state) -> tuple[GameState, str | None]:
    """计票放逐。"""
    target_id = tally_votes(state)
    if target_id is None:
        return state, None

    state = apply_elimination(state, target_id)

    winner = check_win(state)
    if winner:
        state = set_winner(state, winner)

    return state, target_id


async def _emit(on_message, msg: GameMessage):
    if on_message:
        await on_message(msg)
