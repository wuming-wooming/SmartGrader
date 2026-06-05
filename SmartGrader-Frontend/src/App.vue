<template>
  <div id="app">
    <Auth v-if="currentView === 'auth'" @login-success="handleLoginSuccess" />
    <Workspace v-else-if="currentView === 'workspace'" :user="currentUser" @logout="handleLogout" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import Auth from './components/Auth.vue'
import Workspace from './components/Workspace.vue'
import api from './utils/api'

const currentView = ref<'auth' | 'workspace'>('auth')
const currentUser = ref<any>(null)

const checkAuth = async () => {
  const token = localStorage.getItem('token')
  if (!token) {
    currentView.value = 'auth'
    return
  }
  
  try {
    await api.get('/users/protected')
    
    let username = 'User'
    try {
      // 解析 JWT Token 获取用户名
      const base64Url = token.split('.')[1]
      const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
      const jsonPayload = decodeURIComponent(
        window.atob(base64).split('').map(function(c) {
          return '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2)
        }).join('')
      )
      const payload = JSON.parse(jsonPayload)
      if (payload.username) {
        username = payload.username
      }
    } catch (e) {
      console.error('Failed to parse token', e)
    }

    currentUser.value = { username }
    currentView.value = 'workspace'
  } catch (error) {
    // 静默处理，不输出错误日志
    localStorage.removeItem('token')
    currentView.value = 'auth'
  }
}

const handleLoginSuccess = () => {
  checkAuth()
}

const handleLogout = () => {
  currentView.value = 'auth'
  currentUser.value = null
}

const handleAuthExpired = () => {
  handleLogout()
}

onMounted(() => {
  checkAuth()
  window.addEventListener('auth-expired', handleAuthExpired)
})

onUnmounted(() => {
  window.removeEventListener('auth-expired', handleAuthExpired)
})
</script>

<style>
#app {
  height: 100vh;
  width: 100vw;
}
</style>
