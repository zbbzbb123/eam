<script setup>
import { ref, onMounted, computed } from 'vue'
import {
  getHoldingsSummary, createHolding, updateHolding, deleteHolding,
  createTransaction, syncPrices, classifyTier,
  analyzeHolding, analyzeAllHoldings
} from '../api'
import AIAnalysisModal from '../components/AIAnalysisModal.vue'

const holdings = ref([])
const loading = ref(true)
const syncing = ref(false)
const filterTier = ref('')
const filterMarket = ref('')

// AI state
const aiModalVisible = ref(false)
const aiLoading = ref(false)
const aiAnalysis = ref(null)
const aiTitle = ref('AI 分析结果')
const batchLoading = ref(false)

// Add holding modal
const showAddModal = ref(false)
const addForm = ref({ symbol: '', market: 'US', quantity: '', avg_cost: '', first_buy_date: '' })
const addError = ref('')
const addSubmitting = ref(false)

// Edit holding modal
const showEditModal = ref(false)
const editForm = ref({ id: null, quantity: '', avg_cost: '', stop_loss_price: '', take_profit_price: '', notes: '' })
const editHolding = ref(null)
const editError = ref('')
const editSubmitting = ref(false)

// Transaction modal
const showTxModal = ref(false)
const txForm = ref({ action: 'buy', quantity: '', price: '', reason: '' })
const txHolding = ref(null)
const txError = ref('')
const txSubmitting = ref(false)

onMounted(async () => {
  // Load holdings first, then sync prices in background
  holdings.value = await getHoldingsSummary()
  loading.value = false
  // Sync prices in background, reload when done
  syncing.value = true
  await syncPrices()
  syncing.value = false
  holdings.value = await getHoldingsSummary()
})

async function reload() {
  holdings.value = await getHoldingsSummary()
}

async function onSyncPrices() {
  syncing.value = true
  await syncPrices()
  await reload()
  syncing.value = false
}

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
  return Number(v).toFixed(2) + '%'
}

function tierLabel(t) {
  const map = { stable: '稳健', medium: '成长', gamble: '投机', STABLE: '稳健', MEDIUM: '成长', GAMBLE: '投机' }
  return map[t] || t
}

// === Add holding ===
function openAddModal() {
  addForm.value = { symbol: '', market: 'US', quantity: '', avg_cost: '', first_buy_date: new Date().toISOString().slice(0, 10) }
  addError.value = ''
  showAddModal.value = true
}

async function submitAdd() {
  const f = addForm.value
  if (!f.symbol || !f.quantity || !f.avg_cost || !f.first_buy_date) {
    addError.value = '请填写所有必填项'
    return
  }
  addSubmitting.value = true
  addError.value = ''
  try {
    // AI classify tier
    const { tier } = await classifyTier(f.symbol, f.market)
    await createHolding({
      symbol: f.symbol.toUpperCase(),
      market: f.market,
      tier: tier,
      quantity: f.quantity,
      avg_cost: f.avg_cost,
      first_buy_date: f.first_buy_date,
      buy_reason: '手动录入'
    })
    showAddModal.value = false
    // Sync price for the new holding
    await syncPrices()
    await reload()
  } catch (e) {
    addError.value = e.response?.data?.detail || '录入失败'
  } finally {
    addSubmitting.value = false
  }
}

// === Edit holding ===
function openEditModal(h) {
  editHolding.value = h
  editForm.value = {
    id: h.id,
    quantity: h.quantity,
    avg_cost: h.avg_cost,
    stop_loss_price: h.stop_loss || '',
    take_profit_price: h.take_profit || '',
    notes: h.notes || ''
  }
  editError.value = ''
  showEditModal.value = true
}

async function submitEdit() {
  editSubmitting.value = true
  editError.value = ''
  try {
    const data = {}
    const f = editForm.value
    if (f.quantity) data.quantity = String(f.quantity)
    if (f.avg_cost) data.avg_cost = String(f.avg_cost)
    if (f.stop_loss_price) data.stop_loss_price = String(f.stop_loss_price)
    if (f.take_profit_price) data.take_profit_price = String(f.take_profit_price)
    if (f.notes) data.notes = f.notes
    await updateHolding(f.id, data)
    showEditModal.value = false
    await reload()
  } catch (e) {
    editError.value = e.response?.data?.detail || '修改失败'
  } finally {
    editSubmitting.value = false
  }
}

// === Delete holding ===
async function onDelete(h) {
  if (!confirm(`确认删除 ${h.symbol} 的持仓记录？`)) return
  try {
    await deleteHolding(h.id)
    await reload()
  } catch (e) {
    alert('删除失败: ' + (e.response?.data?.detail || e.message))
  }
}

// === Transaction ===
function openTxModal(h, action) {
  txHolding.value = h
  txForm.value = { action, quantity: '', price: '', reason: '' }
  txError.value = ''
  showTxModal.value = true
}

async function submitTx() {
  const f = txForm.value
  if (!f.quantity || !f.price) {
    txError.value = '请填写数量和价格'
    return
  }
  txSubmitting.value = true
  txError.value = ''
  try {
    await createTransaction(txHolding.value.id, {
      action: f.action,
      quantity: f.quantity,
      price: f.price,
      reason: f.reason || (f.action === 'buy' ? '加仓' : '减仓'),
      transaction_date: new Date().toISOString()
    })
    showTxModal.value = false
    await reload()
  } catch (e) {
    txError.value = e.response?.data?.detail || '交易失败'
  } finally {
    txSubmitting.value = false
  }
}

// === AI ===
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
        <option value="STABLE">稳健</option>
        <option value="MEDIUM">成长</option>
        <option value="GAMBLE">投机</option>
      </select>
      <select v-model="filterMarket">
        <option value="">全部市场</option>
        <option v-for="m in markets" :key="m" :value="m">{{ m }}</option>
      </select>
      <button class="btn-primary" @click="openAddModal">+ 新增持仓</button>
      <button class="btn-sync" :disabled="syncing" @click="onSyncPrices">
        {{ syncing ? '同步中...' : '刷新股价' }}
      </button>
      <button class="ai-btn" :disabled="batchLoading" @click="onBatchAnalyze">
        {{ batchLoading ? 'AI 分析中...' : '批量分析' }}
      </button>
    </div>

    <div v-if="loading" class="loading">{{ syncing ? '正在同步最新股价...' : '加载中' }}</div>

    <div v-else class="card" style="overflow-x:auto">
      <table class="data-table">
        <thead>
          <tr>
            <th>代码</th>
            <th>名称</th>
            <th>市场</th>
            <th>分层</th>
            <th>数量</th>
            <th>均价</th>
            <th>现价</th>
            <th>盈亏</th>
            <th>盈亏%</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="!filtered.length">
            <td colspan="10" class="empty">暂无持仓数据，点击"新增持仓"开始录入</td>
          </tr>
          <tr v-for="h in filtered" :key="h.id">
            <td style="font-weight:600;color:#fff">{{ h.symbol }}</td>
            <td class="name-cell">{{ h.name || '-' }}</td>
            <td>{{ h.market || '-' }}</td>
            <td><span class="badge" :class="'badge-' + (h.tier||'').toLowerCase()">{{ tierLabel(h.tier) }}</span></td>
            <td>{{ fmt(h.quantity, 0) }}</td>
            <td>{{ fmt(h.avg_cost) }}</td>
            <td>{{ fmt(h.current_price) }}</td>
            <td :class="pnlClass(h.pnl)">{{ fmt(h.pnl) }}</td>
            <td :class="pnlClass(h.pnl_pct)">{{ pctFmt(h.pnl_pct) }}</td>
            <td class="actions">
              <button class="btn-buy" @click="openTxModal(h, 'buy')">买入</button>
              <button class="btn-sell" @click="openTxModal(h, 'sell')">卖出</button>
              <button class="btn-edit" @click="openEditModal(h)">编辑</button>
              <button class="btn-del" @click="onDelete(h)">删除</button>
              <button class="ai-btn-sm" @click="onAnalyzeHolding(h)">AI</button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 新增持仓弹窗 -->
    <div v-if="showAddModal" class="modal-overlay" @click.self="showAddModal = false">
      <div class="modal">
        <h2>新增持仓</h2>
        <p class="modal-hint">分层将由 AI 自动判断</p>
        <div class="form-row">
          <label>股票代码</label>
          <input v-model="addForm.symbol" placeholder="如 AAPL、00700、600519" />
        </div>
        <div class="form-row">
          <label>市场</label>
          <select v-model="addForm.market">
            <option value="US">美股</option>
            <option value="HK">港股</option>
            <option value="CN">A股</option>
          </select>
        </div>
        <div class="form-row">
          <label>持仓数量</label>
          <input v-model="addForm.quantity" type="number" min="1" placeholder="股数" />
        </div>
        <div class="form-row">
          <label>成本均价</label>
          <input v-model="addForm.avg_cost" type="number" step="0.01" min="0.01" placeholder="每股成本" />
        </div>
        <div class="form-row">
          <label>首次买入日期</label>
          <input v-model="addForm.first_buy_date" type="date" />
        </div>
        <div v-if="addError" class="form-error">{{ addError }}</div>
        <div class="form-actions">
          <button class="btn-cancel" @click="showAddModal = false">取消</button>
          <button class="btn-primary" :disabled="addSubmitting" @click="submitAdd">
            {{ addSubmitting ? 'AI 分类中...' : '确认录入' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 编辑持仓弹窗 -->
    <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
      <div class="modal">
        <h2>编辑 {{ editHolding?.symbol }}</h2>
        <div class="form-row">
          <label>持仓数量</label>
          <input v-model="editForm.quantity" type="number" min="0" />
        </div>
        <div class="form-row">
          <label>成本均价</label>
          <input v-model="editForm.avg_cost" type="number" step="0.01" min="0.01" />
        </div>
        <div class="form-row">
          <label>止损价</label>
          <input v-model="editForm.stop_loss_price" type="number" step="0.01" placeholder="可选" />
        </div>
        <div class="form-row">
          <label>止盈价</label>
          <input v-model="editForm.take_profit_price" type="number" step="0.01" placeholder="可选" />
        </div>
        <div class="form-row">
          <label>备注</label>
          <input v-model="editForm.notes" placeholder="可选" />
        </div>
        <div v-if="editError" class="form-error">{{ editError }}</div>
        <div class="form-actions">
          <button class="btn-cancel" @click="showEditModal = false">取消</button>
          <button class="btn-primary" :disabled="editSubmitting" @click="submitEdit">
            {{ editSubmitting ? '保存中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 交易弹窗 -->
    <div v-if="showTxModal" class="modal-overlay" @click.self="showTxModal = false">
      <div class="modal">
        <h2>{{ txForm.action === 'buy' ? '买入' : '卖出' }} {{ txHolding?.symbol }}</h2>
        <div class="form-info">
          当前持仓：{{ fmt(txHolding?.quantity, 0) }} 股 | 均价：{{ fmt(txHolding?.avg_cost) }}
        </div>
        <div class="form-row">
          <label>{{ txForm.action === 'buy' ? '买入' : '卖出' }}数量</label>
          <input v-model="txForm.quantity" type="number" min="1" placeholder="股数" />
        </div>
        <div class="form-row">
          <label>成交价格</label>
          <input v-model="txForm.price" type="number" step="0.01" min="0.01" placeholder="每股价格" />
        </div>
        <div class="form-row">
          <label>交易备注</label>
          <input v-model="txForm.reason" :placeholder="txForm.action === 'buy' ? '加仓理由' : '减仓理由'" />
        </div>
        <div v-if="txError" class="form-error">{{ txError }}</div>
        <div class="form-actions">
          <button class="btn-cancel" @click="showTxModal = false">取消</button>
          <button :class="txForm.action === 'buy' ? 'btn-buy-lg' : 'btn-sell-lg'" :disabled="txSubmitting" @click="submitTx">
            {{ txSubmitting ? '提交中...' : (txForm.action === 'buy' ? '确认买入' : '确认卖出') }}
          </button>
        </div>
      </div>
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
.btn-primary {
  background: #4caf50; color: #fff; border: none; border-radius: 6px;
  padding: 8px 16px; font-size: 13px; cursor: pointer; font-weight: 600;
}
.btn-primary:hover:not(:disabled) { filter: brightness(1.15); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

.btn-sync {
  background: #ff9800; color: #fff; border: none; border-radius: 6px;
  padding: 8px 16px; font-size: 13px; cursor: pointer; font-weight: 600;
}
.btn-sync:hover:not(:disabled) { filter: brightness(1.15); }
.btn-sync:disabled { opacity: 0.6; cursor: not-allowed; }

.btn-buy, .btn-sell, .btn-edit, .btn-del {
  border: none; border-radius: 4px; padding: 4px 10px;
  font-size: 12px; cursor: pointer; font-weight: 600; color: #fff;
}
.btn-buy { background: #e53935; }
.btn-sell { background: #43a047; }
.btn-edit { background: #666; }
.btn-del { background: #444; color: #f44336; }
.btn-buy:hover, .btn-sell:hover, .btn-edit:hover { filter: brightness(1.15); }
.btn-del:hover { background: #f44336; color: #fff; }

.btn-buy-lg, .btn-sell-lg {
  border: none; border-radius: 6px; padding: 8px 16px;
  font-size: 13px; cursor: pointer; font-weight: 600; color: #fff;
}
.btn-buy-lg { background: #e53935; }
.btn-sell-lg { background: #43a047; }
.btn-buy-lg:hover, .btn-sell-lg:hover { filter: brightness(1.15); }
.btn-buy-lg:disabled, .btn-sell-lg:disabled { opacity: 0.6; cursor: not-allowed; }

.btn-cancel {
  background: transparent; color: #999; border: 1px solid #444; border-radius: 6px;
  padding: 8px 16px; font-size: 13px; cursor: pointer;
}
.btn-cancel:hover { border-color: #888; color: #ccc; }

.actions { display: flex; gap: 4px; align-items: center; flex-wrap: nowrap; }
.name-cell { color: #bbb; font-size: 13px; white-space: nowrap; }

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

/* Modal */
.modal-overlay {
  position: fixed; top: 0; left: 0; right: 0; bottom: 0;
  background: rgba(0,0,0,0.6); display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.modal {
  background: #1e1e2e; border-radius: 12px; padding: 28px; width: 420px;
  max-width: 90vw; box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.modal h2 { margin: 0 0 6px; color: #fff; font-size: 18px; }
.modal-hint { margin: 0 0 16px; color: #888; font-size: 12px; }
.form-row { margin-bottom: 14px; }
.form-row label { display: block; color: #aaa; font-size: 13px; margin-bottom: 4px; }
.form-row input, .form-row select {
  width: 100%; padding: 8px 12px; background: #2a2a3e; border: 1px solid #444;
  border-radius: 6px; color: #fff; font-size: 14px; box-sizing: border-box;
}
.form-row input:focus, .form-row select:focus { border-color: #4fc3f7; outline: none; }
.form-info { background: #2a2a3e; padding: 10px 14px; border-radius: 6px; color: #bbb; font-size: 13px; margin-bottom: 16px; }
.form-error { color: #ef5350; font-size: 13px; margin-bottom: 12px; }
.form-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
</style>
