import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'
import Holdings from '../views/Holdings.vue'
import Signals from '../views/Signals.vue'
import Reports from '../views/Reports.vue'

const routes = [
  { path: '/', name: 'Dashboard', component: Dashboard },
  { path: '/holdings', name: 'Holdings', component: Holdings },
  { path: '/signals', name: 'Signals', component: Signals },
  { path: '/reports', name: 'Reports', component: Reports },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
