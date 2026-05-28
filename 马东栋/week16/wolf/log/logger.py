from __future__ import annotations
import json
from pathlib import Path
from schema.messages import GameMessage
from schema.state import GameState


class GameLogger:
    """结构化 JSONL 日志记录器。"""

    def __init__(self, log_dir: str):
        self.dir = Path(log_dir)
        self.dir.mkdir(parents=True, exist_ok=True)
        self._state_file = self.dir / "state.jsonl"
        self._msg_file = self.dir / "messages.jsonl"
        self._decision_file = self.dir / "decisions.jsonl"

    def log_state(self, state: GameState):
        """记录状态快照。"""
        record = {
            "round": state.round,
            "phase": state.phase.value,
            "alive": [p.id for p in state.players if p.alive],
            "eliminated": state.eliminated_players,
            "winner": state.winner,
        }
        self._append(self._state_file, record)

    def log_message(self, msg: GameMessage):
        """记录消息。"""
        self._append(self._msg_file, msg.model_dump())

    def log_decision(self, player_id: str, phase: str, prompt: str, output: str, parsed: dict):
        """记录 Agent 决策过程（含 LLM 原始响应）。"""
        self._append(self._decision_file, {
            "player_id": player_id,
            "phase": phase,
            "prompt": prompt,
            "raw_output": output,
            "parsed": parsed,
        })

    def log_summary(self, summary: dict):
        """写入对局总结。"""
        with open(self.dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _append(filepath: Path, record: dict):
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
