<script setup>
import { ref, onMounted, computed } from 'vue'
import { getWatchlist, addWatchlistItem, updateWatchlistItem, deleteWatchlistItem } from '../api'

const items = ref([])
const loading = ref(true)
const filterMarket = ref('')
const filterTheme = ref('')

// Add modal
const showAddModal = ref(false)
const addForm = ref({ symbol: '', market: 'US', theme: '', reason: '' })
const addError = ref('')
const addSubmitting = ref(false)

// Edit modal
const showEditModal = ref(false)
const editItem = ref(null)
const editForm = ref({ theme: '', reason: '' })
const editError = ref('')
const editSubmitting = ref(false)

onMounted(async () => {
  items.value = await getWatchlist()
  loading.value = false
})

async function reload() {
  items.value = await getWatchlist()
}

const themes = computed(() => [...new Set(items.value.map(i => i.theme).filter(Boolean))])
const markets = computed(() => [...new Set(items.value.map(i => i.market).filter(Boolean))])

const filtered = computed(() => {
  let list = items.value
  if (filterMarket.value) list = list.filter(i => i.market === filterMarket.value)
  if (filterTheme.value) list = list.filter(i => i.theme === filterTheme.value)
  return list
})

const grouped = computed(() => {
  const groups = {}
  for (const item of filtered.value) {
    const key = item.theme || 'Uncategorized'
    if (!groups[key]) groups[key] = []
    groups[key].push(item)
  }
  return groups
})

function marketLabel(m) {
  return { US: 'US', HK: 'HK', CN: 'CN' }[m] || m
}

function formatDate(d) {
  if (!d) return '-'
  return d.slice(0, 10)
}

// === Add ===
function openAddModal() {
  addForm.value = { symbol: '', market: 'US', theme: '', reason: '' }
  addError.value = ''
  showAddModal.value = true
}

async function submitAdd() {
  const f = addForm.value
  if (!f.symbol) { addError.value = 'Symbol is required'; return }
  addSubmitting.value = true
  addError.value = ''
  try {
    await addWatchlistItem({
      symbol: f.symbol.toUpperCase(),
      market: f.market,
      theme: f.theme || 'Default',
      reason: f.reason,
    })
    showAddModal.value = false
    await reload()
  } catch (e) {
    addError.value = e.response?.data?.detail || 'Failed to add'
  } finally {
    addSubmitting.value = false
  }
}

// === Edit ===
function openEditModal(item) {
  editItem.value = item
  editForm.value = { theme: item.theme, reason: item.reason }
  editError.value = ''
  showEditModal.value = true
}

async function submitEdit() {
  editSubmitting.value = true
  editError.value = ''
  try {
    await updateWatchlistItem(editItem.value.id, editForm.value)
    showEditModal.value = false
    await reload()
  } catch (e) {
    editError.value = e.response?.data?.detail || 'Update failed'
  } finally {
    editSubmitting.value = false
  }
}

// === Delete ===
async function onDelete(item) {
  if (!confirm(`Unwatch ${item.symbol}?`)) return
  try {
    await deleteWatchlistItem(item.id)
    await reload()
  } catch (e) {
    alert('Delete failed: ' + (e.response?.data?.detail || e.message))
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Watchlist</h1>
      <p>Tracked stocks & ETFs with weekly report analysis</p>
    </div>

    <div class="filters">
      <select v-model="filterMarket">
        <option value="">All Markets</option>
        <option v-for="m in markets" :key="m" :value="m">{{ marketLabel(m) }}</option>
      </select>
      <select v-model="filterTheme">
        <option value="">All Themes</option>
        <option v-for="t in themes" :key="t" :value="t">{{ t }}</option>
      </select>
      <button class="btn-primary" @click="openAddModal">+ Add to Watchlist</button>
    </div>

    <div v-if="loading" class="loading">Loading</div>

    <template v-else-if="filtered.length === 0">
      <div class="card empty-card">
        <p>No watchlist items</p>
        <p class="empty-hint">Add stocks or ETFs you're interested in. Data will be collected automatically and analyzed in weekly reports.</p>
      </div>
    </template>

    <template v-else>
      <div v-for="(group, theme) in grouped" :key="theme" class="card" style="margin-bottom: 16px">
        <div class="card-title">{{ theme }} <span class="group-count">{{ group.length }}</span></div>
        <table class="data-table">
          <thead>
            <tr>
              <th>Symbol</th>
              <th>Market</th>
              <th>Reason</th>
              <th>Added</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="item in group" :key="item.id">
              <td style="font-weight:600;color:#fff">{{ item.symbol }}</td>
              <td><span class="market-tag">{{ marketLabel(item.market) }}</span></td>
              <td class="reason-cell">{{ item.reason || '-' }}</td>
              <td class="date-cell">{{ formatDate(item.created_at) }}</td>
              <td class="actions">
                <button class="btn-edit" @click="openEditModal(item)">Edit</button>
                <button class="btn-del" @click="onDelete(item)">Unwatch</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>

    <!-- 添加关注弹窗 -->
    <div v-if="showAddModal" class="modal-overlay" @click.self="showAddModal = false">
      <div class="modal">
        <h2>Add to Watchlist</h2>
        <div class="form-row">
          <label>Symbol</label>
          <input v-model="addForm.symbol" placeholder="e.g. NVDA, 00700, 512480" />
        </div>
        <div class="form-row">
          <label>Market</label>
          <select v-model="addForm.market">
            <option value="US">US</option>
            <option value="HK">HK</option>
            <option value="CN">CN</option>
          </select>
        </div>
        <div class="form-row">
          <label>Theme</label>
          <input v-model="addForm.theme" placeholder="e.g. AI Chips, Consumer Tech" list="theme-suggestions" />
          <datalist id="theme-suggestions">
            <option v-for="t in themes" :key="t" :value="t" />
          </datalist>
        </div>
        <div class="form-row">
          <label>Reason</label>
          <textarea v-model="addForm.reason" rows="3" placeholder="Why watch this? Entry conditions?"></textarea>
        </div>
        <div v-if="addError" class="form-error">{{ addError }}</div>
        <div class="form-actions">
          <button class="btn-cancel" @click="showAddModal = false">Cancel</button>
          <button class="btn-primary" :disabled="addSubmitting" @click="submitAdd">
            {{ addSubmitting ? 'Adding...' : 'Confirm' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 编辑弹窗 -->
    <div v-if="showEditModal" class="modal-overlay" @click.self="showEditModal = false">
      <div class="modal">
        <h2>Edit {{ editItem?.symbol }}</h2>
        <div class="form-row">
          <label>Theme</label>
          <input v-model="editForm.theme" list="theme-suggestions-edit" />
          <datalist id="theme-suggestions-edit">
            <option v-for="t in themes" :key="t" :value="t" />
          </datalist>
        </div>
        <div class="form-row">
          <label>Reason</label>
          <textarea v-model="editForm.reason" rows="3"></textarea>
        </div>
        <div v-if="editError" class="form-error">{{ editError }}</div>
        <div class="form-actions">
          <button class="btn-cancel" @click="showEditModal = false">Cancel</button>
          <button class="btn-primary" :disabled="editSubmitting" @click="submitEdit">
            {{ editSubmitting ? 'Saving...' : 'Save' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.btn-primary {
  background: #4caf50; color: #fff; border: none; border-radius: 6px;
  padding: 8px 16px; font-size: 13px; cursor: pointer; font-weight: 600;
}
.btn-primary:hover:not(:disabled) { filter: brightness(1.15); }
.btn-primary:disabled { opacity: 0.6; cursor: not-allowed; }

.btn-edit, .btn-del {
  border: none; border-radius: 4px; padding: 4px 10px;
  font-size: 12px; cursor: pointer; font-weight: 600; color: #fff;
}
.btn-edit { background: #666; }
.btn-del { background: #444; color: #f44336; }
.btn-edit:hover { filter: brightness(1.15); }
.btn-del:hover { background: #f44336; color: #fff; }

.btn-cancel {
  background: transparent; color: #999; border: 1px solid #444; border-radius: 6px;
  padding: 8px 16px; font-size: 13px; cursor: pointer;
}
.btn-cancel:hover { border-color: #888; color: #ccc; }

.actions { display: flex; gap: 4px; align-items: center; }
.reason-cell { color: #bbb; font-size: 13px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.date-cell { color: #888; font-size: 13px; }

.market-tag {
  background: #2a3a5e; color: #64b5f6; padding: 2px 8px; border-radius: 4px; font-size: 12px;
}

.group-count {
  font-size: 12px; color: #888; font-weight: 400; margin-left: 8px;
}

.empty-card { text-align: center; padding: 40px 20px; }
.empty-card p { color: #888; margin: 0 0 8px; }
.empty-hint { font-size: 13px; color: #666; }

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
.modal h2 { margin: 0 0 16px; color: #fff; font-size: 18px; }
.form-row { margin-bottom: 14px; }
.form-row label { display: block; color: #aaa; font-size: 13px; margin-bottom: 4px; }
.form-row input, .form-row select, .form-row textarea {
  width: 100%; padding: 8px 12px; background: #2a2a3e; border: 1px solid #444;
  border-radius: 6px; color: #fff; font-size: 14px; box-sizing: border-box;
  font-family: inherit;
}
.form-row input:focus, .form-row select:focus, .form-row textarea:focus { border-color: #4fc3f7; outline: none; }
.form-row textarea { resize: vertical; }
.form-error { color: #ef5350; font-size: 13px; margin-bottom: 12px; }
.form-actions { display: flex; justify-content: flex-end; gap: 10px; margin-top: 20px; }
</style>
