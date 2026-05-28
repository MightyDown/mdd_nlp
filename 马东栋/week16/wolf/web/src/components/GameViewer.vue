<template>
  <div class="game-viewer">
    <!-- Top Bar -->
    <div class="top-bar">
      <div class="top-left">
        <button class="back-btn" @click="$emit('back')">
          <ArrowLeftOutlined /> 返回
        </button>
        <span class="game-id">{{ gameId }}</span>
      </div>
      <div class="top-center">
        <span v-if="winner" class="winner-badge" :class="winner">
          <TrophyOutlined />
          {{ winner === 'werewolf' ? '狼人获胜' : '村民获胜' }}
        </span>
      </div>
      <div class="top-right">
        <a-statistic
          title="回合进度"
          :value="currentFrame + 1"
          :suffix="`/ ${totalFrames}`"
          class="round-stat"
        />
      </div>
    </div>

    <!-- Main Content Area -->
    <div class="viewer-body">
      <!-- Player Panel (Left Sidebar) -->
      <aside class="player-sidebar">
        <PlayerPanel :playerStates="playerStates" />
      </aside>

      <!-- Phase Display (Center) -->
      <main class="phase-main">
        <PhaseDisplay
          v-if="currentFrameData"
          :frame="currentFrameData"
          :playerStates="playerStates"
          :currentFrame="currentFrame"
          :key="currentFrame"
        />
        <a-empty v-else description="无数据" class="empty-state" />
      </main>
    </div>

    <!-- Bottom Control Bar -->
    <div class="control-bar">
      <div class="control-left">
        <a-button-group>
          <a-button :disabled="!canPrev" @click="$emit('prev')">
            <StepBackwardOutlined /> 上一回合
          </a-button>
          <a-button :disabled="!canNext" @click="$emit('next')">
            下一回合 <StepForwardOutlined />
          </a-button>
        </a-button-group>
      </div>

      <div class="control-center">
        <div class="frame-dots">
          <button
            v-for="(f, i) in frames"
            :key="i"
            :class="['frame-dot', { active: i === currentFrame, seen: i < currentFrame }]"
            :title="`第 ${f.round} 回合`"
            @click="$emit('goto', i)"
          >
            R{{ f.round }}
          </button>
        </div>
      </div>

      <div class="control-right">
        <a-slider
          :min="0"
          :max="totalFrames - 1"
          :value="currentFrame"
          @change="$emit('goto', $event)"
          :tooltip="{ formatter: (v) => `第 ${frames[v]?.round ?? '?'} 回合` }"
          class="frame-slider"
        />
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import {
  ArrowLeftOutlined,
  TrophyOutlined,
  StepBackwardOutlined,
  StepForwardOutlined,
} from '@ant-design/icons-vue'
import PlayerPanel from './PlayerPanel.vue'
import PhaseDisplay from './PhaseDisplay.vue'

const props = defineProps({
  playerStates: { type: Object, default: () => ({}) },
  frames: { type: Array, default: () => [] },
  currentFrame: { type: Number, default: 0 },
  totalFrames: { type: Number, default: 0 },
  canPrev: { type: Boolean, default: false },
  canNext: { type: Boolean, default: false },
  winner: { type: String, default: null },
  gameId: { type: String, default: '' },
})

defineEmits(['back', 'prev', 'next', 'goto'])

const currentFrameData = computed(() => props.frames[props.currentFrame] ?? null)
</script>

<style scoped>
.game-viewer {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--bg-primary);
}

/* Top Bar */
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
  border-color: var(--accent-moon);
  color: var(--text-primary);
}
.game-id {
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: var(--text-muted);
}

.top-center {
  display: flex;
  align-items: center;
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

.round-stat {
  min-width: 100px;
}

/* Body */
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

.empty-state {
  margin-top: 120px;
}

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
  border-color: var(--accent-moon);
  color: var(--text-primary);
}
.frame-dot.active {
  border-color: var(--accent-moon);
  color: #fff;
  background: var(--accent-moon-soft);
}
.frame-dot.seen {
  color: var(--text-secondary);
}

.control-right {
  width: 200px;
  flex-shrink: 0;
}
.frame-slider {
  margin: 0;
}
</style>
