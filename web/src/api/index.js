import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// Graceful error handling - return default data when backend is unavailable
function safe(promise, fallback) {
  return promise.then(r => r.data).catch(() => fallback)
}

export function getPortfolioSummary() {
  return safe(api.get('/portfolio/summary'), {
    total_value: 0,
    tiers: { STABLE: { current_pct: 0, target_pct: 50 }, MODERATE: { current_pct: 0, target_pct: 30 }, GAMBLE: { current_pct: 0, target_pct: 20 } },
  })
}

export function getHoldingsSummary() {
  return safe(api.get('/portfolio/holdings-summary'), [])
}

export function getHoldings(params = {}) {
  return safe(api.get('/holdings', { params }), [])
}

export function getHolding(id) {
  return safe(api.get(`/holdings/${id}`), null)
}

export function createHolding(data) {
  return api.post('/holdings', data).then(r => r.data)
}

export function createTransaction(holdingId, data) {
  return api.post(`/holdings/${holdingId}/transactions`, data).then(r => r.data)
}

export function updateHolding(id, data) {
  return api.patch(`/holdings/${id}`, data).then(r => r.data)
}

export function deleteHolding(id) {
  return api.delete(`/holdings/${id}`)
}

export function syncPrices() {
  return api.post('/portfolio/sync-prices', null, { timeout: 60000 }).then(r => r.data).catch(() => null)
}

export function getSignals(params = {}) {
  return safe(api.get('/signals', { params }), [])
}

export function getWeeklyReport() {
  return safe(api.get('/reports/weekly'), null)
}

export function getDailyReport() {
  return safe(api.get('/reports/daily'), null)
}

export function getEnhancedWeeklyReport() {
  return safe(api.get('/reports/weekly/enhanced'), null)
}

export function getSchedulerJobs() {
  return safe(api.get('/scheduler/jobs'), [])
}

export function getAnalyzers() {
  return safe(api.get('/analyzers'), [])
}

export function runAnalyzer(id) {
  return api.post(`/analyzers/${id}/run`).then(r => r.data).catch(() => null)
}

// AI endpoints (longer timeout)
const aiApi = axios.create({ baseURL: '/api', timeout: 120000 })

export function analyzeHolding(holdingId, quality = true) {
  return aiApi.post(`/ai/analyze-holding/${holdingId}`, null, { params: { quality } }).then(r => r.data).catch(() => null)
}

export function analyzeAllHoldings() {
  return aiApi.post('/ai/analyze-all').then(r => r.data).catch(() => null)
}

export function getPortfolioAdvice() {
  return aiApi.post('/ai/portfolio-advice').then(r => r.data).catch(() => null)
}

export function enhanceReport() {
  return aiApi.post('/ai/enhance-report').then(r => r.data).catch(() => null)
}

export function classifyTier(symbol, market) {
  return aiApi.post('/ai/classify-tier', { symbol, market }).then(r => r.data).catch(() => ({ tier: 'medium' }))
}

// Pre-generated report endpoints
export function getDailyReportList(limit = 10) {
  return safe(api.get('/reports/daily/list', { params: { limit } }), [])
}
export function getDailyReportDetail(id) {
  return safe(api.get(`/reports/daily/${id}`), null)
}
export function getWeeklyReportList(limit = 10) {
  return safe(api.get('/reports/weekly/list', { params: { limit } }), [])
}
export function getWeeklyReportDetail(id) {
  return safe(api.get(`/reports/weekly/${id}`), null)
}
export function triggerDailyReport() {
  return safe(aiApi.post('/reports/daily/generate'), null)
}
export function triggerWeeklyReport() {
  return safe(aiApi.post('/reports/weekly/generate'), null)
}

// Collection report
export function getCollectionReportRange(params = {}) {
  return safe(api.get('/collection-report/range', { params }), { source_names: [], days: [] })
}

export function getCollectionReport(reportDate) {
  return safe(api.get('/collection-report', { params: { report_date: reportDate } }), null)
}
