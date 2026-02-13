<template>
  <div class="score-gauge" :style="{ height: containerHeight }">
    <v-chart :option="chartOption" autoresize />
    <div v-if="label" class="gauge-label">{{ label }}</div>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import { use } from 'echarts/core'
import { GaugeChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

use([GaugeChart, CanvasRenderer])

const props = defineProps({
  score: Number,
  size: { type: String, default: 'large' },
  label: { type: String, default: '' },
})

const isLarge = computed(() => props.size === 'large')
const containerHeight = computed(() => (isLarge.value ? '200px' : '140px'))

const chartOption = computed(() => ({
  series: [
    {
      type: 'gauge',
      min: 0,
      max: 100,
      startAngle: 200,
      endAngle: -20,
      data: [{ value: props.score ?? 0 }],
      axisLine: {
        lineStyle: {
          width: isLarge.value ? 15 : 10,
          color: [
            [0.25, '#ff5252'],
            [0.5, '#ff9800'],
            [0.75, '#ffeb3b'],
            [1, '#00c853'],
          ],
        },
      },
      pointer: {
        length: '60%',
        width: 6,
      },
      axisTick: { show: false },
      splitLine: { show: false },
      axisLabel: {
        color: '#8892a4',
        distance: isLarge.value ? 20 : 15,
        fontSize: isLarge.value ? 12 : 10,
      },
      detail: {
        formatter: '{value}',
        fontSize: isLarge.value ? 24 : 16,
        color: '#e0e0e0',
        offsetCenter: [0, '70%'],
      },
    },
  ],
}))
</script>

<style scoped>
.score-gauge {
  position: relative;
  width: 100%;
}

.gauge-label {
  text-align: center;
  color: var(--text-muted, #8892a4);
  font-size: 12px;
  margin-top: -12px;
}
</style>
