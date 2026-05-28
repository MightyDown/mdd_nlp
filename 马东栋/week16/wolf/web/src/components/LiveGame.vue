<template>
  <div class="live-game">
    <!-- Pre-game: Connection + Config -->
    <div v-if="!gameStarted" class="live-setup">
      <div class="setup-card">
        <h2 class="setup-title">即时对局</h2>
        <div class="setup-divider"><span></span></div>

        <!-- Connection -->
        <div class="setup-section">
          <h4>服务器连接</h4>
          <div class="conn-row">
            <a-input
              v-model:value="host"
              placeholder="localhost"
              size="large"
              :disabled="connected"
              class="host-input"
            />
            <span class="conn-sep">:</span>
            <a-input
              v-model:value="port"
              placeholder="8765"
              size="large"
              :disabled="connected"
              class="port-input"
            />
            <a-button
              v-if="!connected"
              type="primary"
              :loading="connecting"
              @click="doConnect"
              size="large"
              class="conn-btn"
            >
              连接
            </a-button>
            <a-button v-else type="default" @click="disconnect" size="large" class="conn-btn connected">
              已连接 <CheckCircleOutlined />
            </a-button>
          </div>
          <a-alert v-if="error" :message="error" type="error" show-icon closable class="setup-alert" />
        </div>

        <!-- Config -->
        <div class="setup-section" v-if="connected">
          <h4>对局配置</h4>
          <div class="config-grid">
            <div class="config-item">
              <label>总玩家数</label>
              <a-input-number v-model:value="totalPlayers" :min="4" :max="12" size="large" />
            </div>
            <div class="config-item">
              <label>狼人数量</label>
              <a-input-number v-model:value="werewolfCount" :min="1" :max="4" size="large" />
            </div>
          </div>
          <a-button
            type="primary"
            size="large"
            :disabled="!connected"
            @click="doStartGame"
            class="start-btn"
          >
            <ThunderboltOutlined /> 开始对局
          </a-button>
        </div>
      </div>
    </div>

    <!-- Live Game Viewer -->
    <div v-else class="live-viewer">
      <!-- Top Bar -->
      <div class="top-bar">
        <div class="top-left">
          <button class="back-btn" @click="handleLeave">
            <ArrowLeftOutlined /> 离开
          </button>
          <span class="game-id">{{ gameId }}</span>
        </div>
        <div class="top-center">
          <!-- Thinking Indicator -->
          <div v-if="thinking" class="thinking-badge">
            <span class="thinking-dot"></span>
            {{ getPlayerName(thinking.player_id) }} 正在思考...
          </div>
          <!-- Winner Badge -->
          <span v-else-if="winner" class="winner-badge" :class="winner">
            <TrophyOutlined />
            {{ winner === 'werewolf' ? '狼人获胜' : '村民获胜' }}
          </span>
        </div>
        <div class="top-right">
          <a-statistic
            title="当前回合"
            :value="currentRound"
            :suffix="gameEnded ? ' (终局)' : ''"
            class="round-stat"
          />
        </div>
      </div>

      <!-- Body -->
      <div class="viewer-body">
        <aside class="player-sidebar">
          <LivePlayerPanel :players="livePlayers" :thinking="thinking" />
        </aside>
        <main class="phase-main">
          <PhaseDisplay
            v-if="currentFrameData"
            :frame="currentFrameData"
            :playerStates="playerStatesMap"
            :currentFrame="currentFrame"
            :key="currentFrame"
          />
          <a-empty v-else description="等待对局开始..." class="empty-state" />
        </main>
      </div>

      <!-- Control Bar -->
      <div class="control-bar">
        <div class="control-left">
          <a-button-group>
            <a-button :disabled="currentFrame <= 0" @click="prevFrame()">
              <StepBackwardOutlined />
            </a-button>
            <a-button :disabled="currentFrame >= totalFrames - 1" @click="nextFrame()">
              <StepForwardOutlined />
            </a-button>
          </a-button-group>
          <a-switch
            v-model:checked="autoScroll"
            checked-children="自动"
            un-children="手动"
            class="auto-switch"
          />
        </div>

        <div class="control-center">
          <div class="frame-dots">
            <button
              v-for="(f, i) in frames"
              :key="i"
              :class="['frame-dot', { active: i === currentFrame, seen: i < currentFrame }]"
              @click="goToFrame(i)"
            >
              R{{ f.round }}
            </button>
          </div>
        </div>

        <div class="control-right">
          <a-slider
            :min="0"
            :max="Math.max(totalFrames - 1, 0)"
            :value="currentFrame"
            @change="goToFrame($event)"
            :tooltip="{ formatter: (v) => `第 ${frames[v]?.round ?? '?'} 回合` }"
            class="frame-slider"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import {
  ArrowLeftOutlined,
  TrophyOutlined,
  StepBackwardOutlined,
  StepForwardOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons-vue'
import { message } from 'ant-design-vue'
import { useLiveGame } from '../composables/useLiveGame.js'
import PhaseDisplay from './PhaseDisplay.vue'
import LivePlayerPanel from './LivePlayerPanel.vue'

const emit = defineEmits(['back'])

const {
  connected,
  connecting,
  error,
  gameId,
  gameStarted,
  gameEnded,
  summary,
  players,
  werewolfIds,
  frames,
  currentFrame,
  totalFrames,
  deadPlayers,
  thinking,
  winner,
  connect,
  startGame,
  disconnect,
  goToFrame,
  prevFrame,
  nextFrame,
} = useLiveGame()

const host = ref('localhost')
const port = ref(8765)
const totalPlayers = ref(6)
const werewolfCount = ref(2)
const autoScroll = ref(true)

const currentRound = computed(() => frames.value[currentFrame.value]?.round ?? 0)
const currentFrameData = computed(() => frames.value[currentFrame.value] ?? null)

const livePlayers = computed(() => {
  return players.value.map(p => ({
    ...p,
    displayName: `玩家${(p.id || '').replace('p', '')}`,
    alive: !deadPlayers.value.has(p.id),
  }))
})

const playerStatesMap = computed(() => {
  const map = {}
  players.value.forEach(p => {
    map[p.id] = {
      id: p.id,
      role: p.role,
      alive: !deadPlayers.value.has(p.id),
      displayName: `玩家${(p.id || '').replace('p', '')}`,
    }
  })
  return map
})

function getPlayerName(pid) {
  if (!pid) return '?'
  return `玩家${pid.replace('p', '')}`
}

// Auto-scroll to latest frame when new data arrives
watch(
  () => frames.value.length,
  () => {
    if (autoScroll.value) {
      nextTick(() => {
        currentFrame.value = frames.value.length - 1
      })
    }
  }
)

// Also auto-scroll when current frame data changes within the same frame
watch(
  () => {
    const f = frames.value[frames.value.length - 1]
    if (!f) return 0
    return f.speeches.length + (f.voteResult ? 10 : 0) + (f.elimination ? 20 : 0)
  },
  () => {
    if (autoScroll.value) {
      nextTick(() => {
        currentFrame.value = frames.value.length - 1
      })
    }
  }
)

async function doConnect() {
  try {
    await connect(host.value, port.value)
    message.success('已连接到服务器')
  } catch (e) {
    message.error('连接失败，请确认服务器已启动')
  }
}

function doStartGame() {
  startGame({
    total_players: totalPlayers.value,
    werewolf_count: werewolfCount.value,
    project: 'live',
  })
}

function handleLeave() {
  disconnect()
  emit('back')
}
</script>

<style scoped>
.live-game {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}

/* ===== Setup ===== */
.live-setup {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 40px 24px;
}

.setup-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 40px;
  width: 100%;
  max-width: 520px;
}

.setup-title {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--text-primary);
  text-align: center;
  margin: 0;
}

.setup-divider {
  display: flex;
  justify-content: center;
  margin: 16px 0 28px;
}
.setup-divider span {
  display: block;
  width: 40px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent-moon), transparent);
}

.setup-section {
  margin-bottom: 24px;
}
.setup-section h4 {
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--text-muted);
  text-transform: uppercase;
  margin: 0 0 12px;
}

.conn-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.host-input { flex: 1; }
.port-input { width: 90px; flex-shrink: 0; }
.conn-sep {
  font-family: var(--font-display);
  color: var(--text-muted);
  font-size: 16px;
}
.conn-btn {
  flex-shrink: 0;
  min-width: 100px;
}
.conn-btn.connected {
  background: #1a3a1a !important;
  border-color: #2a5a2a !important;
  color: #7acc7a !important;
}

.setup-alert {
  margin-top: 12px;
}

.config-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.config-item label {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 6px;
}
.config-item :deep(.ant-input-number) {
  width: 100%;
}

.start-btn {
  width: 100%;
  height: 44px;
  font-family: var(--font-display) !important;
  font-size: 15px !important;
  letter-spacing: 0.08em;
  background: var(--accent-werewolf) !important;
  border-color: var(--accent-werewolf) !important;
}
.start-btn:hover {
  opacity: 0.85;
}

/* ===== Viewer ===== */
.live-viewer {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 24px;
  border-bottom: 1px solid var(--border);
  background: var(--bg-secondary);
  flex-shrink: 0;
}
.top-left {
  display: flex;
  align-items: center;
  gap: 16px;
}
.back-btn {
  background: none;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  padding: 4px 12px;
  border-radius: var(--radius-sm);
  font-family: var(--font-display);
  font-size: 12px;
  letter-spacing: 0.06em;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 6px;
  transition: all 0.2s;
}
.back-btn:hover {
  border-color: var(--accent-werewolf);
  color: var(--accent-werewolf);
}
.game-id {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: var(--text-muted);
}
.top-center { display: flex; align-items: center; }

.thinking-badge {
  display: flex;
  align-items: center;
  gap: 10px;
  font-family: var(--font-display);
  font-size: 13px;
  letter-spacing: 0.06em;
  color: var(--accent-gold);
  padding: 6px 16px;
  background: rgba(196, 163, 90, 0.08);
  border: 1px solid rgba(196, 163, 90, 0.2);
  border-radius: var(--radius-sm);
}
.thinking-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--accent-gold);
  animation: pulse 1s ease-in-out infinite;
}

.winner-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  letter-spacing: 0.08em;
  padding: 6px 16px;
  border-radius: var(--radius-sm);
}
.winner-badge.werewolf {
  color: var(--accent-werewolf);
  background: var(--accent-werewolf-soft);
  border: 1px solid rgba(192, 57, 43, 0.3);
}
.winner-badge.villager {
  color: var(--accent-villager);
  background: var(--accent-villager-soft);
  border: 1px solid rgba(74, 142, 201, 0.3);
}

.viewer-body {
  display: flex;
  flex: 1;
  overflow: hidden;
}
.player-sidebar {
  width: 240px;
  flex-shrink: 0;
  padding: 16px 12px;
  overflow: hidden;
}
.phase-main {
  flex: 1;
  overflow-y: auto;
  border-left: 1px solid var(--border);
  border-right: 1px solid var(--border);
}
.empty-state { margin-top: 120px; }

/* Control Bar */
.control-bar {
  display: flex;
  align-items: center;
  padding: 14px 24px;
  border-top: 1px solid var(--border);
  background: var(--bg-secondary);
  gap: 24px;
  flex-shrink: 0;
}
.control-left {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 12px;
}
.auto-switch {
  margin-left: 4px;
}

.control-center {
  flex: 1;
  display: flex;
  justify-content: center;
}
.frame-dots {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  justify-content: center;
}
.frame-dot {
  background: var(--bg-tertiary);
  border: 1px solid var(--border);
  color: var(--text-secondary);
  padding: 4px 10px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-family: var(--font-display);
  font-size: 10px;
  letter-spacing: 0.05em;
  transition: all 0.2s;
}
.frame-dot:hover {
  border-color: var(--accent-gold);
  color: var(--text-primary);
}
.frame-dot.active {
  border-color: var(--accent-gold);
  color: #fff;
  background: rgba(196, 163, 90, 0.1);
}
.frame-dot.seen {
  color: var(--text-secondary);
}

.control-right {
  width: 200px;
  flex-shrink: 0;
}
</style>
