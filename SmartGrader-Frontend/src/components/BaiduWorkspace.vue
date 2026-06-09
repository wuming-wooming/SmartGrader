<template>
  <div class="workspace-container">
    <el-header class="header">
      <div class="logo">智能作业批改系统 (百度路线)</div>
      <div class="user-info">
        <span class="welcome">欢迎，{{ user?.username }}</span>
        <el-button link type="primary" @click="historyVisible = true">历史记录</el-button>
        <el-button link type="danger" @click="handleLogout">退出登录</el-button>
      </div>
    </el-header>

    <el-main class="main-content">
      <el-card class="workspace-card">
        <el-steps :active="currentStepIndex" finish-status="success" align-center class="steps">
          <el-step title="上传作业" />
          <el-step title="百度智能批改" />
          <el-step title="查看报告" />
        </el-steps>

        <div class="view-container">
          <BaiduUpload v-if="workspaceStep === 'upload'" @uploaded="handleUploaded" />
          <BaiduProcessing 
            v-else-if="workspaceStep === 'processing'" 
            :taskId="gradingTaskId"
            @complete="handleGradingComplete"
          />
          <BaiduResult 
            v-else-if="workspaceStep === 'result'" 
            :taskId="gradingTaskId" 
            @reset="resetWorkspace" 
          />
        </div>
      </el-card>
    </el-main>
    <HistoryDrawer v-model="historyVisible" @view-result="handleViewHistoryResult" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import BaiduUpload from './BaiduUpload.vue'
import BaiduProcessing from './BaiduProcessing.vue'
import BaiduResult from './BaiduResult.vue'
import HistoryDrawer from './HistoryDrawer.vue'

const props = defineProps<{
  user: any
}>()

const emit = defineEmits<{
  (e: 'logout'): void
}>()

const workspaceStep = ref<'upload' | 'processing' | 'result'>('upload')
const gradingTaskId = ref<number | null>(null)
const historyVisible = ref(false)

const currentStepIndex = computed(() => {
  switch (workspaceStep.value) {
    case 'upload': return 0
    case 'processing': return 1
    case 'result': return 3
    default: return 0
  }
})

const handleLogout = () => {
  localStorage.removeItem('token')
  emit('logout')
}

const handleUploaded = (taskId: number) => {
  gradingTaskId.value = taskId
  workspaceStep.value = 'processing'
}

const handleGradingComplete = () => {
  workspaceStep.value = 'result'
}

const resetWorkspace = () => {
  workspaceStep.value = 'upload'
  gradingTaskId.value = null
}

const handleViewHistoryResult = (taskId: number) => {
  gradingTaskId.value = taskId
  workspaceStep.value = 'result'
}
</script>

<style scoped>
.workspace-container {
  height: 100vh;
  display: flex;
  flex-direction: column;
}
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
  z-index: 10;
}
.logo {
  font-size: 20px;
  font-weight: bold;
  color: #409EFF;
}
.user-info {
  display: flex;
  align-items: center;
  gap: 16px;
}
.welcome {
  color: #606266;
}
.main-content {
  flex: 1;
  padding: 24px;
  background-color: #f5f7fa;
  display: flex;
  justify-content: center;
}
.workspace-card {
  width: 100%;
  max-width: 1000px;
  display: flex;
  flex-direction: column;
}
.steps {
  margin-bottom: 40px;
  margin-top: 20px;
}
.view-container {
  flex: 1;
  min-height: 400px;
}
</style>