from __future__ import annotations
import os
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseModel):
    # ---- LLM ----
    openai_api_key: str = os.getenv("aliyunAPI_KEY", "")
    openai_base_url: str = os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    openai_model: str = os.getenv("OPENAI_MODEL", "qwen-flash")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "512"))
    llm_timeout: int = int(os.getenv("LLM_TIMEOUT", "30"))
    llm_max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "3"))

    # ---- 对局 ----
    total_players: int = int(os.getenv("TOTAL_PLAYERS", "6"))
    werewolf_count: int = int(os.getenv("WEREWOLF_COUNT", "2"))
    villager_count: int = int(os.getenv("VILLAGER_COUNT", "4"))
    max_rounds: int = int(os.getenv("MAX_ROUNDS", "20"))

    # ---- 日志 ----
    games_dir: str = os.getenv("GAMES_DIR", "games")


settings = Settings()
