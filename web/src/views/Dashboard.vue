<script setup>
import { ref, onMounted } from 'vue'
import SignalCard from '../components/SignalCard.vue'
import { getDashboard, getSignals, getDailyReportList, getWeeklyReportList } from '../api'

const dashboard = ref(null)
const signals = ref([])
const latestDaily = ref(null)
const latestWeekly = ref(null)
const loading = ref(true)

function threeDaysAgo() {
  const d = new Date()
  d.setDate(d.getDate() - 3)
  return d.toISOString()
}

onMounted(async () => {
  const [dash, sigs, dailyList, weeklyList] = await Promise.all([
    getDashboard(),
    getSignals({ since: threeDaysAgo(), limit: 50 }),
    getDailyReportList(1),
    getWeeklyReportList(1),
  ])
  dashboard.value = dash
  signals.value = Array.isArray(sigs) ? sigs : []
  latestDaily.value = Array.isArray(dailyList) && dailyList.length ? dailyList[0] : null
  latestWeekly.value = Array.isArray(weeklyList) && weeklyList.length ? weeklyList[0] : null
  loading.value = false
})

function fmt(v) {
  const n = Number(v) || 0
  return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
}

function pnlClass(v) {
  const n = Number(v) || 0
  if (n > 0) return 'pnl-pos'
  if (n < 0) return 'pnl-neg'
  return ''
}

function pnlSign(v) {
  const n = Number(v) || 0
  return n > 0 ? '+' : ''
}

function tierLabel(t) {
  const m = { core: 'Core', growth: 'Growth', gamble: 'Gamble' }
  return m[t] || t
}

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('zh-CN')
}

function truncate(text, len = 120) {
  if (!text) return ''
  return text.length > len ? text.slice(0, len) + '...' : text
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>仪表盘</h1>
      <p>投资组合概览</p>
    </div>

    <div v-if="loading" class="loading">加载中</div>

    <template v-else>
      <!-- Section 1: 持仓概览 -->
      <div class="tier-grid">
        <!-- 总持仓卡片 -->
        <div class="card tier-card total-card">
          <div class="tier-header">
            <span class="tier-title">总持仓</span>
          </div>
          <div class="tier-value">¥{{ fmt(dashboard.total_value) }}</div>
          <div class="pnl-row">
            <div class="pnl-item">
              <span class="pnl-label">7天</span>
              <span :class="pnlClass(dashboard.pnl_7d)">
                {{ pnlSign(dashboard.pnl_7d) }}{{ fmt(dashboard.pnl_7d) }}
                <small>({{ pnlSign(dashboard.pnl_7d_pct) }}{{ fmt(dashboard.pnl_7d_pct) }}%)</small>
              </span>
            </div>
            <div class="pnl-item">
              <span class="pnl-label">30天</span>
              <span :class="pnlClass(dashboard.pnl_30d)">
                {{ pnlSign(dashboard.pnl_30d) }}{{ fmt(dashboard.pnl_30d) }}
                <small>({{ pnlSign(dashboard.pnl_30d_pct) }}{{ fmt(dashboard.pnl_30d_pct) }}%)</small>
              </span>
            </div>
          </div>
        </div>

        <!-- Tier 卡片 -->
        <div v-for="tier in dashboard.tiers" :key="tier.tier" class="card tier-card">
          <div class="tier-header">
            <span class="tier-title">{{ tierLabel(tier.tier) }}</span>
            <span class="badge" :class="'badge-' + tier.tier">{{ tier.tier }}</span>
          </div>
          <div class="tier-value">
            ¥{{ fmt(tier.market_value) }}
            <small class="weight-label">占 {{ fmt(tier.weight_pct) }}%</small>
          </div>
          <div class="pnl-row">
            <div class="pnl-item">
              <span class="pnl-label">7天</span>
              <span :class="pnlClass(tier.pnl_7d)">
                {{ pnlSign(tier.pnl_7d) }}{{ fmt(tier.pnl_7d) }}
                <small>({{ pnlSign(tier.pnl_7d_pct) }}{{ fmt(tier.pnl_7d_pct) }}%)</small>
              </span>
            </div>
            <div class="pnl-item">
              <span class="pnl-label">30天</span>
              <span :class="pnlClass(tier.pnl_30d)">
                {{ pnlSign(tier.pnl_30d) }}{{ fmt(tier.pnl_30d) }}
                <small>({{ pnlSign(tier.pnl_30d_pct) }}{{ fmt(tier.pnl_30d_pct) }}%)</small>
              </span>
            </div>
          </div>

          <!-- Holdings table -->
          <table v-if="tier.holdings.length" class="holdings-table">
            <thead>
              <tr>
                <th>股票</th>
                <th>市值</th>
                <th>占比</th>
                <th>7天盈亏</th>
                <th>30天盈亏</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="h in tier.holdings" :key="h.id">
                <td class="stock-cell">
                  <span class="stock-symbol">{{ h.symbol }}</span>
                  <span v-if="h.name" class="stock-name">{{ h.name }}</span>
                </td>
                <td>¥{{ fmt(h.market_value) }}</td>
                <td>{{ fmt(h.weight_in_tier) }}%</td>
                <td :class="pnlClass(h.pnl_7d)">
                  {{ pnlSign(h.pnl_7d) }}{{ fmt(h.pnl_7d) }}
                  <small>({{ pnlSign(h.pnl_7d_pct) }}{{ fmt(h.pnl_7d_pct) }}%)</small>
                </td>
                <td :class="pnlClass(h.pnl_30d)">
                  {{ pnlSign(h.pnl_30d) }}{{ fmt(h.pnl_30d) }}
                  <small>({{ pnlSign(h.pnl_30d_pct) }}{{ fmt(h.pnl_30d_pct) }}%)</small>
                </td>
              </tr>
            </tbody>
          </table>
          <div v-else class="empty">暂无持仓</div>
        </div>
      </div>

      <!-- Section 2: 最近信号 -->
      <div class="card" style="margin-top:20px">
        <div class="card-title">最近3天信号</div>
        <div v-if="!signals.length" class="empty">暂无信号</div>
        <SignalCard v-for="s in signals" :key="s.id" :signal="s" />
      </div>

      <!-- Section 3: 最新报告 -->
      <div class="grid-2" style="margin-top:20px">
        <div class="card">
          <div class="card-title">最新日报</div>
          <template v-if="latestDaily">
            <div class="report-date">{{ formatDate(latestDaily.report_date || latestDaily.generated_at) }}</div>
            <div class="report-summary">{{ truncate(latestDaily.summary) }}</div>
            <router-link to="/reports" class="report-link">查看详情 &rarr;</router-link>
          </template>
          <div v-else class="empty">暂无日报</div>
        </div>
        <div class="card">
          <div class="card-title">最新周报</div>
          <template v-if="latestWeekly">
            <div class="report-date">{{ formatDate(latestWeekly.report_date || latestWeekly.generated_at) }}</div>
            <div class="report-summary">{{ truncate(latestWeekly.summary) }}</div>
            <router-link to="/reports" class="report-link">查看详情 &rarr;</router-link>
          </template>
          <div v-else class="empty">暂无周报</div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.tier-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.tier-card {
  padding: 16px;
}

.total-card {
  background: linear-gradient(135deg, #1a2744, #1e3a5f);
}

.tier-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.tier-title {
  font-size: 16px;
  font-weight: 600;
  color: #e0e6ed;
}

.tier-value {
  font-size: 22px;
  font-weight: 700;
  color: #fff;
  margin-bottom: 10px;
}

.weight-label {
  font-size: 13px;
  color: #8892a4;
  font-weight: 400;
  margin-left: 6px;
}

.pnl-row {
  display: flex;
  gap: 20px;
  margin-bottom: 12px;
}

.pnl-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
}

.pnl-label {
  color: #8892a4;
  font-size: 12px;
}

.pnl-pos { color: #00c853; }
.pnl-neg { color: #ff5252; }

.badge-core { background: #00c853; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge-growth { background: #ff9800; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge-gamble { background: #ff5252; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }

.holdings-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin-top: 4px;
}

.holdings-table th {
  text-align: left;
  color: #8892a4;
  font-weight: 500;
  padding: 6px 8px;
  border-bottom: 1px solid #2a3a5e;
  font-size: 12px;
}

.holdings-table td {
  padding: 6px 8px;
  color: #c8d0dc;
  border-bottom: 1px solid #1e2d4a;
  white-space: nowrap;
}

.holdings-table small {
  font-size: 11px;
  opacity: 0.8;
}

.stock-cell {
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.stock-symbol {
  font-weight: 600;
  color: #e0e6ed;
}

.stock-name {
  font-size: 11px;
  color: #8892a4;
}

.report-date {
  color: #8892a4;
  font-size: 13px;
  margin-bottom: 6px;
}

.report-summary {
  color: #c8d0dc;
  font-size: 13px;
  line-height: 1.6;
  margin-bottom: 10px;
}

.report-link {
  color: #4fc3f7;
  font-size: 13px;
  text-decoration: none;
}

.report-link:hover {
  text-decoration: underline;
}

@media (max-width: 768px) {
  .tier-grid {
    grid-template-columns: 1fr;
  }
}
</style>
