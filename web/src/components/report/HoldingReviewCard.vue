<script setup>
import { ref, computed } from 'vue'

const props = defineProps({ holding: { type: Object, required: true } })
const showDetail = ref(false)

const h = computed(() => props.holding)

const actionLabel = { hold: '持有', add: '加仓', reduce: '减仓', sell: '卖出' }
const actionColor = {
  hold: 'var(--blue)', add: 'var(--green)',
  reduce: 'var(--orange)', sell: 'var(--red)',
}
const tierLabel = { stable: '稳健', medium: '进取', gamble: '投机' }
const marketBadgeColor = { US: '#448aff', HK: '#00c853', CN: '#ff9800' }

function formatPct(v) {
  if (v == null) return '--'
  return (v >= 0 ? '+' : '') + v.toFixed(2) + '%'
}
function formatMoney(v) {
  if (v == null) return '--'
  return (v >= 0 ? '+' : '') + v.toLocaleString('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 0 })
}
</script>

<template>
  <div class="holding-card">
    <!-- Header -->
    <div class="holding-header">
      <div class="holding-info">
        <span class="symbol">{{ h.name || h.symbol }}</span>
        <span class="code">{{ h.symbol }}</span>
        <span class="badge market" :style="{ background: `${marketBadgeColor[h.market] || '#78909c'}20`, color: marketBadgeColor[h.market] || '#78909c' }">{{ h.market }}</span>
        <span class="badge tier">{{ tierLabel[h.tier] || h.tier }}</span>
      </div>
      <div class="holding-weight">
        <span class="action-badge" :style="{ background: `${actionColor[h.action] || actionColor.hold}20`, color: actionColor[h.action] || actionColor.hold }">
          {{ actionLabel[h.action] || '持有' }}
        </span>
        <span class="weight">{{ (h.weight_pct || 0).toFixed(1) }}%</span>
      </div>
    </div>

    <!-- Data Row -->
    <div class="holding-data">
      <div class="data-item">
        <span class="data-label">现价</span>
        <span class="data-value">{{ h.current_price?.toFixed(2) || '--' }}</span>
      </div>
      <div class="data-item">
        <span class="data-label">今日</span>
        <span class="data-value" :style="{ color: (h.today_change_pct || 0) >= 0 ? 'var(--green)' : 'var(--red)' }">
          {{ formatPct(h.today_change_pct) }}
        </span>
      </div>
      <div class="data-item">
        <span class="data-label">盈亏</span>
        <span class="data-value" :style="{ color: (h.total_pnl || 0) >= 0 ? 'var(--green)' : 'var(--red)' }">
          {{ formatMoney(h.total_pnl) }}
        </span>
      </div>
      <div class="data-item">
        <span class="data-label">盈亏%</span>
        <span class="data-value" :style="{ color: (h.total_pnl_pct || 0) >= 0 ? 'var(--green)' : 'var(--red)' }">
          {{ formatPct(h.total_pnl_pct) }}
        </span>
      </div>
      <div class="data-item">
        <span class="data-label">成本</span>
        <span class="data-value">{{ h.avg_cost?.toFixed(2) || '--' }}</span>
      </div>
    </div>

    <!-- Warnings -->
    <div v-if="h.near_stop_loss" class="warning stop-loss">
      接近止损位 ¥{{ h.stop_loss_price }}
    </div>
    <div v-if="h.near_take_profit" class="warning take-profit">
      接近止盈位 ¥{{ h.take_profit_price }}
    </div>

    <!-- AI Comment -->
    <div v-if="h.ai_comment" class="ai-comment">
      {{ h.ai_comment }}
    </div>

    <!-- Expand Detail -->
    <div v-if="h.ai_detail" class="detail-toggle" @click="showDetail = !showDetail">
      {{ showDetail ? '收起详细分析 ▲' : '查看详细分析 ▼' }}
    </div>
    <div v-if="showDetail && h.ai_detail" class="ai-detail">
      {{ h.ai_detail }}
    </div>
  </div>
</template>

<style scoped>
.holding-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
}
.holding-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.holding-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.symbol {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
.code {
  font-size: 12px;
  color: var(--text-muted);
}
.badge {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 4px;
  font-weight: 600;
}
.badge.tier {
  background: rgba(255,255,255,0.06);
  color: var(--text-muted);
}
.holding-weight {
  display: flex;
  align-items: center;
  gap: 10px;
}
.action-badge {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 4px;
  font-weight: 600;
}
.weight {
  font-size: 13px;
  color: var(--text-muted);
  font-weight: 600;
}
.holding-data {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.data-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.data-label {
  font-size: 11px;
  color: var(--text-muted);
}
.data-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}
.warning {
  font-size: 12px;
  padding: 6px 10px;
  border-radius: 4px;
  margin-bottom: 8px;
  font-weight: 600;
}
.warning.stop-loss {
  background: rgba(255,82,82,0.1);
  color: var(--red);
  border-left: 3px solid var(--red);
}
.warning.take-profit {
  background: rgba(0,200,83,0.1);
  color: var(--green);
  border-left: 3px solid var(--green);
}
.ai-comment {
  font-size: 13px;
  color: var(--text);
  line-height: 1.6;
  padding: 10px 0;
  border-top: 1px solid var(--border);
}
.detail-toggle {
  font-size: 12px;
  color: #4fc3f7;
  cursor: pointer;
  padding: 6px 0;
  user-select: none;
}
.detail-toggle:hover {
  text-decoration: underline;
}
.ai-detail {
  font-size: 13px;
  color: var(--text-muted);
  white-space: pre-wrap;
  line-height: 1.6;
  padding: 12px;
  background: var(--bg-dark);
  border-radius: 6px;
  margin-top: 8px;
}
</style>
