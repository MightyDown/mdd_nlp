"""Mock LLM 集成测试入口 — 不消耗 API，验证完整流程闭环。"""
from __future__ import annotations
import asyncio
import random
from schema import Role
from schema.config import settings
from utils import generate_game_id, generate_player_ids
from engine import AgentProxy, run as run_game
from log.logger import GameLogger


def _build_mock_proxies(player_ids, werewolf_ids):
    proxies = {}
    for pid in player_ids:
        role = Role.WEREWOLF if pid in werewolf_ids else Role.VILLAGER

        async def night(visible, alive, _pid=pid):
            non_wolf = [p for p in alive if p not in visible.get("werewolf_teammates", []) and p != _pid]
            target = random.choice(non_wolf) if non_wolf else alive[0]
            return {"actor_id": _pid, "action_type": "kill", "target_id": target, "reasoning": f"{_pid} 选择击杀 {target}"}

        async def speech(visible, _pid=pid):
            prev = visible.get("speeches", {})
            if not prev:
                return f"{_pid}: 第一轮发言，暂时没有线索，先观察大家。"
            last_pid = list(prev.keys())[-1]
            return f"{_pid}: 我对 {last_pid} 的发言有些疑问，需要进一步解释。"

        async def vote(visible, candidates, _pid=pid):
            target = random.choice([c for c in candidates if c != _pid])
            return {"voter_id": _pid, "target_id": target, "reason": f"{_pid} 投票给 {target}"}

        proxies[pid] = AgentProxy(
            player_id=pid,
            on_night=night if role == Role.WEREWOLF else None,
            on_speech=speech,
            on_vote=vote,
        )
    return proxies


async def main():
    game_id = generate_game_id()
    player_ids = generate_player_ids(settings.total_players)
    werewolf_ids = player_ids[:settings.werewolf_count]

    print(f"=== Mock 对局 {game_id} ===")
    print(f"玩家: {player_ids}")
    print(f"狼人: {werewolf_ids}")

    log_dir = f"{settings.games_dir}/demo/{game_id}"
    logger = GameLogger(log_dir)

    async def on_message(msg):
        logger.log_message(msg)

    proxies = _build_mock_proxies(player_ids, werewolf_ids)
    state = await run_game(game_id, proxies, player_ids, werewolf_ids, on_message)

    logger.log_summary({
        "game_id": game_id,
        "winner": state.winner,
        "rounds": state.round,
        "players": [{"id": p.id, "role": p.role.value, "alive": p.alive} for p in state.players],
        "eliminated": state.eliminated_players,
    })

    print(f"\n对局结束: {state.winner} 获胜, 共 {state.round} 轮")
    print(f"日志: {log_dir}")


if __name__ == "__main__":
    asyncio.run(main())
