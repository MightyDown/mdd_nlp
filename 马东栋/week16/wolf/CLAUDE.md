# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

狼人杀 AI 对局系统 — 基于多 Agent 协作框架，构建自主完成信息不对称博弈的狼人杀 Agent Team。首阶段实现最小可跑对局：Game Engine + 狼人 + 平民，完成夜晚→发言→投票→裁决的完整闭环。

## 技术选型

- **语言**: Python 3.12+ / asyncio
- **LLM 后端**: 阿里云 DashScope（qwen-flash 默认），兼容 OpenAI API 协议
- **类型安全**: Pydantic v2 — 所有核心结构定义在 `schema/`，全项目统一引用
- **日志**: JSONL 结构化日志，按 `games/{project_name}/{date}_{game_id}/` 输出

## 项目结构

```
wolf/
├── schema/                  # Pydantic 类型定义 + 配置（全项目类型基础）
│   ├── player.py            # Player, Role, Faction 枚举及映射表
│   ├── state.py             # GameState, Phase
│   ├── actions.py           # NightAction, Vote, Speech
│   ├── messages.py          # GameMessage, MessageType（含可见范围控制）
│   └── config.py            # Settings(BaseModel) + settings 单例
├── engine/                  # 对局引擎（纯逻辑，不依赖 LLM）
│   ├── state.py             # 状态管理器：创建/更新/信息隔离
│   ├── rules.py             # 纯函数：胜负判定、投票计票
│   └── game.py              # 主循环，回合流转，协调 Agent
├── agents/                  # Agent 实现
│   ├── base.py              # BaseAgent 抽象接口
│   ├── werewolf.py          # 狼人：夜间击杀 + 日间伪装
│   └── villager.py          # 村民：日间推理投票
├── llm/                     # LLM 接口层
│   ├── client.py            # OpenAI 兼容 API 封装（含 Mock 模式 + 重试）
│   └── prompts.py           # 按角色/阶段组织的 Prompt 模板
├── utils/                   # 工具函数
│   ├── id_gen.py            # 唯一 ID 生成
│   └── text.py              # 文本格式化
├── log/                     # 日志系统
│   └── logger.py            # JSONL 结构化日志
├── tests/
│   ├── test_engine.py       # 规则/状态单元测试
│   ├── test_agents.py       # Agent 单元测试
│   └── test_integration.py  # 集成测试
├── docs/
│   ├── architecture.md      # 架构说明
│   └── game-rules.md        # 规则定义
├── web/                     # 前端回放查看器（Vue 3 + Ant Design Vue）
│   └── src/
│       ├── components/      # GameLoader, GameViewer, PlayerPanel, PhaseDisplay
│       └── composables/     # useGameReplay — 解析 JSONL 重建对局时间线
├── projects/                # 实验配置（config.yaml 驱动）
├── leaderboard/             # 跨项目聚合排行榜
├── games/                   # 对局日志（运行时生成）
├── main.py                  # 统一后端入口
│                               #   python main.py            → 单局 AI 对局
│                               #   python main.py --demo     → Mock 对局（不消耗 API）
│                               #   python main.py --server   → WebSocket 服务器
├── config.py                # 兼容层：从 schema 转发 Settings
└── .env.example             # 环境变量模板
```

## 架构层次

```
┌──────────────────────────────────────────┐
│          main.py                          │  统一入口层
├──────────────────────────────────────────┤
│  engine/game.py                          │  编排层：主循环
│  engine/state.py  ←→  engine/rules.py   │
├──────────────────────────────────────────┤
│  agents/  ←→  llm/  ←→  utils/          │  智能体层
├──────────────────────────────────────────┤
│  schema/                                 │  类型基础层
│  ┌─────────────────────────────────────┐ │
│  │ config.py  player.py  state.py     │ │
│  │ actions.py  messages.py            │ │
│  └─────────────────────────────────────┘ │
├──────────────────────────────────────────┤
│  log/                                    │  可观测层
└──────────────────────────────────────────┘
```

## 信息隔离设计（核心约束）

三层信息隔离：

| 层级 | 机制 | 说明 |
|------|------|------|
| 引擎层 | `engine/state.py` → `get_visible_state()` | 根据 player_id 过滤 GameState 字段 |
| Prompt 层 | `llm/prompts.py` — 按角色组装不同 system prompt | 狼人知道同伴，村民只知道公开信息 |
| 校验层 | 发言后检测 | Agent 发言是否引用了不该知道的博弈信息 |

每个 Agent 只能通过 `receive_info()` 获取引擎分发的信息，绝不直接访问全局 GameState。

## 回合流转

```
夜晚(NIGHT) → 狼人选击杀目标
    → 天亮公告(DAY_ANNOUNCEMENT)
    → 发言(DAY_SPEECH) 所有存活玩家依次发言
    → 投票(DAY_VOTE) 所有存活玩家投票
    → 放逐(ELIMINATION)
    → 胜负检查 → NIGHT / ENDED
```

## 评测体系（三层）

| 层次 | 范围 | 方法 |
|------|------|------|
| 结果评测 | 宏观胜率、平均回合数 | 每配置 ≥30 局 |
| 过程评测 | 刀人效率、投票准确率、发言影响力、角色一致性 | 按角色维度打分 |
| 复盘归因 | 关键转折点定位（投票原因链、信息泄露检测） | 单局分析 |

Leaderboard: `leaderboard/{project_name}.json` — 含胜率、过程指标、对阵记录。

## 核心难点

1. **信息隔离完整性** — Prompt 层最容易泄露信息（如不慎在村民 prompt 中包含狼人身份）
2. **LLM 输出不稳定** — JSON 解析失败、虚构玩家 ID、拒绝对话 → 需要 schema 校验 + 重试 + fallback
3. **狼人夜间协调** — 两只狼独立选目标可能不一致 → 串行协调模式（狼1提议→狼2决定）
4. **发言有意义性** — Prompt 需强制要求引用具体发言 + 推理链 + 行动建议
5. **评测统计显著性** — 单局方差大，用 `main_demo.py` (Mock) 验流程，真实 API 小样本看趋势

## 常用命令

```bash
# Python 后端
pip install -r requirements.txt
python main.py                      # 单局 AI 对局
python main.py --demo               # Mock 对局（不消耗 API）
python main.py --server             # 启动 WebSocket 服务器（默认 ws://0.0.0.0:8765）
python main.py --server --port 9000 # 启动 WebSocket 服务器（指定端口）
pytest tests/ -v                    # 运行所有测试
pytest tests/test_engine.py -v      # 运行特定测试

# 前端回放查看器
cd web && npm install               # 安装前端依赖
cd web && npm run dev               # 启动开发服务器（localhost:5173）
cd web && npm run build             # 生产构建

# 实时对局模式（前端 + WebSocket 后端）
# 1. 先启动后端:
python main.py --server
# 2. 再启动前端:
cd web && npm run dev
# 3. 打开 http://localhost:5173 → 选择「即时对局」→ 连接 → 开始对局

## 配置方式

复制 `.env.example` 为 `.env`，填写 API key。所有配置通过 `schema/config.py` 的 `Settings` 类统一管理：

```python
from schema import settings
# settings.openai_api_key, settings.openai_model, settings.werewolf_count ...
```
