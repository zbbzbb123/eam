<script setup>
import { useRouter } from 'vue-router'
import { isAdmin, getUser, clearAuth } from '../stores/auth'

const router = useRouter()

const navItems = [
  { path: '/', icon: '📊', label: '仪表盘' },
  { path: '/holdings', icon: '💼', label: '持仓管理' },
  { path: '/signals', icon: '🔔', label: '信号中心' },
  { path: '/reports', icon: '📄', label: '报告分析' },
  { path: '/collection', icon: '🕷', label: '采集日报' },
]

function onLogout() {
  clearAuth()
  router.push('/login')
}
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
      <router-link v-if="isAdmin()" to="/admin">
        <span class="nav-icon">🔑</span>
        <span class="nav-label">邀请码管理</span>
      </router-link>
    </nav>
    <div class="sidebar-footer">
      <div class="sidebar-user">{{ getUser()?.username || '' }}</div>
      <button class="logout-btn" @click="onLogout">退出登录</button>
    </div>
  </aside>
</template>

<style scoped>
.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--border);
}

.sidebar-user {
  color: var(--text-muted);
  font-size: 13px;
  margin-bottom: 10px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.logout-btn {
  width: 100%;
  padding: 8px 0;
  background: transparent;
  color: var(--text-muted);
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  transition: all 0.2s;
}

.logout-btn:hover {
  color: #fff;
  border-color: var(--red);
  background: rgba(255, 82, 82, 0.1);
}
</style>
