<script setup>
import { computed } from 'vue'

const props = defineProps({ summary: { type: Object, required: true } })

const todayColor = computed(() => (props.summary.today_pnl || 0) >= 0 ? 'var(--green)' : 'var(--red)')
const totalColor = computed(() => (props.summary.total_pnl || 0) >= 0 ? 'var(--green)' : 'var(--red)')

function formatMoney(v) {
  if (v == null) return '--'
  return v.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}
function formatPct(v) {
  if (v == null) return '--'
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}
</script>

<template>
  <div class="summary-card">
    <div class="total-value">
      <span class="label">总市值</span>
      <span class="value">¥{{ formatMoney(summary.total_value_cny) }}</span>
    </div>
    <div class="pnl-row">
      <div class="pnl-item">
        <span class="label">今日盈亏</span>
        <span class="value" :style="{ color: todayColor }">
          {{ (summary.today_pnl >= 0 ? '+' : '') }}{{ formatMoney(summary.today_pnl) }}
          <small>{{ formatPct(summary.today_pnl_pct) }}</small>
        </span>
      </div>
      <div class="pnl-item">
        <span class="label">累计盈亏</span>
        <span class="value" :style="{ color: totalColor }">
          {{ (summary.total_pnl >= 0 ? '+' : '') }}{{ formatMoney(summary.total_pnl) }}
          <small>{{ formatPct(summary.total_pnl_pct) }}</small>
        </span>
      </div>
      <div class="pnl-item">
        <span class="label">持仓数</span>
        <span class="value">{{ summary.holdings_count }}</span>
      </div>
      <div class="pnl-item">
        <span class="label">现金比例</span>
        <span class="value">{{ (summary.cash_pct || 0).toFixed(1) }}%</span>
      </div>
    </div>
    <div v-if="summary.ai_summary" class="ai-summary">
      {{ summary.ai_summary }}
    </div>
  </div>
</template>

<style scoped>
.summary-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 20px;
}
.total-value {
  display: flex;
  flex-direction: column;
  margin-bottom: 16px;
}
.total-value .label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}
.total-value .value {
  font-size: 28px;
  font-weight: 700;
  color: var(--text);
}
.pnl-row {
  display: flex;
  gap: 24px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.pnl-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.pnl-item .label {
  font-size: 12px;
  color: var(--text-muted);
}
.pnl-item .value {
  font-size: 16px;
  font-weight: 600;
  color: var(--text);
}
.pnl-item .value small {
  font-size: 12px;
  margin-left: 4px;
  font-weight: 400;
}
.ai-summary {
  font-size: 14px;
  color: var(--text);
  font-style: italic;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  line-height: 1.5;
}
</style>
