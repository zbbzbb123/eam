<script setup>
import { ref, onMounted } from 'vue'
import { getDailyReportList, getDailyReportDetail, getWeeklyReportList, getWeeklyReportDetail, triggerDailyReport, triggerWeeklyReport } from '../api'
import DailyReportView from '../components/report/DailyReportView.vue'
import WeeklyReportView from '../components/report/WeeklyReportView.vue'

const activeTab = ref('daily')
const reports = ref([])
const loading = ref(false)
const expandedId = ref(null)
const expandedContent = ref(null)
const loadingDetail = ref(false)
const generating = ref(false)

async function loadList(type) {
  loading.value = true
  reports.value = []
  expandedId.value = null
  expandedContent.value = null
  try {
    if (type === 'daily') {
      reports.value = await getDailyReportList()
    } else {
      reports.value = await getWeeklyReportList()
    }
    // Auto-expand the latest report
    if (reports.value.length > 0) {
      await toggleReport(reports.value[0])
    }
  } finally {
    loading.value = false
  }
}

async function toggleReport(report) {
  if (expandedId.value === report.id) {
    expandedId.value = null
    expandedContent.value = null
    return
  }
  expandedId.value = report.id
  expandedContent.value = null
  loadingDetail.value = true
  try {
    let detail
    if (activeTab.value === 'daily') {
      detail = await getDailyReportDetail(report.id)
    } else {
      detail = await getWeeklyReportDetail(report.id)
    }
    if (detail) {
      expandedContent.value = detail.content
    }
  } finally {
    loadingDetail.value = false
  }
}

function switchTab(tab) {
  if (activeTab.value === tab) return
  activeTab.value = tab
  loadList(tab)
}

async function handleGenerate() {
  generating.value = true
  try {
    if (activeTab.value === 'daily') {
      await triggerDailyReport()
    } else {
      await triggerWeeklyReport()
    }
    // Reload list after generation
    await loadList(activeTab.value)
  } finally {
    generating.value = false
  }
}

function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const hour = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${month}-${day} ${hour}:${min}`
}

onMounted(() => loadList('daily'))
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Reports</h1>
      <button class="generate-btn" @click="handleGenerate" :disabled="generating">
        {{ generating ? 'Generating...' : 'Generate' }}
      </button>
    </div>

    <!-- Tab Bar -->
    <div class="tab-bar">
      <button :class="['tab-btn', { active: activeTab === 'daily' }]" @click="switchTab('daily')">Daily</button>
      <button :class="['tab-btn', { active: activeTab === 'weekly' }]" @click="switchTab('weekly')">Weekly</button>
    </div>

    <!-- Loading -->
    <div v-if="loading" class="loading">Loading</div>

    <!-- Empty -->
    <div v-else-if="!reports.length" class="empty">No reports yet. Click "Generate" to create one.</div>

    <!-- Report List -->
    <div v-else class="report-list">
      <div v-for="r in reports" :key="r.id" class="report-item" :class="{ expanded: expandedId === r.id }">
        <!-- Collapsed Header -->
        <div class="report-item-header" @click="toggleReport(r)">
          <div class="report-item-left">
            <span class="report-date">{{ formatDate(r.generated_at) }}</span>
            <span class="report-type-badge">{{ activeTab === 'daily' ? 'Daily' : 'Weekly' }}</span>
          </div>
          <div class="report-item-summary">{{ r.summary || '' }}</div>
          <span class="expand-icon">{{ expandedId === r.id ? '▼' : '▶' }}</span>
        </div>

        <!-- Expanded Content -->
        <div v-if="expandedId === r.id" class="report-item-content">
          <div v-if="loadingDetail" class="loading">Loading report...</div>
          <template v-else-if="expandedContent">
            <DailyReportView v-if="activeTab === 'daily'" :content="expandedContent" />
            <WeeklyReportView v-else :content="expandedContent" />
          </template>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.generate-btn {
  background: rgba(79, 195, 247, 0.15);
  color: #4fc3f7;
  border: 1px solid rgba(79, 195, 247, 0.3);
  padding: 8px 20px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 600;
  transition: all 0.2s;
}
.generate-btn:hover:not(:disabled) {
  background: rgba(79, 195, 247, 0.25);
}
.generate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.tab-bar {
  display: flex;
  gap: 0;
  margin-bottom: 20px;
  border-bottom: 2px solid rgba(255,255,255,0.06);
}
.tab-btn {
  background: none;
  border: none;
  color: var(--text-muted);
  font-size: 15px;
  font-weight: 600;
  padding: 10px 24px;
  cursor: pointer;
  border-bottom: 2px solid transparent;
  margin-bottom: -2px;
  transition: color 0.2s, border-color 0.2s;
}
.tab-btn:hover { color: var(--text); }
.tab-btn.active { color: #4fc3f7; border-bottom-color: #4fc3f7; }

.report-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.report-item {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  overflow: hidden;
}
.report-item.expanded {
  border-color: rgba(79, 195, 247, 0.3);
}
.report-item-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  cursor: pointer;
  transition: background 0.2s;
}
.report-item-header:hover {
  background: var(--bg-hover);
}
.report-item-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}
.report-date {
  font-size: 13px;
  color: var(--text-muted);
  font-family: monospace;
  min-width: 80px;
}
.report-type-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(79, 195, 247, 0.15);
  color: #4fc3f7;
  font-weight: 600;
}
.report-item-summary {
  flex: 1;
  font-size: 13px;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.expand-icon {
  color: var(--text-muted);
  font-size: 12px;
  flex-shrink: 0;
}
.report-item-content {
  padding: 16px;
  border-top: 1px solid var(--border);
  max-width: 100%;
  overflow-x: hidden;
}
</style>
