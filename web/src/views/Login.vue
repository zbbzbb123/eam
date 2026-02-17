<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { login, register } from '../api'
import { setAuth } from '../stores/auth'

const router = useRouter()

const activeTab = ref('login')
const form = ref({ username: '', password: '', invitation_code: '' })
const error = ref('')
const submitting = ref(false)

async function onSubmit() {
  error.value = ''
  const { username, password, invitation_code } = form.value
  if (!username || !password) {
    error.value = 'Please enter username and password'
    return
  }
  if (activeTab.value === 'register' && !invitation_code) {
    error.value = 'Please enter invitation code'
    return
  }
  submitting.value = true
  try {
    const data = activeTab.value === 'login'
      ? await login(username, password)
      : await register(username, password, invitation_code)
    setAuth(data.token, { user_id: data.user_id, username: data.username, is_admin: data.is_admin })
    router.push('/')
  } catch (e) {
    error.value = e.response?.data?.detail || (activeTab.value === 'login' ? 'Login failed' : 'Registration failed')
  } finally {
    submitting.value = false
  }
}

function switchTab(tab) {
  activeTab.value = tab
  error.value = ''
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="login-logo">
        <span>CGG</span> Alpha Strategy Engine
      </div>

      <div class="tab-bar">
        <button :class="['tab-btn', { active: activeTab === 'login' }]" @click="switchTab('login')">Login</button>
        <button :class="['tab-btn', { active: activeTab === 'register' }]" @click="switchTab('register')">Register</button>
      </div>

      <form @submit.prevent="onSubmit">
        <div class="form-row">
          <label>Username</label>
          <input v-model="form.username" type="text" placeholder="Enter username" autocomplete="username" />
        </div>
        <div class="form-row">
          <label>Password</label>
          <input v-model="form.password" type="password" placeholder="Enter password" autocomplete="current-password" />
        </div>
        <div v-if="activeTab === 'register'" class="form-row">
          <label>Invitation Code</label>
          <input v-model="form.invitation_code" type="text" placeholder="Enter invitation code" />
        </div>

        <div v-if="error" class="form-error">{{ error }}</div>

        <button class="submit-btn" type="submit" :disabled="submitting">
          {{ submitting ? 'Please wait...' : (activeTab === 'login' ? 'Login' : 'Register') }}
        </button>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-dark);
}

.login-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 36px;
  width: 400px;
  max-width: 90vw;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
}

.login-logo {
  font-size: 22px;
  font-weight: 700;
  color: #fff;
  text-align: center;
  margin-bottom: 28px;
  letter-spacing: 1px;
}

.login-logo span {
  color: var(--blue);
}

.tab-bar {
  display: flex;
  gap: 0;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border);
}

.tab-btn {
  flex: 1;
  background: none;
  border: none;
  padding: 10px 0;
  font-size: 15px;
  color: var(--text-muted);
  cursor: pointer;
  border-bottom: 2px solid transparent;
  transition: all 0.2s;
}

.tab-btn.active {
  color: #fff;
  border-bottom-color: var(--blue);
}

.tab-btn:hover:not(.active) {
  color: var(--text);
}

.form-row {
  margin-bottom: 16px;
}

.form-row label {
  display: block;
  color: var(--text-muted);
  font-size: 13px;
  margin-bottom: 6px;
}

.form-row input {
  width: 100%;
  padding: 10px 14px;
  background: #2a2a3e;
  border: 1px solid #444;
  border-radius: 6px;
  color: #fff;
  font-size: 14px;
  box-sizing: border-box;
}

.form-row input:focus {
  border-color: var(--blue);
  outline: none;
}

.form-row input::placeholder {
  color: #555;
}

.form-error {
  color: #ef5350;
  font-size: 13px;
  margin-bottom: 14px;
}

.submit-btn {
  width: 100%;
  padding: 11px 0;
  background: var(--blue);
  color: #fff;
  border: none;
  border-radius: 6px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  margin-top: 8px;
  transition: filter 0.2s;
}

.submit-btn:hover:not(:disabled) {
  filter: brightness(1.15);
}

.submit-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
