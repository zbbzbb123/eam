<script setup>
const navItems = [
  { path: '/', icon: '📊', label: '仪表盘' },
  { path: '/holdings', icon: '💼', label: '持仓管理' },
  { path: '/signals', icon: '🔔', label: '信号中心' },
  { path: '/reports', icon: '📄', label: '周报分析' },
]
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-logo">
      <span>EAM</span> 投资系统
    </div>
    <nav class="sidebar-nav">
      <router-link v-for="item in navItems" :key="item.path" :to="item.path">
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-label">{{ item.label }}</span>
      </router-link>
    </nav>
  </aside>
</template>
