from __future__ import annotations
import json
import random

from openai import AsyncOpenAI
from agents import Agent, Runner
from agents import set_default_openai_client, set_default_openai_api, set_tracing_disabled

from schema import config

_client = AsyncOpenAI(
    api_key=config.settings.openai_api_key,
    base_url=config.settings.openai_base_url,
)
set_default_openai_client(_client)
set_default_openai_api("chat_completions")
set_tracing_disabled(True)

from schema.player import Role, Faction, ROLE_DISPLAY_NAME, FACTION_GOAL
from llm.prompts import build_night_prompt, build_speech_prompt, build_vote_prompt


_WEREWOLF_INSTRUCTIONS = f"""你是{ROLE_DISPLAY_NAME[Role.WEREWOLF]}，属于狼人阵营。
目标：{FACTION_GOAL[Faction.WEREWOLF]}

规则：
- 夜晚你可击杀一名玩家，你认识其他狼人同伴
- 白天你必须伪装成村民参与讨论和投票
- 发言不能暴露你或同伴的狼人身份
- 投票时引导村民互相猜忌

策略：
- 白天发言要装作分析线索，不要沉默
- 可适度质疑其他玩家，但不要太激进
- 投票时和同伴保持一致以增加票数压力
- 同伴被怀疑时适当辩护但不能太明显"""


class WerewolfAgent:
    """狼人 Agent — 参考 keywords.py 的 Agent(name, model, instructions) → run 模式。"""

    def __init__(self, player_id: str):
        self.player_id = player_id
        self.role = Role.WEREWOLF
        self.agent = Agent(
            name="",
            model=config.settings.openai_model,
            instructions=_WEREWOLF_INSTRUCTIONS,
        )

    async def night_act(self, visible: dict, alive: list[str]) -> dict:
        prompt = build_night_prompt(visible)
        output = await Runner.run(self.agent, prompt)
        text = output.final_output.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}

        target_id = data.get("target_id", "")
        if not target_id or target_id not in alive or target_id == self.player_id:
            non_wolf = [p for p in alive if p not in visible.get("werewolf_teammates", []) and p != self.player_id]
            target_id = random.choice(non_wolf) if non_wolf else alive[0]

        return {
            "actor_id": self.player_id,
            "action_type": "kill",
            "target_id": target_id,
            "reasoning": data.get("reasoning", ""),
        }

    async def speak(self, visible: dict) -> str:
        prompt = build_speech_prompt(visible)
        output = await Runner.run(self.agent, prompt)
        return output.final_output.strip()

    async def vote(self, visible: dict, candidates: list[str]) -> dict:
        prompt = build_vote_prompt(visible, candidates)
        output = await Runner.run(self.agent, prompt)
        text = output.final_output.strip()
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}

        target_id = data.get("target_id", "")
        if not target_id or target_id not in candidates:
            target_id = random.choice([c for c in candidates if c != self.player_id])

        return {
            "voter_id": self.player_id,
            "target_id": target_id,
            "reason": data.get("reason", ""),
        }
