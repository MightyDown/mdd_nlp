import { ref, computed } from 'vue'

/**
 * Parse JSONL game log into structured replay data.
 *
 * Each round produces a frame:
 *   { round, night, dayAnnouncement, speeches: [], voteResult, elimination, gameOver }
 */
export function useGameReplay() {
  const messages = ref([])
  const summary = ref(null)
  const frames = ref([])
  const currentFrame = ref(0)
  const playerStates = ref({})
  const loading = ref(false)
  const error = ref(null)

  const totalFrames = computed(() => frames.value.length)
  const currentRound = computed(() => frames.value[currentFrame.value]?.round ?? 0)
  const isGameOver = computed(() => frames.value[currentFrame.value]?.gameOver != null)
  const hasData = computed(() => frames.value.length > 0)
  const winner = computed(() => summary.value?.winner ?? frames.value[currentFrame.value]?.gameOver?.winner ?? null)

  const canPrev = computed(() => currentFrame.value > 0)
  const canNext = computed(() => currentFrame.value < totalFrames.value - 1)

  function parseMessages(jsonlText) {
    const lines = jsonlText.trim().split('\n').filter(Boolean)
    return lines.map(line => {
      try { return JSON.parse(line) } catch { return null }
    }).filter(Boolean)
  }

  function buildFrames(msgs) {
    const result = []
    let currentRound = null
    let frame = null

    // Collect unique player IDs from visible_to
    const playerSet = new Set()
    msgs.forEach(m => m.visible_to?.forEach(id => {
      if (id && id !== 'all') playerSet.add(id)
    }))

    function finishFrame() {
      if (frame) {
        result.push({ ...frame })
        frame = null
      }
    }

    for (const msg of msgs) {
      // Detect round from night_start
      if (msg.type === 'night_start') {
        finishFrame()
        currentRound = msg.content?.round ?? msg.round
        frame = { round: currentRound, night: null, dayAnnouncement: null, speeches: [], voteResult: null, elimination: null, gameOver: null }
        continue
      }

      if (!frame) continue

      switch (msg.type) {
        case 'night_kill_target':
          frame.night = msg.content
          break
        case 'day_announcement':
          frame.dayAnnouncement = msg.content
          break
        case 'speech':
          frame.speeches.push(msg.content)
          break
        case 'vote_result':
          frame.voteResult = msg.content
          break
        case 'elimination':
          frame.elimination = msg.content
          break
        case 'game_over':
          frame.gameOver = msg.content
          break
      }
    }
    finishFrame()

    return result
  }

  function computePlayerStates(msgs, summ) {
    const states = {}

    // If we have summary, use it for role info
    if (summ?.players) {
      summ.players.forEach(p => {
        states[p.id] = {
          id: p.id,
          role: p.role,
          alive: p.alive,
          displayName: `玩家${p.id.replace('p', '')}`,
        }
      })
      return states
    }

    // Otherwise infer from visible_to patterns — werewolves appear in night_kill_target visible_to
    const wolfSet = new Set()
    for (const msg of msgs) {
      if (msg.type === 'night_kill_target' && msg.visible_to) {
        msg.visible_to.forEach(id => wolfSet.add(id))
      }
    }

    // Collect all player IDs from day_announcement visible_to
    const allPlayers = new Set()
    for (const msg of msgs) {
      if (msg.type === 'day_announcement' && msg.visible_to) {
        msg.visible_to.forEach(id => allPlayers.add(id))
      }
    }

    // Track deaths
    const deadSet = new Set()
    const eliminationOrder = []
    for (const msg of msgs) {
      if (msg.type === 'day_announcement' && msg.content?.dead_player) {
        deadSet.add(msg.content.dead_player)
        eliminationOrder.push(msg.content.dead_player)
      }
      if (msg.type === 'elimination' && msg.content?.eliminated) {
        deadSet.add(msg.content.eliminated)
        eliminationOrder.push(msg.content.eliminated)
      }
    }

    allPlayers.forEach(id => {
      states[id] = {
        id,
        role: wolfSet.has(id) ? 'werewolf' : 'villager',
        alive: !deadSet.has(id),
        displayName: `玩家${id.replace('p', '')}`,
      }
    })

    return states
  }

  function loadFromText(jsonlText, summaryJson = null) {
    loading.value = true
    error.value = null

    const msgs = parseMessages(jsonlText)
    if (msgs.length === 0) {
      error.value = '未能解析任何有效消息，请检查文件格式'
      loading.value = false
      return
    }

    messages.value = msgs
    summary.value = summaryJson
    frames.value = buildFrames(msgs)
    playerStates.value = computePlayerStates(msgs, summaryJson)
    currentFrame.value = 0
    loading.value = false
  }

  function loadFromFiles(messagesText, summaryText = null) {
    let summaryJson = null
    if (summaryText) {
      try { summaryJson = JSON.parse(summaryText) } catch { /* ignore */ }
    }
    loadFromText(messagesText, summaryJson)
  }

  function prevFrame() {
    if (canPrev.value) currentFrame.value--
  }

  function nextFrame() {
    if (canNext.value) currentFrame.value++
  }

  function goToFrame(index) {
    if (index >= 0 && index < totalFrames.value) currentFrame.value = index
  }

  function reset() {
    messages.value = []
    summary.value = null
    frames.value = []
    currentFrame.value = 0
    playerStates.value = {}
    error.value = null
  }

  return {
    messages,
    summary,
    frames,
    currentFrame,
    playerStates,
    loading,
    error,
    totalFrames,
    currentRound,
    isGameOver,
    hasData,
    winner,
    canPrev,
    canNext,
    loadFromText,
    loadFromFiles,
    prevFrame,
    nextFrame,
    goToFrame,
    reset,
  }
}
