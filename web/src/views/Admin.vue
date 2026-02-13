<script setup>
import { ref, onMounted } from 'vue'
import { createInvitationCodes, getInvitationCodes } from '../api'

const codes = ref([])
const loading = ref(true)
const generateCount = ref(1)
const generateNote = ref('')
const generating = ref(false)
const newCodes = ref([])

onMounted(async () => {
  await loadCodes()
})

async function loadCodes() {
  loading.value = true
  codes.value = await getInvitationCodes()
  loading.value = false
}

async function onGenerate() {
  if (generateCount.value < 1) return
  generating.value = true
  newCodes.value = []
  try {
    const result = await createInvitationCodes(generateCount.value, generateNote.value || undefined)
    newCodes.value = Array.isArray(result) ? result : []
    generateNote.value = ''
    await loadCodes()
  } catch (e) {
    alert(e.response?.data?.detail || '生成失败')
  } finally {
    generating.value = false
  }
}

function formatTime(t) {
  if (!t) return '-'
  return new Date(t).toLocaleString('zh-CN')
}

function copyCode(code) {
  navigator.clipboard.writeText(code)
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>邀请码管理</h1>
      <p>生成和管理邀请码</p>
    </div>

    <!-- Generate Section -->
    <div class="card generate-section">
      <div class="card-title">生成邀请码</div>
      <div class="generate-form">
        <div class="form-row-inline">
          <label>数量</label>
          <input v-model.number="generateCount" type="number" min="1" max="50" />
        </div>
        <div class="form-row-inline">
          <label>备注</label>
          <input v-model="generateNote" type="text" placeholder="可选备注" />
        </div>
        <button class="btn-generate" :disabled="generating" @click="onGenerate">
          {{ generating ? '生成中...' : '生成' }}
        </button>
      </div>

      <!-- Newly generated codes -->
      <div v-if="newCodes.length" class="new-codes">
        <div class="new-codes-title">新生成的邀请码：</div>
        <div v-for="c in newCodes" :key="c.code || c" class="new-code-item" @click="copyCode(c.code || c)">
          <span class="code-text">{{ c.code || c }}</span>
          <span class="copy-hint">点击复制</span>
        </div>
      </div>
    </div>

    <!-- Code List -->
    <div class="card">
      <div class="card-title">邀请码列表</div>
      <div v-if="loading" class="loading">加载中</div>
      <div v-else-if="!codes.length" class="empty">暂无邀请码</div>
      <div v-else style="overflow-x: auto">
        <table class="data-table">
          <thead>
            <tr>
              <th>邀请码</th>
              <th>状态</th>
              <th>备注</th>
              <th>使用者</th>
              <th>使用时间</th>
              <th>创建时间</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="c in codes" :key="c.code">
              <td class="code-cell">{{ c.code }}</td>
              <td>
                <span :class="['badge', c.used_by ? 'badge-used' : 'badge-unused']">
                  {{ c.used_by ? '已使用' : '未使用' }}
                </span>
              </td>
              <td class="note-cell">{{ c.note || '-' }}</td>
              <td>{{ c.used_by || '-' }}</td>
              <td>{{ formatTime(c.used_at) }}</td>
              <td>{{ formatTime(c.created_at) }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<style scoped>
.generate-section {
  margin-bottom: 24px;
}

.generate-form {
  display: flex;
  gap: 16px;
  align-items: flex-end;
  flex-wrap: wrap;
}

.form-row-inline {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-row-inline label {
  color: var(--text-muted);
  font-size: 13px;
}

.form-row-inline input {
  padding: 8px 12px;
  background: #2a2a3e;
  border: 1px solid #444;
  border-radius: 6px;
  color: #fff;
  font-size: 14px;
  box-sizing: border-box;
}

.form-row-inline input[type="number"] {
  width: 80px;
}

.form-row-inline input[type="text"] {
  width: 200px;
}

.form-row-inline input:focus {
  border-color: var(--blue);
  outline: none;
}

.btn-generate {
  background: var(--blue);
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 8px 20px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: filter 0.2s;
}

.btn-generate:hover:not(:disabled) {
  filter: brightness(1.15);
}

.btn-generate:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.new-codes {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--border);
}

.new-codes-title {
  color: var(--green);
  font-size: 13px;
  margin-bottom: 8px;
  font-weight: 600;
}

.new-code-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px;
  background: #2a2a3e;
  border-radius: 4px;
  margin-bottom: 4px;
  cursor: pointer;
  transition: background 0.2s;
}

.new-code-item:hover {
  background: var(--bg-hover);
}

.code-text {
  font-family: 'Courier New', monospace;
  color: #fff;
  font-size: 14px;
  letter-spacing: 0.5px;
}

.copy-hint {
  color: var(--text-muted);
  font-size: 11px;
}

.code-cell {
  font-family: 'Courier New', monospace;
  color: #fff;
  letter-spacing: 0.5px;
}

.note-cell {
  color: var(--text-muted);
  font-size: 13px;
}

.badge-used {
  background: #444;
  color: #999;
}

.badge-unused {
  background: #1b5e20;
  color: #a5d6a7;
}
</style>
