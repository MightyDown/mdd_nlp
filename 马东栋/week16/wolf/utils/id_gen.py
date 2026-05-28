from __future__ import annotations
import uuid
from datetime import datetime


def generate_game_id() -> str:
    return f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"


def generate_player_ids(count: int = 6) -> list[str]:
    return [f"p{i}" for i in range(1, count + 1)]
