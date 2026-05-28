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
from llm.prompts import build_speech_prompt, build_vote_prompt


_VILLAGER_INSTRUCTIONS = f"""你是{ROLE_DISPLAY_NAME[Role.VILLAGER]}，属于好人阵营。
目标：{FACTION_GOAL[Faction.VILLAGER]}

规则：
- 你没有特殊能力，只能通过发言和投票找出狼人
- 仔细分析每位玩家的发言，寻找矛盾和不自然之处
- 狼人会很活跃但可能前后矛盾，注意观察投票一致性

策略：
- 发言要表达推理，引用具体玩家的发言
- 投票时要说出理由，不要跟风盲投
- 如某玩家发言含糊、回避质疑，很可能是狼人"""


class VillagerAgent:
    """村民 Agent — 参考 keywords.py 的 Agent(name, model, instructions) → run 模式。"""

    def __init__(self, player_id: str):
        self.player_id = player_id
        self.role = Role.VILLAGER
        self.agent = Agent(
            name="",
            model=config.settings.openai_model,
            instructions=_VILLAGER_INSTRUCTIONS,
        )

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
