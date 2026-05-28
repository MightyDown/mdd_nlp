<template>
  <div class="phase-display">
    <!-- Round Header -->
    <div class="round-header">
      <div class="round-badge">ROUND {{ frame.round }}</div>
      <div class="phase-steps">
        <a-steps :current="currentStepIndex" size="small" direction="horizontal">
          <a-step title="夜晚" />
          <a-step title="天亮" />
          <a-step title="发言" />
          <a-step title="投票" />
          <a-step title="放逐" />
        </a-steps>
      </div>
    </div>

    <div class="phase-content" :key="currentFrame">
      <!-- Night Phase -->
      <transition name="phase-card" appear>
        <div v-if="frame.night" class="phase-card night-card anim-fade-up" style="animation-delay: 0s">
          <div class="phase-icon">🌙</div>
          <div class="phase-body">
            <h4>狼人行动</h4>
            <p>
              狼人选择击杀
              <span class="highlight-target">{{ getPlayerName(frame.night.target_id) }}</span>
            </p>
            <p v-if="frame.night.reasoning" class="reasoning">
              "{{ frame.night.reasoning }}"
            </p>
          </div>
        </div>
      </transition>

      <!-- Day Announcement -->
      <transition name="phase-card" appear>
        <div v-if="frame.dayAnnouncement" class="phase-card day-card anim-fade-up" style="animation-delay: 0.1s">
          <div class="phase-icon">💀</div>
          <div class="phase-body">
            <h4>天亮公告</h4>
            <p v-if="frame.dayAnnouncement.dead_player">
              <span class="highlight-target">{{ getPlayerName(frame.dayAnnouncement.dead_player) }}</span>
              昨夜死亡
            </p>
            <p v-else class="no-death">昨晚是平安夜，无人死亡</p>
          </div>
        </div>
      </transition>

      <!-- Speeches -->
      <transition name="phase-card" appear>
        <div v-if="frame.speeches.length > 0" class="phase-card speech-card anim-fade-up" style="animation-delay: 0.2s">
          <div class="phase-icon">💬</div>
          <div class="phase-body">
            <h4>玩家发言</h4>
            <div class="speech-list">
              <div v-for="s in frame.speeches" :key="s.player_id" class="speech-item">
                <div class="speech-header">
                  <span class="speech-player">{{ getPlayerName(s.player_id) }}</span>
                </div>
                <p class="speech-content">{{ s.content }}</p>
              </div>
            </div>
          </div>
        </div>
      </transition>

      <!-- Vote Result -->
      <transition name="phase-card" appear>
        <div v-if="frame.voteResult" class="phase-card vote-card anim-fade-up" style="animation-delay: 0.3s">
          <div class="phase-icon">🗳️</div>
          <div class="phase-body">
            <h4>投票结果</h4>
            <div class="vote-grid">
              <div
                v-for="(target, voter) in frame.voteResult.votes"
                :key="voter"
                class="vote-item"
              >
                <span class="vote-voter">{{ getPlayerName(voter) }}</span>
                <span class="vote-arrow">→</span>
                <span class="vote-target">{{ getPlayerName(target) }}</span>
              </div>
            </div>
            <div class="vote-tally">
              <span
                v-for="(count, pid) in voteCounts"
                :key="pid"
                class="tally-chip"
              >
                {{ getPlayerName(pid) }}: {{ count }}票
              </span>
            </div>
          </div>
        </div>
      </transition>

      <!-- Elimination -->
      <transition name="phase-card" appear>
        <div v-if="frame.elimination" class="phase-card elim-card anim-fade-up" style="animation-delay: 0.4s">
          <div class="phase-icon">⚖️</div>
          <div class="phase-body">
            <h4>放逐结果</h4>
            <p v-if="frame.elimination.eliminated">
              <span class="highlight-target">{{ getPlayerName(frame.elimination.eliminated) }}</span> 被放逐
            </p>
            <p v-else>平票，无人被放逐</p>
          </div>
        </div>
      </transition>
    </div>

    <!-- Game Over Banner -->
    <transition name="banner" appear>
      <div v-if="frame.gameOver" class="game-over-banner anim-fade-up" style="animation-delay: 0.5s">
        <div class="winner-crown">🏆</div>
        <h3>
          <span v-if="frame.gameOver.winner === 'werewolf'" class="winner-wolf">狼人阵营</span>
          <span v-else class="winner-villager">村民阵营</span>
          获胜！
        </h3>
        <p>对局结束</p>
      </div>
    </transition>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  frame: { type: Object, required: true },
  playerStates: { type: Object, default: () => ({}) },
  currentFrame: { type: Number, default: 0 },
})

function getPlayerName(pid) {
  if (!pid) return '?'
  const state = props.playerStates[pid]
  if (state) return state.displayName
  return `玩家${pid.replace('p', '')}`
}

const voteCounts = computed(() => {
  if (!props.frame.voteResult?.votes) return {}
  const counts = {}
  Object.values(props.frame.voteResult.votes).forEach(target => {
    counts[target] = (counts[target] || 0) + 1
  })
  return counts
})

const currentStepIndex = computed(() => {
  const f = props.frame
  if (!f) return 0
  if (f.gameOver) return 5
  if (f.elimination) return 4
  if (f.voteResult) return 3
  if (f.speeches.length > 0) return 2
  if (f.dayAnnouncement) return 1
  if (f.night) return 0
  return 0
})
</script>

<style scoped>
.phase-display {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
}

.round-header {
  margin-bottom: 28px;
}

.round-badge {
  display: inline-block;
  font-family: var(--font-display);
  font-size: 18px;
  font-weight: 700;
  letter-spacing: 0.12em;
  color: var(--accent-moon);
  margin-bottom: 16px;
  padding: 6px 16px;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--accent-moon-soft);
}

.phase-steps {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 16px 20px;
}

.phase-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.phase-card {
  display: flex;
  gap: 16px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 20px;
  transition: border-color 0.3s;
}
.phase-card:hover {
  border-color: var(--border-active);
}

.phase-icon {
  font-size: 24px;
  flex-shrink: 0;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
}

.phase-body {
  flex: 1;
  min-width: 0;
}
.phase-body h4 {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--text-primary);
  margin: 0 0 8px;
}
.phase-body > p {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0;
}

.highlight-target {
  color: var(--accent-gold);
  font-weight: 600;
}

.no-death {
  color: var(--accent-villager) !important;
  font-style: italic;
}

.reasoning {
  margin-top: 8px !important;
  padding: 10px 14px;
  background: var(--bg-tertiary);
  border-left: 2px solid var(--accent-werewolf);
  border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
  font-size: 13px !important;
  color: var(--text-secondary) !important;
  font-style: italic;
}

/* Speeches */
.speech-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 8px;
}
.speech-item {
  background: var(--bg-secondary);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
  border-left: 2px solid var(--accent-moon);
}
.speech-header {
  margin-bottom: 4px;
}
.speech-player {
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.06em;
  color: var(--accent-moon);
}
.speech-content {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.6;
}

/* Votes */
.vote-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-top: 8px;
}
.vote-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
}
.vote-voter {
  color: var(--text-secondary);
  min-width: 60px;
}
.vote-arrow {
  color: var(--text-muted);
  font-family: var(--font-display);
}
.vote-target {
  color: var(--text-primary);
  font-weight: 600;
}
.vote-tally {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
.tally-chip {
  font-family: var(--font-display);
  font-size: 11px;
  letter-spacing: 0.05em;
  padding: 4px 10px;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  color: var(--accent-gold);
}

/* Game Over */
.game-over-banner {
  text-align: center;
  padding: 36px 24px;
  background: var(--bg-card);
  border: 1px solid var(--accent-gold);
  border-radius: var(--radius-lg);
  animation: moonGlow 2s ease-in-out infinite;
}
.game-over-banner .winner-crown {
  font-size: 48px;
  margin-bottom: 12px;
}
.game-over-banner h3 {
  font-family: var(--font-display);
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 4px;
}
.game-over-banner p {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0;
}
.winner-wolf {
  color: var(--accent-werewolf);
}
.winner-villager {
  color: var(--accent-villager);
}

/* Transitions */
.phase-card-enter-active {
  transition: all 0.4s ease-out;
}
.phase-card-enter-from {
  opacity: 0;
  transform: translateX(-20px);
}

.banner-enter-active {
  transition: all 0.6s ease-out;
}
.banner-enter-from {
  opacity: 0;
  transform: scale(0.95);
}
</style>
