"""Agent 层单元测试 — Mock Runner.run() 避免真实 API 调用。"""
from __future__ import annotations
import importlib.util
import sys
from unittest.mock import AsyncMock, patch
from dataclasses import dataclass


def _load_agent_class(filename, classname):
    """用 importlib 加载 agents/ 下的 Agent 类（agents/ 无 __init__.py）。"""
    spec = importlib.util.spec_from_file_location(classname.lower(), f"agents/{filename}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[classname.lower()] = mod
    spec.loader.exec_module(mod)
    return getattr(mod, classname)


WerewolfAgent = _load_agent_class("werewolf", "WerewolfAgent")
VillagerAgent = _load_agent_class("villager", "VillagerAgent")


@dataclass
class MockRunResult:
    final_output: str


def make_runner_mock(json_response: str):
    """创建 mock 函数，模拟 Runner.run() 返回指定 JSON 字符串。"""
    async def mock_run(agent, prompt):
        return MockRunResult(final_output=json_response)
    return mock_run


def _patch_runner(agent_instance, json_response: str):
    """给 agent 实例打补丁，让 Runner.run 返回指定结果。"""
    mock = make_runner_mock(json_response)
    patcher = patch("agents.Runner.run", side_effect=mock)
    patcher.start()
    return patcher


# ---- WerewolfAgent ----

class TestWerewolfAgent:
    async def test_night_act_parses_json(self):
        agent = WerewolfAgent("p1")
        patcher = _patch_runner(agent, '{"target_id": "p3", "reasoning": "test"}')
        result = await agent.night_act(
            {"werewolf_teammates": ["p2"], "alive_players": ["p1", "p2", "p3", "p4", "p5", "p6"]},
            ["p1", "p2", "p3", "p4", "p5", "p6"],
        )
        patcher.stop()
        assert result["actor_id"] == "p1"
        assert result["target_id"] == "p3"
        assert result["reasoning"] == "test"

    async def test_night_act_fallback_on_invalid_json(self):
        agent = WerewolfAgent("p1")
        patcher = _patch_runner(agent, "not json!!!")
        result = await agent.night_act(
            {"werewolf_teammates": ["p2"], "alive_players": ["p1", "p2", "p3", "p4", "p5", "p6"]},
            ["p1", "p2", "p3", "p4", "p5", "p6"],
        )
        patcher.stop()
        assert result["target_id"] in ["p3", "p4", "p5", "p6"]

    async def test_night_act_fallback_on_empty_target(self):
        agent = WerewolfAgent("p1")
        patcher = _patch_runner(agent, '{"target_id": "", "reasoning": ""}')
        result = await agent.night_act(
            {"werewolf_teammates": ["p2"], "alive_players": ["p1", "p2", "p3", "p4", "p5", "p6"]},
            ["p1", "p2", "p3", "p4", "p5", "p6"],
        )
        patcher.stop()
        assert result["target_id"] not in ["p1", "p2"]

    async def test_night_act_never_targets_self(self):
        agent = WerewolfAgent("p1")
        patcher = _patch_runner(agent, '{"target_id": "p1", "reasoning": ""}')
        result = await agent.night_act(
            {"werewolf_teammates": ["p2"], "alive_players": ["p1", "p2", "p3"]},
            ["p1", "p2", "p3"],
        )
        patcher.stop()
        assert result["target_id"] != "p1"

    async def test_speak_returns_text(self):
        agent = WerewolfAgent("p1")
        patcher = _patch_runner(agent, "我觉得p3很可疑")
        result = await agent.speak(
            {"my_role": "werewolf", "alive_players": ["p1", "p2", "p3", "p4", "p5", "p6"],
             "eliminated_players": [], "speeches": {}}
        )
        patcher.stop()
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_vote_parses_json(self):
        agent = WerewolfAgent("p1")
        patcher = _patch_runner(agent, '{"target_id": "p4", "reason": "发言矛盾"}')
        result = await agent.vote({}, ["p1", "p2", "p3", "p4", "p5", "p6"])
        patcher.stop()
        assert result["voter_id"] == "p1"
        assert result["target_id"] == "p4"

    async def test_vote_fallback(self):
        agent = WerewolfAgent("p1")
        patcher = _patch_runner(agent, "bad json")
        result = await agent.vote({}, ["p1", "p2", "p3"])
        patcher.stop()
        assert result["target_id"] in ["p1", "p2", "p3"]


# ---- VillagerAgent ----

class TestVillagerAgent:
    async def test_speak_returns_text(self):
        agent = VillagerAgent("p3")
        patcher = _patch_runner(agent, "我认为p1和p2很可疑")
        result = await agent.speak(
            {"my_role": "villager", "alive_players": ["p1", "p2", "p3", "p4", "p5", "p6"],
             "eliminated_players": [], "speeches": {}}
        )
        patcher.stop()
        assert isinstance(result, str)
        assert len(result) > 0

    async def test_vote_parses_json(self):
        agent = VillagerAgent("p3")
        patcher = _patch_runner(agent, '{"target_id": "p1", "reason": "发言可疑"}')
        result = await agent.vote({}, ["p1", "p2", "p3", "p4", "p5", "p6"])
        patcher.stop()
        assert result["voter_id"] == "p3"
        assert result["target_id"] == "p1"

    async def test_vote_fallback(self):
        agent = VillagerAgent("p3")
        patcher = _patch_runner(agent, "invalid json here")
        result = await agent.vote({}, ["p1", "p2", "p3"])
        patcher.stop()
        assert result["target_id"] in ["p1", "p2", "p3"]

    def test_no_night_action(self):
        agent = VillagerAgent("p3")
        assert not hasattr(agent, "night_act")
