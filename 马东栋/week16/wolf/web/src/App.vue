<template>
  <div class="app-root">
    <!-- Mode Selection -->
    <div v-if="!mode" class="mode-select">
      <div class="mode-hero">
        <h1 class="mode-title">WOLF</h1>
        <p class="mode-subtitle">狼人杀 AI 对局系统</p>
        <div class="mode-divider"><span></span></div>
      </div>

      <div class="mode-cards">
        <div class="mode-card" @click="mode = 'live'">
          <div class="mode-card-icon">
            <ThunderboltOutlined />
          </div>
          <h3>即时对局</h3>
          <p>连接服务器，实时观看 AI 狼人杀对局。每一步决策、每一次发言都在你眼前展开。</p>
          <span class="mode-tag live-tag">实时</span>
        </div>

        <div class="mode-card" @click="mode = 'replay'">
          <div class="mode-card-icon">
            <HistoryOutlined />
          </div>
          <h3>对局回放</h3>
          <p>加载已完成的日志文件，逐回合回顾 AI 的推理、投票和胜负过程。</p>
          <span class="mode-tag replay-tag">离线</span>
        </div>
      </div>
    </div>

    <!-- Replay Mode -->
    <template v-else-if="mode === 'replay'">
      <GameLoader
        v-if="!gameView.hasData.value"
        ref="loaderRef"
        @load="handleLoad"
        @back="mode = null"
      />
      <GameViewer
        v-else
        :playerStates="gameView.playerStates.value"
        :frames="gameView.frames.value"
        :currentFrame="gameView.currentFrame.value"
        :totalFrames="gameView.totalFrames.value"
        :canPrev="gameView.canPrev.value"
        :canNext="gameView.canNext.value"
        :winner="gameView.winner.value"
        :gameId="gameId"
        @back="handleReplayBack"
        @prev="gameView.prevFrame()"
        @next="gameView.nextFrame()"
        @goto="gameView.goToFrame($event)"
      />
    </template>

    <!-- Live Mode -->
    <LiveGame
      v-else-if="mode === 'live'"
      @back="mode = null"
    />

    <!-- Background ambient -->
    <div class="bg-ambient"></div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { ThunderboltOutlined, HistoryOutlined } from '@ant-design/icons-vue'
import GameLoader from './components/GameLoader.vue'
import GameViewer from './components/GameViewer.vue'
import LiveGame from './components/LiveGame.vue'
import { useGameReplay } from './composables/useGameReplay.js'

const mode = ref(null) // null = selection, 'replay' | 'live'
const gameView = useGameReplay()
const loaderRef = ref(null)
const gameId = ref('')

function handleLoad({ messagesText, summaryText }) {
  gameView.loadFromFiles(messagesText, summaryText)
  if (summaryText) {
    try {
      const s = JSON.parse(summaryText)
      gameId.value = s.game_id || ''
    } catch { /* ignore */ }
  }
  if (loaderRef.value) {
    loaderRef.value.setLoading(false)
  }
}

function handleReplayBack() {
  gameView.reset()
  gameId.value = ''
}
</script>

<style scoped>
.app-root {
  height: 100vh;
  overflow: hidden;
  position: relative;
}

/* ===== Mode Selection ===== */
.mode-select {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 40px 24px;
}

.mode-hero {
  text-align: center;
  margin-bottom: 56px;
}

.mode-title {
  font-family: var(--font-display);
  font-size: 80px;
  font-weight: 900;
  letter-spacing: 0.2em;
  color: var(--text-primary);
  margin: 0;
  text-shadow: 0 0 80px rgba(184, 197, 214, 0.12);
}

.mode-subtitle {
  font-family: var(--font-body);
  font-size: 16px;
  font-weight: 300;
  color: var(--text-secondary);
  margin-top: 8px;
  letter-spacing: 0.12em;
}

.mode-divider {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
.mode-divider span {
  display: block;
  width: 60px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent-moon), transparent);
}

/* Mode Cards */
.mode-cards {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 32px;
  width: 100%;
  max-width: 680px;
}

.mode-card {
  position: relative;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 36px 28px;
  cursor: pointer;
  transition: all 0.3s ease;
  text-align: center;
}
.mode-card:hover {
  border-color: var(--accent-moon);
  transform: translateY(-2px);
  box-shadow: var(--shadow-card);
}

.mode-card-icon {
  font-size: 36px;
  color: var(--accent-moon);
  margin-bottom: 16px;
  opacity: 0.6;
}
.mode-card:hover .mode-card-icon {
  opacity: 1;
}

.mode-card h3 {
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--text-primary);
  margin: 0 0 10px;
}

.mode-card p {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.7;
  margin: 0;
}

.mode-tag {
  display: inline-block;
  margin-top: 16px;
  padding: 2px 10px;
  border-radius: var(--radius-sm);
  font-family: var(--font-display);
  font-size: 10px;
  letter-spacing: 0.08em;
}
.live-tag {
  color: var(--accent-werewolf);
  border: 1px solid rgba(192, 57, 43, 0.3);
  background: var(--accent-werewolf-soft);
}
.replay-tag {
  color: var(--accent-villager);
  border: 1px solid rgba(74, 142, 201, 0.3);
  background: var(--accent-villager-soft);
}

/* Add back button to GameLoader */
:deep(.game-loader) .back-link {
  position: absolute;
  top: 24px;
  left: 24px;
}

/* ===== Background ===== */
.bg-ambient {
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background:
    radial-gradient(ellipse at 20% 20%, rgba(192, 57, 43, 0.03) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 80%, rgba(74, 142, 201, 0.03) 0%, transparent 50%),
    radial-gradient(ellipse at 50% 0%, rgba(184, 197, 214, 0.04) 0%, transparent 40%);
}

.app-root > :deep(*) {
  position: relative;
  z-index: 1;
}
</style>
