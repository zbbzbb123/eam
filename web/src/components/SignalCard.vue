<script setup>
defineProps({ signal: Object })

function severityClass(s) {
  return (s || 'info').toLowerCase()
}

function formatTime(t) {
  if (!t) return ''
  return new Date(t).toLocaleString('en-US')
}
</script>

<template>
  <div class="signal-card" :class="severityClass(signal.severity)">
    <div class="signal-header">
      <span class="badge" :class="'badge-' + severityClass(signal.severity)">
        {{ signal.severity || 'INFO' }}
      </span>
      <span class="signal-title">{{ signal.title || signal.signal_type || '信号' }}</span>
    </div>
    <div class="signal-desc">{{ signal.description || signal.message || '' }}</div>
    <div class="signal-time">{{ formatTime(signal.created_at) }}</div>
  </div>
</template>
