<script setup>
import { computed } from 'vue'

const props = defineProps({ summary: { type: Object, required: true } })

const pnlColor = computed(() => (props.summary.week_pnl || 0) >= 0 ? 'var(--green)' : 'var(--red)')

function formatMoney(v) {
  if (v == null) return '--'
  return (v >= 0 ? '+' : '') + v.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}
function formatPct(v) {
  if (v == null) return '--'
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}
</script>

<template>
  <div class="week-card">
    <div class="week-header">
      <span class="week-range">{{ summary.week_start }} ~ {{ summary.week_end }}</span>
    </div>

    <div class="week-pnl">
      <span class="label">本周盈亏</span>
      <span class="value" :style="{ color: pnlColor }">
        {{ formatMoney(summary.week_pnl) }}
        <small>{{ formatPct(summary.week_pnl_pct) }}</small>
      </span>
    </div>

    <div class="best-worst">
      <div v-if="summary.best_holding" class="bw-item best">
        <span class="bw-label">本周最佳</span>
        <span class="bw-symbol">{{ summary.best_holding.symbol }}</span>
        <span class="bw-pct" style="color: var(--green)">{{ formatPct(summary.best_holding.pnl_pct) }}</span>
      </div>
      <div v-if="summary.worst_holding" class="bw-item worst">
        <span class="bw-label">本周最差</span>
        <span class="bw-symbol">{{ summary.worst_holding.symbol }}</span>
        <span class="bw-pct" style="color: var(--red)">{{ formatPct(summary.worst_holding.pnl_pct) }}</span>
      </div>
    </div>

    <div v-if="summary.ai_summary" class="ai-summary">
      {{ summary.ai_summary }}
    </div>
  </div>
</template>

<style scoped>
.week-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
}
.week-header {
  margin-bottom: 12px;
}
.week-range {
  font-size: 13px;
  color: var(--text-muted);
  font-family: monospace;
}
.week-pnl {
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 16px;
}
.week-pnl .label {
  font-size: 12px;
  color: var(--text-muted);
}
.week-pnl .value {
  font-size: 24px;
  font-weight: 700;
}
.week-pnl .value small {
  font-size: 14px;
  margin-left: 6px;
  font-weight: 400;
}
.best-worst {
  display: flex;
  gap: 20px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.bw-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-dark);
  border-radius: 6px;
}
.bw-label {
  font-size: 11px;
  color: var(--text-muted);
}
.bw-symbol {
  font-size: 13px;
  font-weight: 600;
  color: var(--text);
}
.bw-pct {
  font-size: 13px;
  font-weight: 600;
}
.ai-summary {
  font-size: 14px;
  color: var(--text);
  line-height: 1.6;
  padding-top: 12px;
  border-top: 1px solid var(--border);
}
</style>
