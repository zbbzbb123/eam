<script setup>
import { ref, onMounted, computed } from 'vue'
import { getHoldingsSummary, analyzeHolding, analyzeAllHoldings } from '../api'
import AIAnalysisModal from '../components/AIAnalysisModal.vue'

const holdings = ref([])
const loading = ref(true)
const filterTier = ref('')
const filterMarket = ref('')

// AI state
const aiModalVisible = ref(false)
const aiLoading = ref(false)
const aiAnalysis = ref(null)
const aiTitle = ref('AI 分析结果')
const batchLoading = ref(false)

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

async function onAnalyzeHolding(h) {
  aiTitle.value = `AI 分析 - ${h.symbol}`
  aiAnalysis.value = null
  aiLoading.value = true
  aiModalVisible.value = true
  const result = await analyzeHolding(h.id)
  aiAnalysis.value = result
  aiLoading.value = false
}

async function onBatchAnalyze() {
  batchLoading.value = true
  await analyzeAllHoldings()
  batchLoading.value = false
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
      <button class="ai-btn" :disabled="batchLoading" @click="onBatchAnalyze">
        {{ batchLoading ? 'AI 分析中...' : '批量分析' }}
      </button>
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
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!filtered.length">
            <td colspan="11" class="empty">暂无持仓数据</td>
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
            <td><button class="ai-btn-sm" @click="onAnalyzeHolding(h)">AI分析</button></td>
          </tr>
        </tbody>
      </table>
    </div>

    <AIAnalysisModal
      :visible="aiModalVisible"
      :loading="aiLoading"
      :analysis="aiAnalysis"
      :title="aiTitle"
      @close="aiModalVisible = false"
    />
  </div>
</template>

<style scoped>
.ai-btn {
  background: linear-gradient(135deg, #4fc3f7, #0288d1);
  color: #fff; border: none; border-radius: 6px; padding: 8px 16px;
  font-size: 13px; cursor: pointer; font-weight: 600;
}
.ai-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.ai-btn-sm {
  background: linear-gradient(135deg, #4fc3f7, #0288d1);
  color: #fff; border: none; border-radius: 4px; padding: 4px 10px;
  font-size: 12px; cursor: pointer; white-space: nowrap;
}
.ai-btn-sm:hover, .ai-btn:hover:not(:disabled) { filter: brightness(1.15); }
</style>
