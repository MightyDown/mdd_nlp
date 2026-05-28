<template>
  <div class="player-panel">
    <h3 class="panel-title">玩家</h3>
    <div class="player-cards">
      <div
        v-for="player in players"
        :key="player.id"
        :class="['player-card', { dead: !player.alive, werewolf: player.role === 'werewolf' }]"
      >
        <div class="player-medallion">
          <span class="player-num">{{ player.id.replace('p', '') }}</span>
        </div>
        <div class="player-info">
          <span class="player-name">{{ player.displayName }}</span>
          <a-tag :color="player.role === 'werewolf' ? 'red' : 'blue'" size="small">
            {{ player.role === 'werewolf' ? '狼人' : '村民' }}
          </a-tag>
        </div>
        <div class="player-status">
          <span v-if="player.alive" class="status-alive">存活</span>
          <span v-else class="status-dead">已淘汰</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  playerStates: { type: Object, default: () => ({}) },
})

const players = computed(() => Object.values(props.playerStates))
</script>

<style scoped>
.player-panel {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 20px;
  height: 100%;
  overflow-y: auto;
}

.panel-title {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.12em;
  color: var(--text-muted);
  text-transform: uppercase;
  margin: 0 0 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--border);
}

.player-cards {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.player-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  transition: all 0.3s ease;
}
.player-card:hover {
  border-color: var(--border-active);
}
.player-card.werewolf {
  border-left: 2px solid var(--accent-werewolf);
}
.player-card:not(.werewolf) {
  border-left: 2px solid var(--accent-villager);
}
.player-card.dead {
  opacity: 0.45;
}
.player-card.dead .player-medallion {
  filter: grayscale(1);
}

.player-medallion {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--bg-tertiary);
  border: 2px solid var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  transition: all 0.3s;
}
.player-card.werewolf .player-medallion {
  border-color: var(--accent-werewolf);
  box-shadow: 0 0 12px var(--accent-werewolf-soft);
}
.player-card:not(.werewolf) .player-medallion {
  border-color: var(--accent-villager);
  box-shadow: 0 0 12px var(--accent-villager-soft);
}

.player-num {
  font-family: var(--font-display);
  font-size: 14px;
  font-weight: 700;
  color: var(--text-primary);
}

.player-info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.player-name {
  font-size: 13px;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.player-status {
  flex-shrink: 0;
}

.status-alive {
  font-size: 11px;
  color: #4a9;
  font-family: var(--font-display);
  letter-spacing: 0.06em;
}
.status-dead {
  font-size: 11px;
  color: var(--text-muted);
  font-family: var(--font-display);
  letter-spacing: 0.06em;
  text-decoration: line-through;
}
</style>
