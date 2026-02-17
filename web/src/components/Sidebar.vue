<script setup>
import { useRouter } from 'vue-router'
import { isAdmin, getUser, clearAuth } from '../stores/auth'

const router = useRouter()

const navItems = [
  { path: '/', icon: '📊', label: 'Dashboard' },
  { path: '/holdings', icon: '💼', label: 'Holdings' },
  { path: '/watchlist', icon: '👀', label: 'Watchlist' },
  { path: '/signals', icon: '🔔', label: 'Signals' },
  { path: '/reports', icon: '📄', label: 'Reports' },
  { path: '/collection', icon: '🕷', label: 'Collection' },
]

function onLogout() {
  clearAuth()
  router.push('/login')
}
</script>

<template>
  <aside class="sidebar">
    <div class="sidebar-logo">
      <span>CGG</span> Alpha Strategy Engine
    </div>
    <nav class="sidebar-nav">
      <router-link v-for="item in navItems" :key="item.path" :to="item.path">
        <span class="nav-icon">{{ item.icon }}</span>
        <span class="nav-label">{{ item.label }}</span>
      </router-link>
      <router-link v-if="isAdmin()" to="/admin">
        <span class="nav-icon">🔑</span>
        <span class="nav-label">Invitations</span>
      </router-link>
    </nav>
    <div class="sidebar-footer">
      <div class="sidebar-user">{{ getUser()?.username || '' }}</div>
      <button class="logout-btn" @click="onLogout">Logout</button>
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
