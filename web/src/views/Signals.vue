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
      <h1>Signals</h1>
      <p>System-generated signals & risk alerts</p>
    </div>

    <div class="filters">
      <select v-model="filterSeverity">
        <option value="">All Severity</option>
        <option value="CRITICAL">CRITICAL</option>
        <option value="HIGH">HIGH</option>
        <option value="MEDIUM">MEDIUM</option>
        <option value="LOW">LOW</option>
        <option value="INFO">INFO</option>
      </select>
      <select v-model="filterStatus">
        <option value="">All Status</option>
        <option value="NEW">NEW</option>
        <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
        <option value="RESOLVED">RESOLVED</option>
      </select>
    </div>

    <div v-if="loading" class="loading">Loading</div>

    <template v-else>
      <div v-if="!filtered.length" class="empty">No signals</div>
      <SignalCard v-for="(s, i) in filtered" :key="i" :signal="s" />
    </template>
  </div>
</template>
