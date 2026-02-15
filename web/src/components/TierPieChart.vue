<script setup>
import { use } from 'echarts/core'
import { PieChart } from 'echarts/charts'
import { TitleComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'
import { computed } from 'vue'

use([PieChart, TitleComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const props = defineProps({ tiers: Object })

const option = computed(() => ({
  tooltip: { trigger: 'item', formatter: '{b}: {d}%' },
  legend: { bottom: 0, textStyle: { color: '#8892a4' } },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    center: ['50%', '45%'],
    label: { color: '#e0e0e0', formatter: '{b}\n{d}%' },
    data: [
      { value: props.tiers?.CORE?.current_pct ?? 50, name: 'CORE', itemStyle: { color: '#00c853' } },
      { value: props.tiers?.GROWTH?.current_pct ?? 30, name: 'GROWTH', itemStyle: { color: '#ff9800' } },
      { value: props.tiers?.GAMBLE?.current_pct ?? 20, name: 'GAMBLE', itemStyle: { color: '#ff5252' } },
    ],
  }],
}))
</script>

<template>
  <v-chart :option="option" autoresize style="height: 300px" />
</template>
