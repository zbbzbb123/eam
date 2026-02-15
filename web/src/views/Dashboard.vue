<script setup>
import { ref, onMounted, computed } from 'vue'
import { use } from 'echarts/core'
import { BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import TierPieChart from '../components/TierPieChart.vue'
import SignalCard from '../components/SignalCard.vue'
import { getPortfolioSummary, getSignals, getSchedulerJobs, getHoldingsSummary, getPortfolioAdvice } from '../api'

use([BarChart, GridComponent, TooltipComponent, CanvasRenderer])

const summary = ref(null)
const signals = ref([])
const jobs = ref([])
const holdings = ref([])
const loading = ref(true)
const aiAdvice = ref(null)
const aiAdviceLoading = ref(false)

onMounted(async () => {
  const [s, sig, j, h] = await Promise.all([
    getPortfolioSummary(),
    getSignals({ limit: 5 }),
    getSchedulerJobs(),
    getHoldingsSummary(),
  ])
  summary.value = s
  signals.value = Array.isArray(sig) ? sig.slice(0, 5) : []
  jobs.value = Array.isArray(j) ? j : []
  holdings.value = Array.isArray(h) ? h : []
  loading.value = false
})

const tiers = computed(() => summary.value?.tiers || {})

const deviationOption = computed(() => {
  const t = tiers.value
  const names = ['CORE', 'GROWTH', 'GAMBLE']
  const deviations = names.map(n => {
    const tier = t[n] || {}
    return ((tier.current_pct || 0) - (tier.target_pct || 0)).toFixed(1)
  })
  return {
    tooltip: {},
    xAxis: { type: 'category', data: names, axisLabel: { color: '#8892a4' }, axisLine: { lineStyle: { color: '#2a3a5e' } } },
    yAxis: { type: 'value', axisLabel: { color: '#8892a4', formatter: '{value}%' }, splitLine: { lineStyle: { color: '#2a3a5e' } } },
    series: [{
      type: 'bar',
      data: deviations.map((v, i) => ({
        value: v,
        itemStyle: { color: ['#00c853', '#ff9800', '#ff5252'][i] },
      })),
      barWidth: 40,
    }],
  }
})

const totalValue = computed(() => {
  const v = summary.value?.total_value ?? 0
  return v.toLocaleString('zh-CN', { minimumFractionDigits: 2 })
})

const nextJob = computed(() => {
  if (!jobs.value.length) return '无'
  return jobs.value[0].name || jobs.value[0].id || '已安排'
})

async function onGetAdvice() {
  aiAdviceLoading.value = true
  aiAdvice.value = await getPortfolioAdvice()
  aiAdviceLoading.value = false
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
      <!-- Stats -->
      <div class="stats-grid">
        <div class="card">
          <div class="card-title">组合总价值</div>
          <div class="stat-value">¥{{ totalValue }}</div>
        </div>
        <div class="card">
          <div class="card-title">持仓数量</div>
          <div class="stat-value">{{ holdings.length }}</div>
        </div>
        <div class="card">
          <div class="card-title">活跃信号</div>
          <div class="stat-value">{{ signals.length }}</div>
        </div>
        <div class="card">
          <div class="card-title">下次任务</div>
          <div class="stat-value" style="font-size:16px">{{ nextJob }}</div>
        </div>
      </div>

      <!-- Charts -->
      <div class="grid-2">
        <div class="card">
          <div class="card-title">分层配置</div>
          <TierPieChart :tiers="tiers" />
        </div>
        <div class="card">
          <div class="card-title">分层偏离度</div>
          <v-chart :option="deviationOption" autoresize style="height: 300px" />
        </div>
      </div>

      <!-- AI Portfolio Advice -->
      <div class="card">
        <div class="card-title" style="display:flex;justify-content:space-between;align-items:center">
          <span>AI 投资建议</span>
          <button class="ai-btn" :disabled="aiAdviceLoading" @click="onGetAdvice">
            {{ aiAdviceLoading ? 'AI 分析中...' : 'AI投资建议' }}
          </button>
        </div>
        <div v-if="aiAdviceLoading" style="color:#8892a4;padding:20px 0;font-size:14px">AI 分析中...</div>
        <div v-else-if="aiAdvice" class="ai-advice-content">
          <pre style="color:#e0e6ed;white-space:pre-wrap;font-size:13px;line-height:1.7;font-family:inherit;background:none;margin:0">{{ typeof aiAdvice === 'string' ? aiAdvice : JSON.stringify(aiAdvice, null, 2) }}</pre>
        </div>
        <div v-else class="empty">点击按钮获取 AI 投资建议</div>
      </div>

      <!-- Recent Signals -->
      <div class="card">
        <div class="card-title">最近信号</div>
        <div v-if="!signals.length" class="empty">暂无信号</div>
        <SignalCard v-for="(s, i) in signals" :key="i" :signal="s" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.ai-btn {
  background: linear-gradient(135deg, #4fc3f7, #0288d1);
  color: #fff; border: none; border-radius: 6px; padding: 6px 14px;
  font-size: 12px; cursor: pointer; font-weight: 600;
}
.ai-btn:disabled { opacity: 0.6; cursor: not-allowed; }
.ai-btn:hover:not(:disabled) { filter: brightness(1.15); }
</style>
