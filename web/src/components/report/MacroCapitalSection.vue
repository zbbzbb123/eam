<script setup>
import { computed } from 'vue'
import ScoreGauge from './ScoreGauge.vue'

const props = defineProps({ data: { type: Object, required: true } })

const d = computed(() => props.data)

const nbVolChangeColor = computed(() => {
  const pct = d.value.northbound_detail?.vol_change_pct || 0
  return pct >= 0 ? 'var(--green)' : 'var(--red)'
})

const trendBadgeColor = computed(() => {
  const trend = d.value.northbound_trend || ''
  if (trend === '活跃') return 'var(--green)'
  if (trend === '清淡') return 'var(--red)'
  return 'var(--blue)'
})

// Commodity display names
const commodityNames = {
  'GC=F': '黄金', 'SI=F': '白银', 'CL=F': '原油', 'HG=F': '铜', '^VIX': 'VIX'
}

function formatPct(v, sign = true) {
  if (v == null) return '--'
  const prefix = sign && v >= 0 ? '+' : ''
  return prefix + v.toFixed(1) + '%'
}

function percentileColor(pct) {
  if (pct == null) return 'var(--text-muted)'
  if (pct >= 80) return 'var(--red)'
  if (pct >= 60) return 'var(--orange)'
  if (pct <= 20) return 'var(--green)'
  return 'var(--blue)'
}
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

    <!-- Northbound Trading Volume -->
    <div class="nb-flow card-section" v-if="d.northbound_detail?.today_volume">
      <h3>北向交易额</h3>
      <div class="nb-data">
        <div class="nb-main">
          <span class="nb-label">最新日交易额 ({{ d.northbound_detail.today_date }})</span>
          <span class="nb-value" style="color: var(--text)">
            {{ (d.northbound_detail.today_volume || 0).toFixed(1) }} 亿
          </span>
        </div>
        <span class="nb-trend" :style="{ background: `${trendBadgeColor}20`, color: trendBadgeColor }">
          {{ d.northbound_trend || '未知' }}
        </span>
      </div>
      <!-- Volume breakdown and trend -->
      <div class="nb-detail">
        <div class="nb-detail-item">
          <span class="nb-detail-label">沪股通</span>
          <span class="nb-detail-value" style="color: var(--text)">
            {{ (d.northbound_detail.today_hgt || 0).toFixed(1) }} 亿
          </span>
        </div>
        <div class="nb-detail-item">
          <span class="nb-detail-label">深股通</span>
          <span class="nb-detail-value" style="color: var(--text)">
            {{ (d.northbound_detail.today_sgt || 0).toFixed(1) }} 亿
          </span>
        </div>
        <div class="nb-detail-item">
          <span class="nb-detail-label">日环比</span>
          <span class="nb-detail-value" :style="{ color: nbVolChangeColor }">
            {{ (d.northbound_detail.vol_change_pct || 0) >= 0 ? '+' : '' }}{{ (d.northbound_detail.vol_change_pct || 0).toFixed(1) }}%
          </span>
        </div>
        <div class="nb-detail-item">
          <span class="nb-detail-label">5日均量</span>
          <span class="nb-detail-value" style="color: var(--text)">
            {{ (d.northbound_detail.avg_5d_volume || 0).toFixed(1) }} 亿
          </span>
        </div>
        <div class="nb-detail-item">
          <span class="nb-detail-label">周均量</span>
          <span class="nb-detail-value" style="color: var(--text)">
            {{ (d.northbound_detail.week_avg_volume || 0).toFixed(1) }} 亿
          </span>
        </div>
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

    <!-- Yield Spread -->
    <div class="yield-spread card-section" v-if="d.yield_spread">
      <h3>美债利差 (10Y-2Y)</h3>
      <div class="yield-data">
        <span class="yield-value" :style="{ color: d.yield_spread.is_inverted ? 'var(--red)' : 'var(--green)' }">
          {{ d.yield_spread.spread?.toFixed(2) }}%
        </span>
        <span class="yield-status" :class="{ inverted: d.yield_spread.is_inverted }">
          {{ d.yield_spread.is_inverted ? '倒挂' : '正常' }}
        </span>
      </div>
      <div class="yield-detail">
        <span>2Y: {{ d.yield_spread.dgs2?.toFixed(2) }}%</span>
        <span>10Y: {{ d.yield_spread.dgs10?.toFixed(2) }}%</span>
      </div>
    </div>

    <!-- Index Valuations -->
    <div class="index-vals card-section" v-if="d.index_valuations?.length">
      <h3>A股估值</h3>
      <div class="index-grid">
        <div v-for="idx in d.index_valuations" :key="idx.ts_code" class="index-item">
          <span class="index-name">{{ idx.name || idx.ts_code }}</span>
          <div class="index-pe">
            <span class="pe-value">PE {{ idx.pe?.toFixed(1) }}</span>
            <span class="pe-pct" :style="{ color: percentileColor(idx.pe_percentile) }">
              历史{{ idx.pe_percentile }}%分位
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Market Breadth -->
    <div class="market-breadth card-section" v-if="d.market_breadth?.length">
      <h3>市场宽度</h3>
      <div class="breadth-grid">
        <div v-for="b in d.market_breadth" :key="b.index_code" class="breadth-item">
          <span class="breadth-name">{{ b.index_name || b.index_code }}</span>
          <div class="breadth-data">
            <span class="adv" style="color: var(--green)">涨{{ b.advancing }}</span>
            <span class="dec" style="color: var(--red)">跌{{ b.declining }}</span>
            <span class="ratio" v-if="b.declining > 0">
              ({{ (b.advancing / b.declining).toFixed(2) }})
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Commodities -->
    <div class="commodities card-section" v-if="d.commodities?.length">
      <h3>大宗商品</h3>
      <div class="commodity-grid">
        <div v-for="c in d.commodities" :key="c.symbol" class="commodity-item">
          <span class="commodity-name">{{ c.name || commodityNames[c.symbol] || c.symbol }}</span>
          <span class="commodity-price">{{ c.value?.toFixed(2) }}</span>
          <span class="commodity-change" :style="{ color: (c.change_pct || 0) >= 0 ? 'var(--green)' : 'var(--red)' }">
            {{ formatPct(c.change_pct) }}
          </span>
          <span class="commodity-pct" v-if="c.percentile_60d != null" :style="{ color: percentileColor(c.percentile_60d) }">
            60日{{ c.percentile_60d }}%
          </span>
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
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.nb-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.nb-label {
  font-size: 11px;
  color: var(--text-muted);
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
.nb-detail {
  display: flex;
  gap: 20px;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border);
  flex-wrap: wrap;
}
.nb-detail-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.nb-detail-label {
  font-size: 11px;
  color: var(--text-muted);
}
.nb-detail-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text);
}
.flow-cols {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
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
/* Yield Spread */
.yield-data {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}
.yield-value {
  font-size: 20px;
  font-weight: 700;
}
.yield-status {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 4px;
  font-weight: 600;
  background: rgba(0,200,83,0.15);
  color: var(--green);
}
.yield-status.inverted {
  background: rgba(255,82,82,0.15);
  color: var(--red);
}
.yield-detail {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--text-muted);
}
/* Index Valuations */
.index-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}
.index-item {
  background: var(--bg-dark);
  padding: 12px;
  border-radius: 6px;
}
.index-name {
  font-size: 13px;
  color: var(--text);
  font-weight: 600;
  display: block;
  margin-bottom: 6px;
}
.index-pe {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pe-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
}
.pe-pct {
  font-size: 12px;
  font-weight: 600;
}
/* Market Breadth */
.breadth-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 12px;
}
.breadth-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--bg-dark);
  border-radius: 6px;
}
.breadth-name {
  font-size: 13px;
  color: var(--text);
  font-weight: 600;
}
.breadth-data {
  display: flex;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
}
.breadth-data .ratio {
  color: var(--text-muted);
}
/* Commodities */
.commodity-grid {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.commodity-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-dark);
  border-radius: 6px;
  font-size: 13px;
}
.commodity-name {
  font-weight: 600;
  color: var(--text);
  min-width: 50px;
}
.commodity-price {
  color: var(--text);
  font-weight: 600;
}
.commodity-change {
  font-weight: 600;
  min-width: 60px;
  text-align: right;
}
.commodity-pct {
  font-size: 11px;
  font-weight: 600;
  min-width: 60px;
  text-align: right;
}
</style>
