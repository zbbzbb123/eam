import { createRouter, createWebHistory } from 'vue-router'
import { isAuthenticated } from '../stores/auth'
import Dashboard from '../views/Dashboard.vue'
import Holdings from '../views/Holdings.vue'
import Signals from '../views/Signals.vue'
import Reports from '../views/Reports.vue'
import CollectionReport from '../views/CollectionReport.vue'
import Login from '../views/Login.vue'
import Admin from '../views/Admin.vue'

const routes = [
  { path: '/', name: 'Dashboard', component: Dashboard },
  { path: '/holdings', name: 'Holdings', component: Holdings },
  { path: '/signals', name: 'Signals', component: Signals },
  { path: '/reports', name: 'Reports', component: Reports },
  { path: '/collection', name: 'CollectionReport', component: CollectionReport },
  { path: '/login', name: 'Login', component: Login, meta: { public: true } },
  { path: '/admin', name: 'Admin', component: Admin },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, from, next) => {
  if (to.meta.public || isAuthenticated()) {
    next()
  } else {
    next('/login')
  }
})

export default router
