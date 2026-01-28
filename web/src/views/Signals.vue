<script setup>
import { ref, onMounted, computed } from 'vue'
import SignalCard from '../components/SignalCard.vue'
import { getSignals } from '../api'

const signals = ref([])
const loading = ref(true)
const filterSeverity = ref('')
const filterStatus = ref('')

onMounted(async () => {
  signals.value = await getSignals({ limit: 100 })
  loading.value = false
})

const filtered = computed(() => {
  let list = signals.value
  if (filterSeverity.value) list = list.filter(s => s.severity === filterSeverity.value)
  if (filterStatus.value) list = list.filter(s => s.status === filterStatus.value)
  return list
})
</script>

<template>
  <div>
    <div class="page-header">
      <h1>信号中心</h1>
      <p>系统生成的投资信号与风险提醒</p>
    </div>

    <div class="filters">
      <select v-model="filterSeverity">
        <option value="">全部级别</option>
        <option value="CRITICAL">CRITICAL</option>
        <option value="HIGH">HIGH</option>
        <option value="MEDIUM">MEDIUM</option>
        <option value="LOW">LOW</option>
        <option value="INFO">INFO</option>
      </select>
      <select v-model="filterStatus">
        <option value="">全部状态</option>
        <option value="NEW">NEW</option>
        <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
        <option value="RESOLVED">RESOLVED</option>
      </select>
    </div>

    <div v-if="loading" class="loading">加载中</div>

    <template v-else>
      <div v-if="!filtered.length" class="empty">暂无信号</div>
      <SignalCard v-for="(s, i) in filtered" :key="i" :signal="s" />
    </template>
  </div>
</template>
