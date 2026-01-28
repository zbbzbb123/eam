<script setup>
import { ref, onMounted } from 'vue'
import { getWeeklyReport, enhanceReport } from '../api'

const report = ref(null)
const loading = ref(true)
const enhancedReport = ref(null)
const enhanceLoading = ref(false)

onMounted(async () => {
  report.value = await getWeeklyReport()
  loading.value = false
})

function renderItems(items) {
  if (!items) return []
  if (Array.isArray(items)) return items
  if (typeof items === 'string') return [items]
  return Object.entries(items).map(([k, v]) => `${k}: ${typeof v === 'object' ? JSON.stringify(v) : v}`)
}

async function onEnhance() {
  enhanceLoading.value = true
  enhancedReport.value = await enhanceReport()
  enhanceLoading.value = false
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>周报分析</h1>
      <p>每周投资组合报告</p>
    </div>

    <div v-if="loading" class="loading">加载中</div>

    <div v-else-if="!report" class="empty">暂无报告数据。后端服务未运行或尚未生成周报。</div>

    <template v-else>
      <div style="margin-bottom:16px">
        <button class="ai-btn" :disabled="enhanceLoading" @click="onEnhance">
          {{ enhanceLoading ? 'AI 增强中...' : 'AI增强报告' }}
        </button>
      </div>

      <!-- Portfolio Summary -->
      <div class="card report-section">
        <h2>📊 组合概要</h2>
        <div v-if="report.portfolio_summary">
          <ul>
            <li v-for="item in renderItems(report.portfolio_summary)" :key="item">{{ item }}</li>
          </ul>
        </div>
        <div v-else class="empty">无数据</div>
      </div>

      <!-- Signal Summary -->
      <div class="card report-section">
        <h2>🔔 信号汇总</h2>
        <div v-if="report.signal_summary">
          <ul>
            <li v-for="item in renderItems(report.signal_summary)" :key="item">{{ item }}</li>
          </ul>
        </div>
        <div v-else class="empty">无数据</div>
      </div>

      <!-- Risk Alerts -->
      <div class="card report-section">
        <h2>⚠️ 风险提醒</h2>
        <div v-if="report.risk_alerts && report.risk_alerts.length">
          <ul>
            <li v-for="item in report.risk_alerts" :key="item">{{ typeof item === 'object' ? JSON.stringify(item) : item }}</li>
          </ul>
        </div>
        <div v-else class="empty">无风险提醒</div>
      </div>

      <!-- Action Items -->
      <div class="card report-section">
        <h2>✅ 行动建议</h2>
        <div v-if="report.action_items && report.action_items.length">
          <ul>
            <li v-for="item in report.action_items" :key="item">{{ typeof item === 'object' ? JSON.stringify(item) : item }}</li>
          </ul>
        </div>
        <div v-else class="empty">无行动建议</div>
      </div>

      <!-- Raw fallback for unexpected structure -->
      <div class="card report-section" v-if="!report.portfolio_summary && !report.signal_summary && !report.risk_alerts && !report.action_items">
        <h2>报告内容</h2>
        <pre style="color:var(--text-muted);white-space:pre-wrap;font-size:13px">{{ JSON.stringify(report, null, 2) }}</pre>
      </div>

      <!-- AI Enhanced Report -->
      <div v-if="enhanceLoading" class="card report-section">
        <h2>🤖 AI 增强报告</h2>
        <div class="ai-loading-text">AI 增强中...</div>
      </div>
      <div v-else-if="enhancedReport" class="card report-section ai-enhanced">
        <h2>🤖 AI 增强报告</h2>
        <pre class="ai-enhanced-text">{{ typeof enhancedReport === 'string' ? enhancedReport : JSON.stringify(enhancedReport, null, 2) }}</pre>
      </div>
    </template>
  </div>
</template>

<style scoped>
.ai-btn {
  background: linear-gradient(135deg, #4fc3f7, #0288d1);
  color: #fff; border: none; border-radius: 6px; padding: 8px 16px;
  font-size: 13px; cursor: pointer; font-weight: 600;
}
.ai-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.ai-btn:hover:not(:disabled) { filter: brightness(1.15); }
.ai-loading-text { color: #8892a4; padding: 20px 0; font-size: 14px; }
.ai-enhanced { border-left: 3px solid #4fc3f7; }
.ai-enhanced-text { color: #e0e6ed; white-space: pre-wrap; font-size: 13px; line-height: 1.7; font-family: inherit; background: none; margin: 0; }
</style>
