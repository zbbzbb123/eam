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

export function getSignals(params = {}) {
  return safe(api.get('/signals', { params }), [])
}

export function getWeeklyReport() {
  return safe(api.get('/reports/weekly'), null)
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
