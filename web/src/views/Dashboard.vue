<script setup>
import { ref, onMounted } from 'vue'
import SignalCard from '../components/SignalCard.vue'
import {
  getDashboard, getSignals, getWeeklyReportList,
  getStrategyTargets, updateStrategyTargets, getRebalancePlan,
} from '../api'

const dashboard = ref(null)
const signals = ref([])
const latestWeekly = ref(null)
const strategyTargets = ref([])
const rebalancePlan = ref(null)
const loading = ref(true)
const dashboardMode = ref('strategy')
const dashboardLoading = ref(false)
const savingTargets = ref(false)
const targetError = ref('')

function threeDaysAgo() {
  const d = new Date()
  d.setDate(d.getDate() - 3)
  return d.toISOString()
}

onMounted(async () => {
  const [dash, sigs, weeklyList, targets, rebalance] = await Promise.all([
    getDashboard({ group_by: dashboardMode.value }),
    getSignals({ since: threeDaysAgo(), limit: 50 }),
    getWeeklyReportList(1),
    getStrategyTargets(),
    getRebalancePlan(),
  ])
  dashboard.value = dash
  signals.value = Array.isArray(sigs) ? sigs : []
  latestWeekly.value = Array.isArray(weeklyList) && weeklyList.length ? weeklyList[0] : null
  strategyTargets.value = Array.isArray(targets) ? targets : []
  rebalancePlan.value = rebalance
  loading.value = false
})

async function loadDashboard() {
  dashboardLoading.value = true
  try {
    dashboard.value = await getDashboard({ group_by: dashboardMode.value })
  } finally {
    dashboardLoading.value = false
  }
}

function fmt(v) {
  const n = Number(v) || 0
  return n.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
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
  const m = {
    core: 'Core 风险',
    growth: 'Growth 风险',
    gamble: 'Gamble 风险',
    ai_infrastructure: 'AI基础设施',
    ai_application: 'AI应用个股',
    misc: '杂票',
    cash: '现金',
  }
  return m[t] || t
}

async function setDashboardMode(mode) {
  if (dashboardMode.value === mode || dashboardLoading.value) return
  dashboardMode.value = mode
  await loadDashboard()
}

function actionLabel(action) {
  const m = { increase: '补足', reduce: '降低', hold: '保持' }
  return m[action] || action
}

function severityClass(severity) {
  return `severity-${severity || 'ok'}`
}

function formatDate(d) {
  if (!d) return ''
  return new Date(d).toLocaleDateString('en-US')
}

function truncate(text, len = 120) {
  if (!text) return ''
  return text.length > len ? text.slice(0, len) + '...' : text
}

async function saveTargets() {
  savingTargets.value = true
  targetError.value = ''
  try {
    const payload = strategyTargets.value.map(t => ({
      bucket: t.bucket,
      target_pct: Number(t.target_pct),
    }))
    strategyTargets.value = await updateStrategyTargets(payload)
    rebalancePlan.value = await getRebalancePlan()
    await loadDashboard()
  } catch (e) {
    targetError.value = e.response?.data?.detail || '目标仓位保存失败'
  } finally {
    savingTargets.value = false
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Dashboard</h1>
      <p>AI Theme Portfolio</p>
      <div class="view-switch">
        <button
          type="button"
          :class="{ active: dashboardMode === 'strategy' }"
          :disabled="dashboardLoading"
          @click="setDashboardMode('strategy')"
        >
          AI Structure
        </button>
        <button
          type="button"
          :class="{ active: dashboardMode === 'cgg' }"
          :disabled="dashboardLoading"
          @click="setDashboardMode('cgg')"
        >
          CGG Risk
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading</div>

    <template v-else>
      <!-- Section 1: 持仓概览 -->
      <div class="tier-grid" :class="{ refreshing: dashboardLoading }">
        <!-- 总持仓卡片 -->
        <div class="card tier-card total-card">
          <div class="tier-header">
            <span class="tier-title">Total Portfolio</span>
          </div>
          <div class="tier-value">¥{{ fmt(dashboard.total_value) }}</div>
          <div class="pnl-row">
            <div class="pnl-item">
              <span class="pnl-label">7D</span>
              <span :class="pnlClass(dashboard.pnl_7d)">
                {{ pnlSign(dashboard.pnl_7d) }}{{ fmt(dashboard.pnl_7d) }}
                <small>({{ pnlSign(dashboard.pnl_7d_pct) }}{{ fmt(dashboard.pnl_7d_pct) }}%)</small>
              </span>
            </div>
            <div class="pnl-item">
              <span class="pnl-label">30D</span>
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
            <small class="weight-label">{{ fmt(tier.weight_pct) }}% of total</small>
          </div>
          <div class="pnl-row">
            <div class="pnl-item">
              <span class="pnl-label">7D</span>
              <span :class="pnlClass(tier.pnl_7d)">
                {{ pnlSign(tier.pnl_7d) }}{{ fmt(tier.pnl_7d) }}
                <small>({{ pnlSign(tier.pnl_7d_pct) }}{{ fmt(tier.pnl_7d_pct) }}%)</small>
              </span>
            </div>
            <div class="pnl-item">
              <span class="pnl-label">30D</span>
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
                <th>Stock</th>
                <th>Value</th>
                <th>Weight</th>
                <th>7D P&L</th>
                <th>30D P&L</th>
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
          <div v-else class="empty">No holdings</div>
        </div>
      </div>

      <!-- Section 2: Strategy targets and rebalance -->
      <div v-if="dashboardMode === 'strategy'" class="grid-2" style="margin-top:20px">
        <div class="card">
          <div class="card-title">Strategy Targets</div>
          <div class="target-grid">
            <label v-for="t in strategyTargets" :key="t.bucket" class="target-row">
              <span>{{ tierLabel(t.bucket) }}</span>
              <input v-model="t.target_pct" type="number" min="0" max="100" step="0.1" />
              <small>actual {{ fmt(t.actual_pct) }}%</small>
            </label>
          </div>
          <div v-if="targetError" class="form-error">{{ targetError }}</div>
          <button class="save-targets" :disabled="savingTargets" @click="saveTargets">
            {{ savingTargets ? 'Saving...' : 'Save Targets' }}
          </button>
        </div>

        <div class="card">
          <div class="card-title">
            Rebalance Plan
            <span v-if="rebalancePlan?.needs_trade" class="status-pill critical">强提醒</span>
            <span v-else-if="rebalancePlan?.needs_rebalance" class="status-pill warning">预警</span>
            <span v-else class="status-pill ok">正常</span>
          </div>
          <div v-if="!rebalancePlan?.buckets?.length" class="empty">No rebalance data</div>
          <table v-else class="rebalance-table">
            <thead>
              <tr>
                <th>Bucket</th>
                <th>Target</th>
                <th>Actual</th>
                <th>Drift</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="b in rebalancePlan.buckets" :key="b.bucket" :class="severityClass(b.severity)">
                <td>{{ tierLabel(b.bucket) }}</td>
                <td>{{ fmt(b.target_pct) }}%</td>
                <td>{{ fmt(b.actual_pct) }}%</td>
                <td>{{ fmt(b.relative_drift_pct || 0) }}%</td>
                <td>{{ actionLabel(b.action) }} ¥{{ fmt(b.trade_amount_cny) }}</td>
              </tr>
            </tbody>
          </table>
          <div v-if="rebalancePlan?.holdings?.length" class="holding-alerts">
            <div class="mini-title">Holding Alerts</div>
            <div v-for="h in rebalancePlan.holdings" :key="h.holding_id" class="holding-alert" :class="severityClass(h.severity)">
              <span>{{ h.symbol }}</span>
              <span>{{ fmt(h.actual_pct) }}% / target {{ fmt(h.target_pct) }}%</span>
              <span>{{ actionLabel(h.action) }} ¥{{ fmt(h.trade_amount_cny) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Section 2: 最近信号 -->
      <div class="card" style="margin-top:20px">
        <div class="card-title">Recent Signals (3 days)</div>
        <div v-if="!signals.length" class="empty">No signals</div>
        <SignalCard v-for="s in signals" :key="s.id" :signal="s" />
      </div>

      <!-- Section 3: 最新周报 -->
      <div class="grid-2" style="margin-top:20px">
        <div class="card">
          <div class="card-title">Latest Weekly Report</div>
          <template v-if="latestWeekly">
            <div class="report-date">{{ formatDate(latestWeekly.report_date || latestWeekly.generated_at) }}</div>
            <div class="report-summary">{{ truncate(latestWeekly.summary) }}</div>
            <router-link to="/reports" class="report-link">View details &rarr;</router-link>
          </template>
          <div v-else class="empty">No weekly reports</div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.view-switch {
  display: inline-flex;
  gap: 2px;
  padding: 3px;
  margin-top: 8px;
  background: #111a2c;
  border: 1px solid #263653;
  border-radius: 7px;
}

.view-switch button {
  min-width: 108px;
  border: none;
  border-radius: 5px;
  padding: 6px 10px;
  background: transparent;
  color: #8f9bb0;
  font-size: 12px;
  font-weight: 700;
  cursor: pointer;
}

.view-switch button.active {
  background: #263653;
  color: #fff;
}

.view-switch button:disabled {
  cursor: wait;
  opacity: 0.75;
}

.tier-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

.tier-grid.refreshing {
  opacity: 0.65;
  pointer-events: none;
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
.badge-ai_infrastructure { background: #1976d2; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge-ai_application { background: #7b1fa2; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge-misc { background: #607d8b; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }
.badge-cash { background: #2e7d32; color: #fff; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; }

.target-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 10px 14px;
}

.target-row {
  display: grid;
  grid-template-columns: minmax(92px, 1fr) 74px;
  align-items: center;
  gap: 8px;
  color: #c8d0dc;
  font-size: 13px;
}

.target-row input {
  width: 74px;
  background: #15223a;
  color: #fff;
  border: 1px solid #2a3a5e;
  border-radius: 6px;
  padding: 6px 8px;
}

.target-row small {
  grid-column: 1 / -1;
  color: #8892a4;
  font-size: 11px;
}

.save-targets {
  margin-top: 12px;
  background: #1976d2;
  color: #fff;
  border: none;
  border-radius: 6px;
  padding: 8px 14px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
}

.save-targets:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.form-error {
  margin-top: 8px;
  color: #ff5252;
  font-size: 13px;
}

.status-pill {
  margin-left: 8px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 700;
}

.status-pill.ok { background: rgba(0, 200, 83, 0.14); color: #00c853; }
.status-pill.warning { background: rgba(255, 152, 0, 0.16); color: #ffb74d; }
.status-pill.critical { background: rgba(255, 82, 82, 0.16); color: #ff5252; }

.rebalance-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

.rebalance-table th,
.rebalance-table td {
  padding: 7px 8px;
  border-bottom: 1px solid #1e2d4a;
  text-align: left;
  white-space: nowrap;
}

.rebalance-table th {
  color: #8892a4;
  font-weight: 500;
  font-size: 12px;
}

.severity-warning td { color: #ffcc80; }
.severity-critical td { color: #ff8a80; font-weight: 600; }

.holding-alerts {
  margin-top: 12px;
}

.mini-title {
  color: #8892a4;
  font-size: 12px;
  margin-bottom: 6px;
}

.holding-alert {
  display: grid;
  grid-template-columns: 72px 1fr auto;
  gap: 10px;
  font-size: 12px;
  padding: 6px 0;
  border-top: 1px solid #1e2d4a;
}

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
