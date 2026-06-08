<template>
  <div class="auth-container">
    <el-card class="auth-card">
      <h2 class="title">智能作业批改系统</h2>
      <el-tabs v-model="activeTab" class="auth-tabs">
        <el-tab-pane label="登录" name="login">
          <el-form :model="loginForm" @submit.prevent="handleLogin" :rules="rules" ref="loginFormRef">
            <el-form-item prop="routeType">
              <el-radio-group v-model="loginForm.routeType" class="route-group">
                <el-radio-button label="default">默认路线</el-radio-button>
                <el-radio-button label="baidu">百度路线</el-radio-button>
              </el-radio-group>
            </el-form-item>
            <el-form-item prop="username">
              <el-input v-model="loginForm.username" placeholder="用户名" prefix-icon="User" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="loginForm.password" type="password" placeholder="密码" prefix-icon="Lock" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" native-type="submit" :loading="loading" class="submit-btn">登录</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
        
        <el-tab-pane label="注册" name="register">
          <el-form :model="registerForm" @submit.prevent="handleRegister" :rules="rules" ref="registerFormRef">
            <el-form-item prop="username">
              <el-input v-model="registerForm.username" placeholder="用户名" prefix-icon="User" />
            </el-form-item>
            <el-form-item prop="email">
              <el-input v-model="registerForm.email" placeholder="邮箱" prefix-icon="Message" />
            </el-form-item>
            <el-form-item prop="password">
              <el-input v-model="registerForm.password" type="password" placeholder="密码" prefix-icon="Lock" show-password />
            </el-form-item>
            <el-form-item>
              <el-button type="primary" native-type="submit" :loading="loading" class="submit-btn">注册</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../utils/api'

const emit = defineEmits<{
  (e: 'login-success', user: any): void
}>()

const activeTab = ref('login')
const loading = ref(false)

const loginForm = reactive({
  username: '',
  password: '',
  routeType: 'default'
})

const registerForm = reactive({
  username: '',
  email: '',
  password: ''
})

const rules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
  email: [
    { required: true, message: '请输入邮箱', trigger: 'blur' },
    { type: 'email', message: '请输入正确的邮箱地址', trigger: ['blur', 'change'] }
  ]
}

const handleLogin = async () => {
  if (!loginForm.username || !loginForm.password) return
  loading.value = true
  try {
    const res: any = await api.post('/users/login', {
      username: loginForm.username,
      password: loginForm.password
    })
    localStorage.setItem('token', res.access_token)
    
    emit('login-success', { username: loginForm.username, routeType: loginForm.routeType })
    ElMessage.success('登录成功')
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '登录失败')
  } finally {
    loading.value = false
  }
}

const handleRegister = async () => {
  if (!registerForm.username || !registerForm.password) return
  loading.value = true
  try {
    await api.post('/users/register', {
      username: registerForm.username,
      email: registerForm.email,
      password: registerForm.password
    })
    ElMessage.success('注册成功，请登录')
    activeTab.value = 'login'
    loginForm.username = registerForm.username
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || '注册失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f5f7fa;
}
.auth-card {
  width: 400px;
  border-radius: 8px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}
.title {
  text-align: center;
  margin-bottom: 20px;
  color: #303133;
}
.route-group {
  width: 100%;
  display: flex;
  justify-content: center;
}
.route-group .el-radio-button {
  flex: 1;
}
:deep(.route-group .el-radio-button__inner) {
  width: 100%;
}
.submit-btn {
  width: 100%;
}
</style>
