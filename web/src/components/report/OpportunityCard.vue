<script setup>
import { ref, computed } from 'vue'

const props = defineProps({ opportunity: { type: Object, required: true } })
const showDetail = ref(false)

const o = computed(() => props.opportunity)

const timeframeColor = computed(() => o.value.timeframe === '长期' ? 'var(--green)' : 'var(--orange)')
const marketBadgeColor = { US: '#448aff', HK: '#00c853', CN: '#ff9800' }
</script>

<template>
  <div class="opp-card">
    <div class="opp-header">
      <div class="opp-info">
        <span class="symbol">{{ o.name || o.symbol }}</span>
        <span class="code">{{ o.symbol }}</span>
        <span class="badge market" :style="{ background: `${marketBadgeColor[o.market] || '#78909c'}20`, color: marketBadgeColor[o.market] || '#78909c' }">{{ o.market }}</span>
      </div>
      <div class="opp-badges">
        <span class="signal-badge">{{ o.signal_type || '机会' }}</span>
        <span class="timeframe-badge" :style="{ background: `${timeframeColor}20`, color: timeframeColor }">
          {{ o.timeframe || '短期' }}
        </span>
      </div>
    </div>

    <div v-if="o.current_price || o.target_price" class="price-row">
      <span v-if="o.current_price">现价: {{ o.current_price.toFixed(2) }}</span>
      <span v-if="o.target_price">目标价: {{ o.target_price.toFixed(2) }}</span>
    </div>

    <div class="reason">{{ o.reason }}</div>

    <div v-if="o.detail" class="detail-toggle" @click="showDetail = !showDetail">
      {{ showDetail ? '收起 ▲' : '详细分析 ▼' }}
    </div>
    <div v-if="showDetail && o.detail" class="opp-detail">{{ o.detail }}</div>
  </div>
</template>

<style scoped>
.opp-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-left: 3px solid var(--green);
  border-radius: var(--radius);
  padding: 14px 16px;
}
.opp-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}
.opp-info {
  display: flex;
  align-items: center;
  gap: 8px;
}
.symbol { font-size: 15px; font-weight: 600; color: var(--text); }
.code { font-size: 12px; color: var(--text-muted); }
.badge { font-size: 11px; padding: 2px 6px; border-radius: 4px; font-weight: 600; }
.opp-badges { display: flex; gap: 6px; }
.signal-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 4px;
  background: rgba(79,195,247,0.15); color: #4fc3f7; font-weight: 600;
}
.timeframe-badge {
  font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: 600;
}
.price-row {
  display: flex; gap: 16px;
  font-size: 13px; color: var(--text-muted); margin-bottom: 8px;
}
.reason { font-size: 13px; color: var(--text); line-height: 1.5; }
.detail-toggle {
  font-size: 12px; color: #4fc3f7; cursor: pointer;
  padding: 6px 0; user-select: none;
}
.detail-toggle:hover { text-decoration: underline; }
.opp-detail {
  font-size: 13px; color: var(--text-muted); white-space: pre-wrap;
  line-height: 1.6; padding: 12px; background: var(--bg-dark);
  border-radius: 6px; margin-top: 8px;
}
</style>
