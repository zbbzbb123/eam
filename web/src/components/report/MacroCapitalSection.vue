<script setup>
import { computed } from 'vue'
import ScoreGauge from './ScoreGauge.vue'

const props = defineProps({ data: { type: Object, required: true } })

const d = computed(() => props.data)

const nbFlowColor = computed(() => {
  const flow = d.value.northbound_weekly_flow || 0
  return flow >= 0 ? 'var(--green)' : 'var(--red)'
})

const trendBadgeColor = computed(() => {
  const trend = d.value.northbound_trend || ''
  if (trend.includes('积极')) return 'var(--green)'
  if (trend.includes('撤退')) return 'var(--red)'
  return 'var(--blue)'
})
</script>

<template>
  <div>
    <h2 class="section-title">宏观环境 + 资金流向</h2>

    <!-- Macro Scores -->
    <div class="macro-scores">
      <div class="gauge-wrap" v-if="d.us_score != null">
        <ScoreGauge :score="d.us_score" size="small" label="美国宏观" />
        <p class="gauge-summary">{{ d.us_summary }}</p>
      </div>
      <div class="gauge-wrap" v-if="d.cn_score != null">
        <ScoreGauge :score="d.cn_score" size="small" label="中国宏观" />
        <p class="gauge-summary">{{ d.cn_summary }}</p>
      </div>
    </div>

    <!-- Northbound Flow -->
    <div class="nb-flow card-section">
      <h3>北向资金</h3>
      <div class="nb-data">
        <span class="nb-value" :style="{ color: nbFlowColor }">
          {{ (d.northbound_weekly_flow || 0) >= 0 ? '+' : '' }}{{ (d.northbound_weekly_flow || 0).toFixed(1) }} 亿
        </span>
        <span class="nb-trend" :style="{ background: `${trendBadgeColor}20`, color: trendBadgeColor }">
          {{ d.northbound_trend || '未知' }}
        </span>
      </div>
    </div>

    <!-- Sector Flows -->
    <div class="sector-flows card-section" v-if="d.sector_inflow_top5?.length || d.sector_outflow_top5?.length">
      <h3>板块资金</h3>
      <div class="flow-cols">
        <div v-if="d.sector_inflow_top5?.length" class="flow-col">
          <span class="flow-col-title" style="color: var(--green)">流入前5</span>
          <div v-for="s in d.sector_inflow_top5" :key="s.name" class="flow-item">
            <span>{{ s.name }}</span>
            <span style="color: var(--green)">+{{ s.flow?.toFixed(1) }}亿</span>
          </div>
        </div>
        <div v-if="d.sector_outflow_top5?.length" class="flow-col">
          <span class="flow-col-title" style="color: var(--red)">流出前5</span>
          <div v-for="s in d.sector_outflow_top5" :key="s.name" class="flow-item">
            <span>{{ s.name }}</span>
            <span style="color: var(--red)">{{ s.flow?.toFixed(1) }}亿</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Key Events -->
    <div class="key-events card-section" v-if="d.key_events?.length">
      <h3>本周关键事件</h3>
      <ul>
        <li v-for="(e, i) in d.key_events" :key="i">{{ e }}</li>
      </ul>
    </div>
  </div>
</template>

<style scoped>
.section-title {
  font-size: 16px;
  color: var(--text);
  margin: 24px 0 12px;
  font-weight: 600;
}
.macro-scores {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}
.gauge-wrap {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  text-align: center;
}
.gauge-summary {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 8px;
  line-height: 1.4;
}
.card-section {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px;
  margin-bottom: 12px;
}
.card-section h3 {
  font-size: 14px;
  color: var(--text);
  margin: 0 0 10px;
  font-weight: 600;
}
.nb-data {
  display: flex;
  align-items: center;
  gap: 12px;
}
.nb-value {
  font-size: 20px;
  font-weight: 700;
}
.nb-trend {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 4px;
  font-weight: 600;
}
.flow-cols {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.flow-col-title {
  font-size: 12px;
  font-weight: 600;
  display: block;
  margin-bottom: 6px;
}
.flow-item {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  color: var(--text);
  padding: 3px 0;
}
.key-events ul {
  margin: 0;
  padding-left: 18px;
}
.key-events li {
  font-size: 13px;
  color: var(--text);
  line-height: 1.6;
}
</style>
