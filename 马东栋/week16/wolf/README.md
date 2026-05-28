# WOLF — 狼人杀 AI 对局系统

基于多 Agent 协作框架的狼人杀博弈系统。Game Engine 调度狼人与村民 Agent，在信息不对称下自主完成夜晚击杀、白天发言、投票放逐的完整博弈闭环。配备 Web 前端实时观战与对局回放。

## 项目结构

```
wolf/
├── main.py                  # 统一后端入口
├── schema/                  # Pydantic 类型定义 + 配置
├── engine/                  # 对局引擎（纯逻辑，不依赖 LLM）
├── agents/                  # Agent 实现（狼人 / 村民）
├── llm/                     # LLM 接口层（OpenAI 兼容协议）
├── utils/                   # 工具函数
├── log/                     # JSONL 结构化日志
├── tests/                   # 单元测试 + 集成测试
├── web/                     # 前端观战/回放（Vue 3 + Ant Design Vue）
├── games/                   # 对局日志（运行时生成）
├── projects/                # 实验配置（config.yaml 驱动）
└── leaderboard/             # 跨项目聚合排行榜
```

## 快速开始

### 环境要求

- Python 3.12+
- Node.js 18+

### 1. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，填入 LLM API 密钥（兼容 OpenAI 协议，支持阿里云 DashScope 等）：

```env
OPENAI_API_KEY=sk-your-key
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-flash
```

### 2. 安装后端依赖

```bash
pip install -r requirements.txt
```

### 3. 运行

```bash
# 单局对局（真实 LLM）
python main.py

# Mock 对局（不消耗 API，快速验证流程）
python main.py --demo

# 启动 WebSocket 服务器（配合前端实时观战）
python main.py --server
python main.py --server --port 9000   # 指定端口
```

### 4. 启动前端观战页面

```bash
cd web && npm install
npm run dev
```

打开浏览器访问 `http://localhost:5173`：

- **即时对局**: 连接到后端 WebSocket（`ws://localhost:8765`），实时观看 AI 博弈
- **对局回放**: 加载本地 JSONL 日志文件，逐回合复盘

### 实时对局完整流程

```bash
# 终端 1：启动后端 WebSocket 服务
python main.py --server

# 终端 2：启动前端开发服务器
cd web && npm run dev
```

浏览器打开 `http://localhost:5173` → 选择「即时对局」→ 点击连接 → 开始对局。

## 评测

```bash
# 运行全部测试
pytest tests/ -v

# 仅运行引擎测试
pytest tests/test_engine.py -v
```

## 配置项

所有配置通过 `schema/config.py` 统一管理，由 `.env` 文件驱动：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `OPENAI_API_KEY` | LLM API 密钥 | - |
| `OPENAI_BASE_URL` | API 端点 | `https://api.openai.com/v1` |
| `OPENAI_MODEL` | 模型名称 | `gpt-4o` |
| `TOTAL_PLAYERS` | 总玩家数 | `6` |
| `WEREWOLF_COUNT` | 狼人数量 | `2` |
| `LLM_TEMPERATURE` | 生成温度 | `0.7` |
| `LLM_MAX_TOKENS` | 最大 Token | `512` |

## 技术栈

| 层 | 技术 |
|----|------|
| 语言 | Python 3.12+ / asyncio |
| LLM | 阿里云 DashScope（兼容 OpenAI 协议） |
| 类型 | Pydantic v2 |
| 日志 | JSONL 结构化日志 |
| 前端 | Vue 3 + Ant Design Vue + Vite |
| 通信 | WebSocket（实时对局推送） |
| 测试 | pytest + pytest-asyncio |
