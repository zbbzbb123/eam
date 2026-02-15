<script setup>
import { ref, onMounted, computed } from 'vue'
import {
  getHoldingsSummary, createHolding, updateHolding, deleteHolding,
  syncPrices, previewTransaction, updatePosition, getTransactions,
  createTransaction, analyzeHolding, analyzeAllHoldings
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
const addForm = ref({ symbol: '', market: 'US', tier: 'core', quantity: '', avg_cost: '', first_buy_date: '' })
const addError = ref('')
const addSubmitting = ref(false)

// Edit holding modal
const showEditModal = ref(false)
const editForm = ref({ id: null, quantity: '', avg_cost: '', tier: '', stop_loss_price: '', take_profit_price: '', notes: '', transaction_date: '' })
const editHolding = ref(null)
const editError = ref('')
const editSubmitting = ref(false)

// Transaction preview confirmation
const showPreviewModal = ref(false)
const previewData = ref(null)
const previewReason = ref('')
const previewDate = ref('')
const previewSubmitting = ref(false)

// Transaction history
const txHistory = ref([])
const txHistoryLoading = ref(false)
const showTxHistory = ref(false)
const showTxModal = ref(false)
const txModalSymbol = ref('')

// Add transaction form
const showAddTx = ref(false)
const addTxHoldingId = ref(null)
const addTxForm = ref({ action: 'buy', quantity: '', price: '', transaction_date: '', reason: '' })
const addTxError = ref('')
const addTxSubmitting = ref(false)

onMounted(async () => {
  holdings.value = await getHoldingsSummary()
  loading.value = false
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
  const map = { core: 'Core', growth: 'Growth', gamble: 'Gamble', CORE: 'Core', GROWTH: 'Growth', GAMBLE: 'Gamble' }
  return map[t] || t
}

// === Add holding ===
function openAddModal() {
  addForm.value = { symbol: '', market: 'US', tier: 'core', quantity: '', avg_cost: '', first_buy_date: new Date().toISOString().slice(0, 10) }
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
    await createHolding({
      symbol: f.symbol.toUpperCase(),
      market: f.market,
      tier: f.tier,
      quantity: f.quantity,
      avg_cost: f.avg_cost,
      first_buy_date: f.first_buy_date,
      buy_reason: '手动录入'
    })
    showAddModal.value = false
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
    tier: (h.tier || '').toLowerCase(),
    stop_loss_price: h.stop_loss || '',
    take_profit_price: h.take_profit || '',
    notes: h.notes || '',
    transaction_date: ''
  }
  editError.value = ''
  showTxHistory.value = false
  txHistory.value = []
  showEditModal.value = true
}

async function submitEdit() {
  editSubmitting.value = true
  editError.value = ''
  try {
    const f = editForm.value
    const h = editHolding.value
    const qtyChanged = Number(f.quantity) !== Number(h.quantity)
    const avgChanged = Number(f.avg_cost) !== Number(h.avg_cost)

    if (qtyChanged || avgChanged) {
      // Position changed → preview transaction
      const preview = await previewTransaction(f.id, {
        new_quantity: String(f.quantity),
        new_avg_cost: String(f.avg_cost),
        transaction_date: f.transaction_date ? new Date(f.transaction_date).toISOString() : undefined
      })
      previewData.value = preview
      previewReason.value = preview.action === 'buy' ? '加仓' : '减仓'
      previewDate.value = preview.suggested_date || new Date().toISOString().slice(0, 10)
      showPreviewModal.value = true
    } else {
      // Only settings changed → direct PATCH
      const data = {}
      if (f.tier) data.tier = f.tier
      if (f.stop_loss_price) data.stop_loss_price = String(f.stop_loss_price)
      else data.stop_loss_price = null
      if (f.take_profit_price) data.take_profit_price = String(f.take_profit_price)
      else data.take_profit_price = null
      data.notes = f.notes || null
      await updateHolding(f.id, data)
      showEditModal.value = false
      await reload()
    }
  } catch (e) {
    editError.value = e.response?.data?.detail || '操作失败'
  } finally {
    editSubmitting.value = false
  }
}

// === Confirm transaction preview ===
async function confirmPreview() {
  previewSubmitting.value = true
  try {
    const f = editForm.value
    await updatePosition(f.id, {
      new_quantity: String(f.quantity),
      new_avg_cost: String(f.avg_cost),
      transaction_date: new Date(previewDate.value).toISOString(),
      reason: previewReason.value
    })
    showPreviewModal.value = false

    // Also update settings if changed
    const data = {}
    if (f.tier) data.tier = f.tier
    if (f.stop_loss_price) data.stop_loss_price = String(f.stop_loss_price)
    if (f.take_profit_price) data.take_profit_price = String(f.take_profit_price)
    if (f.notes) data.notes = f.notes
    if (Object.keys(data).length) {
      await updateHolding(f.id, data)
    }

    showEditModal.value = false
    await reload()
  } catch (e) {
    editError.value = e.response?.data?.detail || '更新失败'
    showPreviewModal.value = false
  } finally {
    previewSubmitting.value = false
  }
}

// === Transaction history ===
async function loadTxHistory() {
  if (showTxHistory.value) {
    showTxHistory.value = false
    return
  }
  txHistoryLoading.value = true
  txHistory.value = await getTransactions(editHolding.value.id)
  txHistoryLoading.value = false
  showTxHistory.value = true
}

// === View transactions (standalone) ===
async function openTxModal(h) {
  txModalSymbol.value = h.symbol
  addTxHoldingId.value = h.id
  txHistory.value = []
  txHistoryLoading.value = true
  showTxModal.value = true
  showAddTx.value = false
  txHistory.value = await getTransactions(h.id)
  txHistoryLoading.value = false
}

// === Add transaction ===
function openAddTxForm() {
  addTxForm.value = { action: 'buy', quantity: '', price: '', transaction_date: new Date().toISOString().slice(0, 10), reason: '' }
  addTxError.value = ''
  showAddTx.value = true
}

async function submitAddTx() {
  const f = addTxForm.value
  if (!f.quantity || !f.price || !f.transaction_date) {
    addTxError.value = '请填写数量、价格和日期'
    return
  }
  addTxSubmitting.value = true
  addTxError.value = ''
  try {
    await createTransaction(addTxHoldingId.value, {
      action: f.action,
      quantity: Number(f.quantity),
      price: Number(f.price),
      transaction_date: new Date(f.transaction_date).toISOString(),
      reason: f.reason || (f.action === 'buy' ? '加仓' : '减仓')
    })
    showAddTx.value = false
    // Refresh transactions and holdings
    txHistory.value = await getTransactions(addTxHoldingId.value)
    await reload()
  } catch (e) {
    addTxError.value = e.response?.data?.detail || '添加失败'
  } finally {
    addTxSubmitting.value = false
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
        <option value="core">Core</option>
        <option value="growth">Growth</option>
        <option value="gamble">Gamble</option>
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
              <button class="btn-edit" @click="openEditModal(h)">编辑</button>
              <button class="btn-tx" @click="openTxModal(h)">记录</button>
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
          <label>分层</label>
          <select v-model="addForm.tier">
            <option value="core">Core</option>
            <option value="growth">Growth</option>
            <option value="gamble">Gamble</option>
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
            {{ addSubmitting ? '录入中...' : '确认录入' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 编辑持仓弹窗 -->
    <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
      <div class="modal modal-wide">
        <h2>编辑 {{ editHolding?.symbol }}</h2>
        <div class="form-info">
          当前持仓：{{ fmt(editHolding?.quantity, 0) }} 股 | 均价：{{ fmt(editHolding?.avg_cost) }}
        </div>

        <div class="section-label">持仓信息</div>
        <div class="form-grid">
          <div class="form-row">
            <label>持仓数量</label>
            <input v-model="editForm.quantity" type="number" min="0" />
          </div>
          <div class="form-row">
            <label>成本均价</label>
            <input v-model="editForm.avg_cost" type="number" step="0.01" min="0.01" />
          </div>
        </div>
        <div class="form-row">
          <label>交易日期（可选，留空自动推导）</label>
          <input v-model="editForm.transaction_date" type="date" />
        </div>

        <div class="section-label">设置</div>
        <div class="form-row">
          <label>分层</label>
          <select v-model="editForm.tier">
            <option value="core">Core</option>
            <option value="growth">Growth</option>
            <option value="gamble">Gamble</option>
          </select>
        </div>
        <div class="form-grid">
          <div class="form-row">
            <label>止损价</label>
            <input v-model="editForm.stop_loss_price" type="number" step="0.01" placeholder="可选" />
          </div>
          <div class="form-row">
            <label>止盈价</label>
            <input v-model="editForm.take_profit_price" type="number" step="0.01" placeholder="可选" />
          </div>
        </div>
        <div class="form-row">
          <label>备注</label>
          <input v-model="editForm.notes" placeholder="可选" />
        </div>

        <!-- Transaction History -->
        <div class="tx-toggle" @click="loadTxHistory">
          {{ txHistoryLoading ? '加载中...' : (showTxHistory ? '收起交易明细 ▲' : '查看交易明细 ▼') }}
        </div>
        <div v-if="showTxHistory" class="tx-history">
          <div v-if="!txHistory.length" class="tx-empty">暂无交易记录</div>
          <div v-for="tx in txHistory" :key="tx.id" class="tx-item">
            <span :class="tx.action === 'buy' ? 'tx-buy' : 'tx-sell'">{{ tx.action === 'buy' ? '买入' : '卖出' }}</span>
            <span>{{ fmt(tx.quantity, 0) }} 股</span>
            <span>@ {{ fmt(tx.price) }}</span>
            <span class="tx-date">{{ tx.transaction_date?.slice(0, 10) }}</span>
            <span class="tx-reason">{{ tx.reason }}</span>
          </div>
        </div>

        <div v-if="editError" class="form-error">{{ editError }}</div>
        <div class="form-actions">
          <button class="btn-cancel" @click="showEditModal = false">取消</button>
          <button class="btn-primary" :disabled="editSubmitting" @click="submitEdit">
            {{ editSubmitting ? '处理中...' : '保存' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 交易推导确认弹窗 -->
    <div v-if="showPreviewModal" class="modal-overlay" @click.self="showPreviewModal = false">
      <div class="modal">
        <h2>推导交易确认</h2>
        <div class="preview-info">
          <div class="preview-row">
            <span class="preview-label">类型</span>
            <span :class="previewData?.action === 'buy' ? 'tx-buy' : 'tx-sell'">
              {{ previewData?.action === 'buy' ? '买入' : '卖出' }}
            </span>
          </div>
          <div class="preview-row">
            <span class="preview-label">数量</span>
            <span>{{ fmt(previewData?.quantity, 0) }} 股</span>
          </div>
          <div class="preview-row">
            <span class="preview-label">推导价格</span>
            <span>{{ fmt(previewData?.inferred_price) }} 元</span>
          </div>
        </div>
        <div class="form-row">
          <label>交易日期</label>
          <input v-model="previewDate" type="date" />
        </div>
        <div class="form-row">
          <label>原因</label>
          <input v-model="previewReason" :placeholder="previewData?.action === 'buy' ? '加仓' : '减仓'" />
        </div>
        <div v-if="editError" class="form-error">{{ editError }}</div>
        <div class="form-actions">
          <button class="btn-cancel" @click="showPreviewModal = false">取消</button>
          <button class="btn-primary" :disabled="previewSubmitting" @click="confirmPreview">
            {{ previewSubmitting ? '提交中...' : '确认' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 交易记录弹窗 -->
    <div v-if="showTxModal" class="modal-overlay" @click.self="showTxModal = false">
      <div class="modal modal-wide">
        <h2>{{ txModalSymbol }} 交易记录</h2>
        <div v-if="txHistoryLoading" class="tx-empty">加载中...</div>
        <div v-else-if="!txHistory.length" class="tx-empty">暂无交易记录</div>
        <div v-else class="tx-timeline">
          <div v-for="tx in txHistory" :key="tx.id" class="tx-timeline-item">
            <div class="tx-timeline-dot" :class="tx.action === 'buy' ? 'dot-buy' : 'dot-sell'"></div>
            <div class="tx-timeline-content">
              <div class="tx-timeline-header">
                <span :class="tx.action === 'buy' ? 'tx-buy' : 'tx-sell'">{{ tx.action === 'buy' ? '买入' : '卖出' }}</span>
                <span class="tx-timeline-date">{{ tx.transaction_date?.slice(0, 10) }}</span>
              </div>
              <div class="tx-timeline-detail">
                {{ fmt(tx.quantity, 0) }} 股 @ {{ fmt(tx.price) }}
                <span class="tx-timeline-total">合计 {{ fmt(Number(tx.quantity) * Number(tx.price)) }}</span>
              </div>
              <div v-if="tx.reason" class="tx-timeline-reason">{{ tx.reason }}</div>
            </div>
          </div>
        </div>

        <!-- Add transaction inline form -->
        <div v-if="!showAddTx" class="add-tx-toggle" @click="openAddTxForm">+ 新增交易</div>
        <div v-else class="add-tx-form">
          <div class="section-label">新增交易</div>
          <div class="form-grid">
            <div class="form-row">
              <label>类型</label>
              <select v-model="addTxForm.action">
                <option value="buy">买入</option>
                <option value="sell">卖出</option>
              </select>
            </div>
            <div class="form-row">
              <label>日期</label>
              <input v-model="addTxForm.transaction_date" type="date" />
            </div>
          </div>
          <div class="form-grid">
            <div class="form-row">
              <label>数量</label>
              <input v-model="addTxForm.quantity" type="number" min="1" placeholder="股数" />
            </div>
            <div class="form-row">
              <label>价格</label>
              <input v-model="addTxForm.price" type="number" step="0.01" min="0.01" placeholder="每股价格" />
            </div>
          </div>
          <div class="form-row">
            <label>原因</label>
            <input v-model="addTxForm.reason" :placeholder="addTxForm.action === 'buy' ? '加仓' : '减仓'" />
          </div>
          <div v-if="addTxError" class="form-error">{{ addTxError }}</div>
          <div class="form-actions" style="margin-top:10px">
            <button class="btn-cancel" @click="showAddTx = false">取消</button>
            <button class="btn-primary" :disabled="addTxSubmitting" @click="submitAddTx">
              {{ addTxSubmitting ? '提交中...' : '确认添加' }}
            </button>
          </div>
        </div>

        <div class="form-actions">
          <button class="btn-cancel" @click="showTxModal = false">关闭</button>
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

.btn-edit, .btn-del {
  border: none; border-radius: 4px; padding: 4px 10px;
  font-size: 12px; cursor: pointer; font-weight: 600; color: #fff;
}
.btn-edit { background: #666; }
.btn-tx { background: #555; color: #4fc3f7; }
.btn-tx:hover { background: #4fc3f7; color: #fff; }
.btn-del { background: #444; color: #f44336; }
.btn-edit:hover { filter: brightness(1.15); }
.btn-del:hover { background: #f44336; color: #fff; }

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
.modal-wide { width: 500px; max-height: 85vh; overflow-y: auto; }
.modal h2 { margin: 0 0 6px; color: #fff; font-size: 18px; }
.form-row { margin-bottom: 14px; }
.form-row label { display: block; color: #aaa; font-size: 13px; margin-bottom: 4px; }
.form-row input, .form-row select {
  width: 100%; padding: 8px 12px; background: #2a2a3e; border: 1px solid #444;
  border-radius: 6px; color: #fff; font-size: 14px; box-sizing: border-box;
}
.form-row input:focus, .form-row select:focus { border-color: #4fc3f7; outline: none; }
.form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0 14px; }
.form-info { background: #2a2a3e; padding: 10px 14px; border-radius: 6px; color: #bbb; font-size: 13px; margin-bottom: 16px; }
.form-error { color: #ef5350; font-size: 13px; margin-bottom: 12px; }
.form-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }

.section-label {
  color: #888; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px;
  margin: 16px 0 8px; padding-bottom: 4px; border-bottom: 1px solid #333;
}

/* Preview */
.preview-info { background: #2a2a3e; padding: 14px; border-radius: 8px; margin-bottom: 16px; }
.preview-row { display: flex; justify-content: space-between; padding: 6px 0; font-size: 14px; color: #ddd; }
.preview-label { color: #888; }

/* Transaction history */
.tx-toggle {
  color: #4fc3f7; font-size: 13px; cursor: pointer; padding: 8px 0; user-select: none;
}
.tx-toggle:hover { text-decoration: underline; }
.tx-history { margin-top: 4px; max-height: 200px; overflow-y: auto; }
.tx-empty { color: #666; font-size: 13px; padding: 8px 0; }
.tx-item {
  display: flex; gap: 10px; align-items: center; padding: 6px 0;
  font-size: 13px; color: #bbb; border-bottom: 1px solid #2a2a3e;
}
.tx-buy { color: #e53935; font-weight: 600; }
.tx-sell { color: #43a047; font-weight: 600; }
.tx-date { color: #666; }
.tx-reason { color: #888; font-size: 12px; }

/* Transaction timeline */
.tx-timeline { padding: 8px 0; }
.tx-timeline-item {
  display: flex; gap: 12px; position: relative; padding-bottom: 16px;
}
.tx-timeline-item:not(:last-child)::before {
  content: ''; position: absolute; left: 5px; top: 16px; bottom: 0;
  width: 1px; background: #333;
}
.tx-timeline-dot {
  width: 11px; height: 11px; border-radius: 50%; margin-top: 4px; flex-shrink: 0;
}
.dot-buy { background: #e53935; }
.dot-sell { background: #43a047; }
.tx-timeline-content { flex: 1; min-width: 0; }
.tx-timeline-header {
  display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;
}
.tx-timeline-date { color: #666; font-size: 12px; }
.tx-timeline-detail { font-size: 13px; color: #bbb; }
.tx-timeline-total { color: #888; margin-left: 8px; font-size: 12px; }
.tx-timeline-reason { color: #666; font-size: 12px; margin-top: 2px; }

/* Add transaction */
.add-tx-toggle {
  color: #4fc3f7; font-size: 13px; cursor: pointer; padding: 12px 0 4px;
  user-select: none; font-weight: 600;
}
.add-tx-toggle:hover { text-decoration: underline; }
.add-tx-form {
  margin-top: 8px; padding: 14px; background: #2a2a3e; border-radius: 8px;
}
</style>
