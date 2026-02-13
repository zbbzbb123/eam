<script setup>
import Sidebar from './components/Sidebar.vue'
import { isAuthenticated } from './stores/auth'
</script>

<template>
  <div v-if="isAuthenticated()" class="app-layout">
    <Sidebar />
    <main class="main-content">
      <router-view />
    </main>
  </div>
  <router-view v-else />
</template>
