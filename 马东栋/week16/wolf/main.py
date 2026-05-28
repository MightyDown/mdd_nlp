"""
Wolf 后端入口 — 支持单局对局和 WebSocket 实时服务器两种模式。

Usage:
  python main.py                        # 运行单局 AI 对局（真实 LLM）
  python main.py --demo                 # 运行单局 Mock 对局（不消耗 API）
  python main.py --server               # 启动 WebSocket 服务器（默认 ws://0.0.0.0:8765）
  python main.py --server --port 9000   # 启动 WebSocket 服务器（指定端口）
"""
from __future__ import annotations
import argparse
import asyncio
import importlib.util
import json
import os
import sys


def _load_agent(filename: str, classname: str):
    """加载 agents/ 目录下的 Agent 类。"""
    agents_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agents")
    spec = importlib.util.spec_from_file_location(
        classname.lower(), os.path.join(agents_dir, f"{filename}.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[classname.lower()] = mod
    spec.loader.exec_module(mod)
    return getattr(mod, classname)


WerewolfAgent = _load_agent("werewolf", "WerewolfAgent")
VillagerAgent = _load_agent("villager", "VillagerAgent")


# ---------------------------------------------------------------------------
# 单局对局模式
# ---------------------------------------------------------------------------

async def run_single_game(demo: bool = False):
    """运行单局 AI 对局，输出到控制台 + JSONL 日志。"""
    from schema import Role
    from schema.config import settings
    from utils import generate_game_id, generate_player_ids
    from engine import AgentProxy, run as run_game
    from log.logger import GameLogger

    game_id = generate_game_id()
    player_ids = generate_player_ids(settings.total_players)
    werewolf_ids = player_ids[:settings.werewolf_count]

    print(f"=== {'Mock' if demo else 'AI'} 对局 {game_id} ===")
    print(f"玩家: {player_ids}")
    print(f"狼人: {werewolf_ids}")

    log_dir = f"{settings.games_dir}/live/{game_id}"
    logger = GameLogger(log_dir)

    async def on_message(msg):
        logger.log_message(msg)

    agents = {}
    for pid in player_ids:
        agents[pid] = WerewolfAgent(pid) if pid in werewolf_ids else VillagerAgent(pid)

    proxies = {}
    for pid in player_ids:
        agent = agents[pid]
        is_wolf = agent.role == Role.WEREWOLF

        async def night_act(visible, alive, a=agent):
            return await a.night_act(visible, alive)

        async def speak(visible, a=agent):
            return await a.speak(visible)

        async def vote(visible, candidates, a=agent):
            return await a.vote(visible, candidates)

        proxies[pid] = AgentProxy(
            player_id=pid,
            on_night=night_act if is_wolf else None,
            on_speech=speak,
            on_vote=vote,
        )

    state = await run_game(game_id, proxies, player_ids, werewolf_ids, on_message)

    summary = {
        "game_id": game_id,
        "winner": state.winner,
        "rounds": state.round,
        "players": [{"id": p.id, "role": p.role.value, "alive": p.alive} for p in state.players],
        "eliminated": state.eliminated_players,
    }
    logger.log_summary(summary)

    print(f"\n对局结束: {state.winner} 获胜, 共 {state.round} 轮")
    print(f"日志: {log_dir}")


# ---------------------------------------------------------------------------
# WebSocket 服务器模式
# ---------------------------------------------------------------------------

async def _run_live_game(websocket, config: dict):
    """运行一场实时对局，所有游戏事件通过 WebSocket 推送给浏览器。"""
    from schema import Role
    from schema.config import settings
    from utils import generate_game_id, generate_player_ids
    from engine import AgentProxy, run as run_game

    total = config.get("total_players", settings.total_players)
    wolf_count = config.get("werewolf_count", settings.werewolf_count)
    project_name = config.get("project", "live")

    game_id = generate_game_id()
    player_ids = generate_player_ids(total)
    werewolf_ids = player_ids[:wolf_count]

    await websocket.send(json.dumps({
        "type": "game_started",
        "game_id": game_id,
        "players": [
            {"id": pid, "role": "werewolf" if pid in werewolf_ids else "villager"}
            for pid in player_ids
        ],
        "werewolf_ids": werewolf_ids,
        "project": project_name,
    }, ensure_ascii=False))

    async def on_message(msg):
        await websocket.send(json.dumps({
            "type": "game_message",
            "message": msg.model_dump(),
        }, ensure_ascii=False))

    agents = {}
    for pid in player_ids:
        agents[pid] = WerewolfAgent(pid) if pid in werewolf_ids else VillagerAgent(pid)

    proxies = {}
    for pid in player_ids:
        agent = agents[pid]
        is_wolf = agent.role == Role.WEREWOLF

        async def night_act(visible, alive, a=agent):
            await websocket.send(json.dumps({
                "type": "thinking",
                "player_id": a.player_id,
                "phase": "night",
            }, ensure_ascii=False))
            return await a.night_act(visible, alive)

        async def speak(visible, a=agent):
            await websocket.send(json.dumps({
                "type": "thinking",
                "player_id": a.player_id,
                "phase": "speech",
            }, ensure_ascii=False))
            return await a.speak(visible)

        async def vote(visible, candidates, a=agent):
            await websocket.send(json.dumps({
                "type": "thinking",
                "player_id": a.player_id,
                "phase": "vote",
            }, ensure_ascii=False))
            return await a.vote(visible, candidates)

        proxies[pid] = AgentProxy(
            player_id=pid,
            on_night=night_act if is_wolf else None,
            on_speech=speak,
            on_vote=vote,
        )

    state = await run_game(game_id, proxies, player_ids, werewolf_ids, on_message)

    await websocket.send(json.dumps({
        "type": "game_over",
        "summary": {
            "game_id": game_id,
            "winner": state.winner,
            "rounds": state.round,
            "players": [
                {"id": p.id, "role": p.role.value, "alive": p.alive}
                for p in state.players
            ],
            "eliminated": state.eliminated_players,
        },
    }, ensure_ascii=False))


async def _ws_handler(websocket):
    """处理单个 WebSocket 客户端连接。"""
    import websockets

    print(f"[server] client connected")
    try:
        async for raw in websocket:
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            if msg_type == "start_game":
                config = msg.get("config", {})
                print(f"[server] starting game: {config}")
                await _run_live_game(websocket, config)

            elif msg_type == "ping":
                await websocket.send(json.dumps({"type": "pong"}))

    except websockets.exceptions.ConnectionClosed:
        print("[server] client disconnected")
    except Exception as e:
        print(f"[server] error: {e}")
        try:
            await websocket.send(json.dumps({"type": "error", "message": str(e)}))
        except Exception:
            pass


async def run_server(port: int = 8765):
    """启动 WebSocket 服务器。"""
    import websockets
    from websockets.asyncio.server import serve

    print(f"[server] Wolf WebSocket server starting on ws://0.0.0.0:{port}")
    async with serve(_ws_handler, "0.0.0.0", port) as srv:
        await srv.serve_forever()


# ---------------------------------------------------------------------------
# 入口
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Wolf 狼人杀 AI 对局系统",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--server", action="store_true",
        help="启动 WebSocket 服务器模式",
    )
    parser.add_argument(
        "--port", type=int, default=8765,
        help="WebSocket 服务器端口 (默认 8765)",
    )
    parser.add_argument(
        "--demo", action="store_true",
        help="单局模式使用 Mock LLM（不消耗 API）",
    )

    args = parser.parse_args()

    if args.server:
        asyncio.run(run_server(port=args.port))
    elif args.demo:
        # Mock 模式通过环境变量切换
        os.environ["MOCK_LLM"] = "1"
        asyncio.run(run_single_game(demo=True))
    else:
        asyncio.run(run_single_game())


if __name__ == "__main__":
    main()
