<script setup>
import { ref, onMounted, computed, watch } from 'vue'
import { use } from 'echarts/core'
import { HeatmapChart, BarChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, VisualMapComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { getCollectionReportRange, getCollectionReport } from '../api'

use([HeatmapChart, BarChart, GridComponent, TooltipComponent, VisualMapComponent, CanvasRenderer])

const rangeData = ref(null)
const selectedDate = ref(null)
const detail = ref(null)
const loading = ref(true)
const detailLoading = ref(false)

// Date range controls
const days = ref(7)

function formatDate(d) {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

async function fetchRange() {
  loading.value = true
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - days.value + 1)
  rangeData.value = await getCollectionReportRange({
    start: formatDate(start),
    end: formatDate(end),
  })
  loading.value = false
  // Auto-select the latest day with data
  if (rangeData.value?.days?.length) {
    const withData = rangeData.value.days.filter(d => d.total > 0)
    if (withData.length) {
      selectedDate.value = withData[withData.length - 1].date
    }
  }
}

onMounted(fetchRange)

watch(days, fetchRange)

watch(selectedDate, async (val) => {
  if (!val) { detail.value = null; return }
  detailLoading.value = true
  detail.value = await getCollectionReport(val)
  detailLoading.value = false
})

// Heatmap chart option
const heatmapOption = computed(() => {
  if (!rangeData.value?.days?.length) return {}
  const sourceNames = rangeData.value.source_names
  const dayList = rangeData.value.days
  const dates = dayList.map(d => d.date.slice(5)) // MM-DD

  // Build heatmap data: [x=dateIdx, y=sourceIdx, value=count]
  const data = []
  dayList.forEach((day, x) => {
    sourceNames.forEach((name, y) => {
      data.push([x, y, day.counts[name] || 0])
    })
  })

  const maxVal = Math.max(...data.map(d => d[2]), 1)

  return {
    tooltip: {
      formatter(p) {
        const d = dayList[p.data[0]]
        const name = sourceNames[p.data[1]]
        return `${d.date} ${name}<br/><b>${p.data[2]}</b> records`
      },
    },
    grid: { left: 100, right: 40, top: 10, bottom: 40 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#8892a4', fontSize: 12 },
      axisLine: { lineStyle: { color: '#2a3a5e' } },
      splitArea: { show: false },
    },
    yAxis: {
      type: 'category',
      data: sourceNames,
      axisLabel: { color: '#8892a4', fontSize: 12 },
      axisLine: { lineStyle: { color: '#2a3a5e' } },
      splitArea: { show: false },
    },
    visualMap: {
      min: 0,
      max: maxVal,
      calculable: false,
      orient: 'horizontal',
      left: 'center',
      bottom: 0,
      show: false,
      inRange: {
        color: ['#1a2a50', '#0d47a1', '#1565c0', '#1e88e5', '#42a5f5', '#64b5f6'],
      },
    },
    series: [{
      type: 'heatmap',
      data,
      label: {
        show: true,
        color: '#e0e0e0',
        fontSize: 11,
        formatter(p) { return p.data[2] || '' },
      },
      itemStyle: {
        borderColor: '#1a1a2e',
        borderWidth: 2,
        borderRadius: 3,
      },
      emphasis: {
        itemStyle: { borderColor: '#448aff', borderWidth: 2 },
      },
    }],
  }
})

// Daily total bar chart
const barOption = computed(() => {
  if (!rangeData.value?.days?.length) return {}
  const dayList = rangeData.value.days
  const dates = dayList.map(d => d.date.slice(5))
  const totals = dayList.map(d => d.total)

  return {
    tooltip: {
      formatter(p) {
        const d = dayList[p.dataIndex]
        return `${d.date}<br/>Total <b>${d.total}</b> records<br/>Sources ${d.sources_collected}/${d.sources_total}`
      },
    },
    grid: { left: 50, right: 20, top: 10, bottom: 30 },
    xAxis: {
      type: 'category',
      data: dates,
      axisLabel: { color: '#8892a4' },
      axisLine: { lineStyle: { color: '#2a3a5e' } },
    },
    yAxis: {
      type: 'value',
      axisLabel: { color: '#8892a4' },
      splitLine: { lineStyle: { color: '#2a3a5e' } },
    },
    series: [{
      type: 'bar',
      data: totals.map((v, i) => ({
        value: v,
        itemStyle: {
          color: dayList[i].date === selectedDate.value ? '#42a5f5' : '#1565c0',
          borderRadius: [3, 3, 0, 0],
        },
      })),
      barWidth: '60%',
    }],
  }
})

function onBarClick(params) {
  if (params.dataIndex != null && rangeData.value?.days?.[params.dataIndex]) {
    selectedDate.value = rangeData.value.days[params.dataIndex].date
  }
}
</script>

<template>
  <div>
    <div class="page-header">
      <h1>Collection</h1>
      <p>Daily data collection dashboard</p>
    </div>

    <!-- Range selector -->
    <div class="filters">
      <button
        v-for="d in [7, 14, 30]"
        :key="d"
        :class="['range-btn', { active: days === d }]"
        @click="days = d"
      >
        {{ d }}d
      </button>
    </div>

    <div v-if="loading" class="loading">Loading</div>

    <template v-else>
      <!-- Daily total bar -->
      <div class="card" style="margin-bottom: 20px">
        <div class="card-title">Daily Ingestion (click bar for details)</div>
        <v-chart
          :option="barOption"
          autoresize
          style="height: 180px"
          @click="onBarClick"
        />
      </div>

      <!-- Heatmap -->
      <div class="card" style="margin-bottom: 20px">
        <div class="card-title">Source x Date Heatmap</div>
        <v-chart :option="heatmapOption" autoresize style="height: 340px" />
      </div>

      <!-- Detail panel -->
      <div v-if="selectedDate" class="card">
        <div class="card-title">
          {{ selectedDate }} Details
          <span v-if="detail" class="detail-summary">
            {{ detail.total_records }} records, {{ detail.sources_collected }} sources
          </span>
        </div>

        <div v-if="detailLoading" class="loading" style="padding: 20px">Loading</div>

        <table v-else-if="detail" class="data-table">
          <thead>
            <tr>
              <th>Source</th>
              <th>Records</th>
              <th>Status</th>
              <th>Summary</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="s in detail.sections" :key="s.table">
              <td>{{ s.name }}</td>
              <td>{{ s.count }}</td>
              <td>
                <span :class="['status-dot', s.count > 0 ? 'ok' : 'empty']"></span>
                {{ s.count > 0 ? 'OK' : 'Empty' }}
              </td>
              <td class="detail-cell">{{ s.detail || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </template>
  </div>
</template>

<style scoped>
.range-btn {
  background: var(--bg-accent);
  color: var(--text-muted);
  border: 1px solid var(--border);
  padding: 6px 16px;
  border-radius: var(--radius);
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}
.range-btn.active {
  background: var(--blue);
  color: #fff;
  border-color: var(--blue);
}
.range-btn:hover:not(.active) {
  background: var(--bg-hover);
  color: #fff;
}

.detail-summary {
  float: right;
  font-size: 13px;
  color: var(--blue);
  font-weight: 400;
  text-transform: none;
  letter-spacing: 0;
}

.detail-cell {
  max-width: 400px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--text-muted);
  font-size: 12px;
}

.status-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
  vertical-align: middle;
}
.status-dot.ok { background: var(--green); }
.status-dot.empty { background: var(--gray); }
</style>
