import axios from 'axios'
import { getToken, clearAuth } from '../stores/auth'

const api = axios.create({
  baseURL: '/api',
  timeout: 10000,
})

// AI endpoints (longer timeout)
const aiApi = axios.create({ baseURL: '/api', timeout: 120000 })

// Attach Authorization header to both instances
function attachAuth(config) {
  const token = getToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
}

api.interceptors.request.use(attachAuth)
aiApi.interceptors.request.use(attachAuth)

// Handle 401 → clear auth and redirect to /login
function handle401(error) {
  if (error.response?.status === 401) {
    clearAuth()
    if (window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
  }
  return Promise.reject(error)
}

api.interceptors.response.use(r => r, handle401)
aiApi.interceptors.response.use(r => r, handle401)

// Graceful error handling - return default data when backend is unavailable
function safe(promise, fallback) {
  return promise.then(r => r.data).catch(() => fallback)
}

// === Auth API ===
export function login(username, password) {
  return api.post('/auth/login', { username, password }).then(r => r.data)
}

export function register(username, password, invitation_code) {
  return api.post('/auth/register', { username, password, invitation_code }).then(r => r.data)
}

export function getMe() {
  return api.get('/auth/me').then(r => r.data)
}

export function createInvitationCodes(count, note) {
  return api.post('/auth/invitation-codes', { count, note }).then(r => r.data)
}

export function getInvitationCodes() {
  return safe(api.get('/auth/invitation-codes'), [])
}

// === Portfolio & Holdings ===
export function getPortfolioSummary() {
  return safe(api.get('/portfolio/summary'), {
    total_value: 0,
    tiers: { CORE: { current_pct: 0, target_pct: 40 }, GROWTH: { current_pct: 0, target_pct: 30 }, GAMBLE: { current_pct: 0, target_pct: 30 } },
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

export function getSchedulerJobs() {
  return safe(api.get('/scheduler/jobs'), [])
}

export function getAnalyzers() {
  return safe(api.get('/analyzers'), [])
}

export function runAnalyzer(id) {
  return api.post(`/analyzers/${id}/run`).then(r => r.data).catch(() => null)
}

// === AI endpoints ===
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

export function previewTransaction(holdingId, data) {
  return api.post(`/holdings/${holdingId}/preview-transaction`, data).then(r => r.data)
}

export function updatePosition(holdingId, data) {
  return api.post(`/holdings/${holdingId}/update-position`, data).then(r => r.data)
}

export function getTransactions(holdingId) {
  return safe(api.get(`/holdings/${holdingId}/transactions`), [])
}

// === Pre-generated report endpoints ===
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

// === Watchlist ===
export function getWatchlist() {
  return safe(api.get('/watchlist'), [])
}

export function addWatchlistItem(data) {
  return api.post('/watchlist', data).then(r => r.data)
}

export function updateWatchlistItem(id, data) {
  return api.patch(`/watchlist/${id}`, data).then(r => r.data)
}

export function deleteWatchlistItem(id) {
  return api.delete(`/watchlist/${id}`)
}

// === Collection report ===
export function getCollectionReportRange(params = {}) {
  return safe(api.get('/collection-report/range', { params }), { source_names: [], days: [] })
}

export function getCollectionReport(reportDate) {
  return safe(api.get('/collection-report', { params: { report_date: reportDate } }), null)
}
