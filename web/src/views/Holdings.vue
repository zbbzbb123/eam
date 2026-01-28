<script setup>
import { ref, onMounted, computed } from 'vue'
import { getHoldingsSummary } from '../api'

const holdings = ref([])
const loading = ref(true)
const filterTier = ref('')
const filterMarket = ref('')

onMounted(async () => {
  holdings.value = await getHoldingsSummary()
  loading.value = false
})

const filtered = computed(() => {
  let list = holdings.value
  if (filterTier.value) list = list.filter(h => h.tier === filterTier.value)
  if (filterMarket.value) list = list.filter(h => h.market === filterMarket.value)
  return list
})

const markets = computed(() => [...new Set(holdings.value.map(h => h.market).filter(Boolean))])

function pnlClass(v) {
  if (v > 0) return 'pnl-pos'
  if (v < 0) return 'pnl-neg'
  return ''
}

function fmt(v, digits = 2) {
  if (v == null) return '-'
  return Number(v).toLocaleString('zh-CN', { minimumFractionDigits: digits, maximumFractionDigits: digits })
}

function pctFmt(v) {
  if (v == null) return '-'
  return (Number(v) * 100).toFixed(2) + '%'
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>持仓管理</h1>
      <p>所有持仓明细与盈亏</p>
    </div>

    <div class="filters">
      <select v-model="filterTier">
        <option value="">全部分层</option>
        <option value="STABLE">STABLE</option>
        <option value="MODERATE">MODERATE</option>
        <option value="GAMBLE">GAMBLE</option>
      </select>
      <select v-model="filterMarket">
        <option value="">全部市场</option>
        <option v-for="m in markets" :key="m" :value="m">{{ m }}</option>
      </select>
    </div>

    <div v-if="loading" class="loading">加载中</div>

    <div v-else class="card" style="overflow-x:auto">
      <table class="data-table">
        <thead>
          <tr>
            <th>代码</th>
            <th>市场</th>
            <th>分层</th>
            <th>数量</th>
            <th>均价</th>
            <th>现价</th>
            <th>盈亏</th>
            <th>盈亏%</th>
            <th>止损</th>
            <th>止盈</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!filtered.length">
            <td colspan="10" class="empty">暂无持仓数据</td>
          </tr>
          <tr v-for="h in filtered" :key="h.id || h.symbol">
            <td style="font-weight:600;color:#fff">{{ h.symbol }}</td>
            <td>{{ h.market || '-' }}</td>
            <td><span class="badge" :class="'badge-' + (h.tier||'').toLowerCase()">{{ h.tier || '-' }}</span></td>
            <td>{{ fmt(h.quantity, 0) }}</td>
            <td>{{ fmt(h.avg_cost) }}</td>
            <td>{{ fmt(h.current_price) }}</td>
            <td :class="pnlClass(h.pnl)">{{ fmt(h.pnl) }}</td>
            <td :class="pnlClass(h.pnl_pct)">{{ pctFmt(h.pnl_pct) }}</td>
            <td>{{ fmt(h.stop_loss) }}</td>
            <td>{{ fmt(h.take_profit) }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>
