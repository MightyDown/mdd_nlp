"""Mock Agent — 用于 main_demo.py 集成测试，不消耗 API。"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class MockResult:
    final_output: str


class MockAgent:
    def __init__(self, name: str = "", model: str = "", instructions: str = ""):
        self.name = name
        self.model = model
        self.instructions = instructions

    async def run(self, prompt: str) -> MockResult:
        return MockResult(final_output='{"target_id": "", "reasoning": ""}')
