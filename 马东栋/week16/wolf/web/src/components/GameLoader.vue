<template>
  <div class="game-loader">
    <button class="back-link" @click="$emit('back')">
      <ArrowLeftOutlined /> 返回
    </button>
    <div class="loader-hero">
      <h1 class="loader-title">WOLF</h1>
      <p class="loader-subtitle">狼人杀 AI 对局回放系统</p>
      <div class="loader-divider"><span></span></div>
    </div>

    <div class="loader-methods">
      <!-- File Upload -->
      <div class="loader-card">
        <div class="loader-card-icon">
          <FolderOpenOutlined />
        </div>
        <h3>选择日志文件</h3>
        <p>从本地加载 <code>messages.jsonl</code> 和可选的 <code>summary.json</code></p>

        <a-upload-dragger
          :multiple="true"
          :before-upload="() => false"
          :accept="'.jsonl,.json'"
          @change="handleFileChange"
          class="upload-zone"
        >
          <p class="upload-icon">
            <CloudUploadOutlined />
          </p>
          <p class="upload-text">点击或拖拽文件到此处</p>
          <p class="upload-hint">支持 .jsonl 和 .json 文件</p>
        </a-upload-dragger>

        <div v-if="files.length > 0" class="file-list">
          <a-tag v-for="f in files" :key="f.name" :color="f.name.endsWith('.jsonl') ? 'red' : 'gold'">
            {{ f.name }}
          </a-tag>
        </div>

        <a-button
          type="primary"
          :disabled="files.length === 0"
          :loading="loading"
          @click="loadFromFiles"
          class="load-btn"
        >
          加载对局
        </a-button>
      </div>

      <!-- Paste Zone -->
      <div class="loader-card">
        <div class="loader-card-icon">
          <EditOutlined />
        </div>
        <h3>粘贴日志内容</h3>
        <p>将 <code>messages.jsonl</code> 的内容粘贴到下方</p>

        <a-textarea
          v-model:value="pastedText"
          :rows="8"
          placeholder="粘贴 messages.jsonl 的内容（每行一条 JSON）..."
          class="paste-zone"
        />

        <a-button
          type="primary"
          :disabled="!pastedText.trim()"
          :loading="loading"
          @click="loadFromPaste"
          class="load-btn"
        >
          加载对局
        </a-button>
      </div>
    </div>

    <a-alert v-if="error" :message="error" type="error" show-icon closable class="error-alert" />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { CloudUploadOutlined, FolderOpenOutlined, EditOutlined, ArrowLeftOutlined } from '@ant-design/icons-vue'

const emit = defineEmits(['load'])

const files = ref([])
const pastedText = ref('')
const loading = ref(false)
const error = ref(null)

function handleFileChange(info) {
  files.value = info.fileList.map(f => f.originFileObj || f).filter(Boolean)
}

async function loadFromFiles() {
  error.value = null
  loading.value = true

  const fileList = files.value
  let messagesText = ''
  let summaryText = null

  for (const file of fileList) {
    const text = await file.text()
    if (file.name === 'messages.jsonl' || file.name.endsWith('.jsonl')) {
      messagesText = text
    } else if (file.name === 'summary.json' || file.name.endsWith('.json') && file.name !== 'messages.jsonl') {
      summaryText = text
    }
  }

  if (!messagesText) {
    error.value = '请选择 messages.jsonl 文件'
    loading.value = false
    return
  }

  emit('load', { type: 'files', messagesText, summaryText })
}

function loadFromPaste() {
  error.value = null
  if (!pastedText.value.trim()) {
    error.value = '请粘贴日志内容'
    return
  }
  loading.value = true
  emit('load', { type: 'paste', messagesText: pastedText.value, summaryText: null })
}

defineExpose({ setLoading: (v) => { loading.value = v }, setError: (e) => { error.value = e } })
</script>

<style scoped>
.game-loader {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  padding: 40px 24px;
  position: relative;
}

.back-link {
  position: absolute;
  top: 24px;
  left: 24px;
  background: none;
  border: 1px solid var(--border);
  color: var(--text-secondary);
  padding: 6px 14px;
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
.back-link:hover {
  border-color: var(--accent-moon);
  color: var(--text-primary);
}

.loader-hero {
  text-align: center;
  margin-bottom: 48px;
}

.loader-title {
  font-family: var(--font-display);
  font-size: 72px;
  font-weight: 900;
  letter-spacing: 0.16em;
  color: var(--text-primary);
  margin: 0;
  text-shadow: 0 0 60px rgba(184, 197, 214, 0.15);
}

.loader-subtitle {
  font-family: var(--font-body);
  font-size: 16px;
  font-weight: 300;
  color: var(--text-secondary);
  margin-top: 8px;
  letter-spacing: 0.12em;
}

.loader-divider {
  display: flex;
  justify-content: center;
  margin-top: 24px;
}
.loader-divider span {
  display: block;
  width: 60px;
  height: 1px;
  background: linear-gradient(90deg, transparent, var(--accent-moon), transparent);
}

.loader-methods {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
  gap: 32px;
  width: 100%;
  max-width: 900px;
}

.loader-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 32px;
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  transition: border-color 0.3s;
}
.loader-card:hover {
  border-color: var(--border-active);
}
.loader-card h3 {
  font-family: var(--font-display);
  font-size: 15px;
  font-weight: 600;
  letter-spacing: 0.08em;
  color: var(--text-primary);
  margin: 0 0 8px;
}
.loader-card > p {
  font-size: 13px;
  color: var(--text-muted);
  margin: 0 0 20px;
}
.loader-card code {
  background: var(--bg-tertiary);
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 12px;
  color: var(--accent-moon);
}

.loader-card-icon {
  font-size: 28px;
  color: var(--accent-moon);
  margin-bottom: 16px;
  opacity: 0.5;
}

.upload-zone {
  width: 100%;
  margin-bottom: 16px;
}
.upload-icon {
  font-size: 32px;
  color: var(--text-muted);
  margin: 0;
}

.file-list {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.load-btn {
  margin-top: auto;
  width: 100%;
  height: 40px;
  font-family: var(--font-display) !important;
  letter-spacing: 0.08em;
  background: var(--accent-werewolf) !important;
  border-color: var(--accent-werewolf) !important;
}
.load-btn:hover {
  opacity: 0.85;
}

.paste-zone {
  width: 100%;
  margin-bottom: 16px;
  background: var(--bg-tertiary) !important;
  border-color: var(--border) !important;
  color: var(--text-primary) !important;
  font-family: 'Courier New', monospace !important;
  font-size: 12px !important;
  resize: vertical;
}

.error-alert {
  margin-top: 24px;
  max-width: 500px;
}
</style>
