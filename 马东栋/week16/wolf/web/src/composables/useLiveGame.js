import { ref, computed, shallowRef } from 'vue'

/**
 * WebSocket client for live game streaming.
 *
 * Protocol:
 *   Send: { type: "start_game", config: { total_players, werewolf_count, project } }
 *   Recv: { type: "game_started" | "game_message" | "thinking" | "game_over" | "error" }
 */
export function useLiveGame() {
  const ws = shallowRef(null)
  const connected = ref(false)
  const connecting = ref(false)
  const error = ref(null)

  // Game state
  const gameId = ref('')
  const gameStarted = ref(false)
  const gameEnded = ref(false)
  const summary = ref(null)
  const players = ref([])
  const werewolfIds = ref([])
  const deadPlayers = ref(new Set())

  // Streaming frames — built incrementally from messages
  const frames = ref([])
  const currentFrame = ref(0)
  const totalFrames = computed(() => frames.value.length)

  // Thinking indicator
  const thinking = ref(null) // { player_id, phase }

  // Winner
  const winner = computed(() => summary.value?.winner ?? null)

  function connect(host = 'localhost', port = 8765) {
    return new Promise((resolve, reject) => {
      if (ws.value) {
        ws.value.close()
      }

      connecting.value = true
      error.value = null

      const url = `ws://${host}:${port}`
      const socket = new WebSocket(url)

      socket.onopen = () => {
        connected.value = true
        connecting.value = false
        ws.value = socket
        resolve()
      }

      socket.onclose = () => {
        connected.value = false
        connecting.value = false
        ws.value = null
      }

      socket.onerror = (e) => {
        connecting.value = false
        error.value = `连接失败: ${url}`
        reject(new Error(`WebSocket connection to ${url} failed`))
      }

      socket.onmessage = (event) => {
        try {
          const msg = JSON.parse(event.data)
          handleMessage(msg)
        } catch (e) {
          console.error('Failed to parse WS message:', e)
        }
      }
    })
  }

  function handleMessage(msg) {
    switch (msg.type) {
      case 'game_started':
        gameId.value = msg.game_id
        players.value = msg.players
        werewolfIds.value = msg.werewolf_ids
        deadPlayers.value = new Set()
        gameStarted.value = true
        gameEnded.value = false
        summary.value = null
        frames.value = []
        currentFrame.value = 0
        // Seed first empty frame for night_start
        frames.value.push({
          round: 1,
          night: null,
          dayAnnouncement: null,
          speeches: [],
          voteResult: null,
          elimination: null,
          gameOver: null,
        })
        break

      case 'game_message':
        handleGameMessage(msg.message)
        break

      case 'thinking':
        thinking.value = { player_id: msg.player_id, phase: msg.phase }
        break

      case 'game_over':
        summary.value = msg.summary
        gameEnded.value = true
        // Mark final frame with game over
        if (frames.value.length > 0) {
          frames.value[frames.value.length - 1].gameOver = {
            winner: msg.summary.winner,
          }
        }
        thinking.value = null
        break

      case 'error':
        error.value = msg.message
        break
    }
  }

  function handleGameMessage(msg) {
    const lastFrame = frames.value[frames.value.length - 1]
    thinking.value = null

    switch (msg.type) {
      case 'night_start': {
        // Only create new frame if this isn't the initial round
        if (frames.value.length === 1 &&
            !lastFrame.night &&
            !lastFrame.dayAnnouncement &&
            lastFrame.speeches.length === 0) {
          // Still in initial empty frame, update round
          lastFrame.round = msg.content?.round ?? msg.round
        } else {
          frames.value.push({
            round: msg.content?.round ?? msg.round,
            night: null,
            dayAnnouncement: null,
            speeches: [],
            voteResult: null,
            elimination: null,
            gameOver: null,
          })
        }
        break
      }

      case 'night_kill_target':
        if (lastFrame) lastFrame.night = msg.content
        // Auto-advance to show night result
        currentFrame.value = frames.value.length - 1
        break

      case 'day_announcement':
        if (lastFrame) lastFrame.dayAnnouncement = msg.content
        if (msg.content?.dead_player) deadPlayers.value.add(msg.content.dead_player)
        currentFrame.value = frames.value.length - 1
        break

      case 'speech':
        if (lastFrame) lastFrame.speeches.push(msg.content)
        currentFrame.value = frames.value.length - 1
        break

      case 'vote_result':
        if (lastFrame) lastFrame.voteResult = msg.content
        currentFrame.value = frames.value.length - 1
        break

      case 'elimination':
        if (lastFrame) lastFrame.elimination = msg.content
        if (msg.content?.eliminated) deadPlayers.value.add(msg.content.eliminated)
        currentFrame.value = frames.value.length - 1
        break

      case 'game_over':
        if (lastFrame) lastFrame.gameOver = msg.content
        currentFrame.value = frames.value.length - 1
        break
    }
  }

  function startGame(config) {
    if (!ws.value || !connected.value) {
      error.value = '未连接到服务器'
      return
    }
    error.value = null
    ws.value.send(JSON.stringify({ type: 'start_game', config }))
  }

  function disconnect() {
    if (ws.value) {
      ws.value.close()
      ws.value = null
    }
    connected.value = false
    gameStarted.value = false
    gameEnded.value = false
    frames.value = []
    players.value = []
    summary.value = null
  }

  function goToFrame(index) {
    if (index >= 0 && index < totalFrames.value) {
      currentFrame.value = index
    }
  }

  function prevFrame() {
    if (currentFrame.value > 0) currentFrame.value--
  }

  function nextFrame() {
    if (currentFrame.value < totalFrames.value - 1) currentFrame.value++
  }

  return {
    ws,
    connected,
    connecting,
    error,
    gameId,
    gameStarted,
    gameEnded,
    summary,
    players,
    werewolfIds,
    deadPlayers,
    frames,
    currentFrame,
    totalFrames,
    thinking,
    winner,
    connect,
    startGame,
    disconnect,
    goToFrame,
    prevFrame,
    nextFrame,
  }
}
