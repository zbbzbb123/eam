import { reactive } from 'vue'

const TOKEN_KEY = 'eam_token'
const USER_KEY = 'eam_user'

const state = reactive({
  token: localStorage.getItem(TOKEN_KEY) || null,
  user: JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
})

export function getToken() {
  return state.token
}

export function getUser() {
  return state.user
}

export function isAuthenticated() {
  return !!state.token
}

export function isAdmin() {
  return !!state.user?.is_admin
}

export function setAuth(token, user) {
  state.token = token
  state.user = user
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearAuth() {
  state.token = null
  state.user = null
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}
