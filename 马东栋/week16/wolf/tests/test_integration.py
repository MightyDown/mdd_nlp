"""集成测试 — Mock Agent 验证完整对局流程。"""
from __future__ import annotations
import pytest
from schema.actions import Vote
from engine.game import AgentProxy, run as run_game


def _make_proxies(player_ids, werewolf_ids, *, kill_target="p3", wolf2_override=None):
    """构建 Mock AgentProxy。wolf2_override 用于测试狼人协调：狼2 可以覆盖狼1 的提议。"""
    proxies = {}
    for pid in player_ids:
        is_wolf = pid in werewolf_ids
        is_wolf2 = pid == werewolf_ids[1] if len(werewolf_ids) >= 2 else False

        async def night(visible, alive, _pid=pid, _o=wolf2_override, _w2=is_wolf2):
            if _w2 and _o and "teammate_proposal" in visible:
                return {"actor_id": _pid, "action_type": "kill", "target_id": _o, "reasoning": "override"}
            non_wolf = [p for p in alive if p not in visible.get("werewolf_teammates", []) and p != _pid]
            return {"actor_id": _pid, "action_type": "kill", "target_id": non_wolf[0] if non_wolf else alive[0], "reasoning": "mock"}

        async def speech(visible, _pid=pid):
            return f"{_pid}: mock speech"

        async def vote(visible, candidates, _pid=pid):
            target = [c for c in candidates if c != _pid][0]
            return {"voter_id": _pid, "target_id": target, "reason": "mock"}

        proxies[pid] = AgentProxy(
            player_id=pid,
            on_night=night if is_wolf else None,
            on_speech=speech,
            on_vote=vote,
        )
    return proxies


def _player_ids(n=6):
    return [f"p{i}" for i in range(1, n + 1)]


@pytest.mark.asyncio
async def test_full_game_completes():
    proxies = _make_proxies(_player_ids(6), ["p1", "p2"])
    state = await run_game("test1", proxies, _player_ids(6), ["p1", "p2"])
    assert state.winner is not None
    assert state.phase.value == "ended"
    assert state.round >= 1


@pytest.mark.asyncio
async def test_game_has_messages():
    messages = []
    async def collect(msg):
        messages.append(msg)
    proxies = _make_proxies(_player_ids(6), ["p1", "p2"])
    await run_game("test2", proxies, _player_ids(6), ["p1", "p2"], on_message=collect)
    assert len(messages) > 0
    assert any(m.type.value == "game_over" for m in messages)
    assert any(m.type.value == "speech" for m in messages)
    assert any(m.type.value == "night_kill_target" for m in messages)


@pytest.mark.asyncio
async def test_wolf2_overrides_wolf1():
    """狼2 否决狼1 的提议，改为杀 p4。"""
    proxies = _make_proxies(_player_ids(6), ["p1", "p2"], wolf2_override="p4")
    messages = []
    async def collect(msg):
        messages.append(msg)
    state = await run_game("test3", proxies, _player_ids(6), ["p1", "p2"], on_message=collect)

    kill_msg = next(m for m in messages if m.type.value == "night_kill_target")
    assert kill_msg.content["target_id"] == "p4"

    death_msg = next(m for m in messages if m.type.value == "day_announcement")
    assert death_msg.content["dead_player"] == "p4"


@pytest.mark.asyncio
async def test_tie_vote_no_elimination():
    """模拟平票场景：所有玩家投票对半，平票无人被放逐。"""
    async def split_vote(visible, candidates, _pid=None):
        # 前一半投 p1，后一半投 p2
        half = len(candidates) // 2
        idx = candidates.index(_pid) if _pid in candidates else 0
        target = candidates[0] if idx < half else candidates[1]
        return Vote(voter_id=_pid, target_id=target)

    player_ids = ["p1", "p2", "p3", "p4"]
    proxies = {}
    for pid in player_ids:
        is_wolf = pid in ["p1"]

        async def night(visible, alive, _pid=pid):
            non_wolf = [p for p in alive if p != _pid]
            return {"actor_id": _pid, "action_type": "kill", "target_id": non_wolf[0], "reasoning": ""}

        async def speech(visible, _pid=pid):
            return f"{_pid}: mock"

        async def vote(visible, candidates, _pid=pid):
            return await split_vote(visible, candidates, _pid=_pid)

        proxies[pid] = AgentProxy(
            player_id=pid,
            on_night=night if is_wolf else None,
            on_speech=speech,
            on_vote=vote,
        )

    state = await run_game("test4", proxies, player_ids, ["p1"])
    assert state.winner is not None


@pytest.mark.asyncio
async def test_night_no_kill_target():
    """狼人夜间不选目标（action 为 None）→ 无人死亡。"""
    player_ids = _player_ids(6)
    proxies = {}
    for pid in player_ids:
        is_wolf = pid in ["p1", "p2"]

        async def night(visible, alive, _pid=pid):
            return None  # 狼人不行动

        async def speech(visible, _pid=pid):
            return f"{_pid}: mock"

        async def vote(visible, candidates, _pid=pid):
            target = [c for c in candidates if c != _pid][0]
            return {"voter_id": _pid, "target_id": target, "reason": "mock"}

        proxies[pid] = AgentProxy(
            player_id=pid,
            on_night=night if is_wolf else None,
            on_speech=speech,
            on_vote=vote,
        )

    messages = []
    async def collect(msg):
        messages.append(msg)
    state = await run_game("test5", proxies, player_ids, ["p1", "p2"], on_message=collect)
    assert state.winner is not None
    # 第一天无人死亡
    day_msgs = [m for m in messages if m.type.value == "day_announcement"]
    assert day_msgs[0].content["dead_player"] is None
