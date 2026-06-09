<template>
  <div class="processing-container">
    <el-progress 
      type="dashboard" 
      :percentage="progress" 
      :status="status" 
      :color="customColors"
    >
      <template #default="{ percentage }">
        <span class="percentage-value">{{ percentage }}%</span>
        <span class="percentage-label">百度批改</span>
      </template>
    </el-progress>
    <p class="status-text">{{ statusText }}</p>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import api from '../utils/api'
import { ElMessage } from 'element-plus'

const props = defineProps<{
  taskId: number | null
}>()

const emit = defineEmits<{
  (e: 'complete'): void
}>()

const progress = ref(0)
const status = ref<'' | 'success' | 'exception'>('')
const statusText = ref('初始化中...')
let timer: any = null

const customColors = [
  { color: '#f56c6c', percentage: 20 },
  { color: '#e6a23c', percentage: 40 },
  { color: '#5cb87a', percentage: 60 },
  { color: '#1989fa', percentage: 80 },
  { color: '#6f7ad3', percentage: 100 },
]

const pollStatus = async () => {
  if (!props.taskId) return
  
  try {
    const res: any = await api.get(`/baidu-homework/status/${props.taskId}`)
    
    const taskStatus = res.task_status
    
    if (taskStatus === 0 || taskStatus === 1) {
      progress.value = Math.min(progress.value + 10, 95)
      statusText.value = '百度作业批改正在处理中...'
    } else if (taskStatus === 2) {
      progress.value = 100
      status.value = 'success'
      statusText.value = '处理完成！'
      clearInterval(timer)
      
      setTimeout(() => {
        emit('complete')
      }, 1000)
    } else if (taskStatus === 3) {
      status.value = 'exception'
      statusText.value = res.error_msg || '处理失败'
      clearInterval(timer)
      ElMessage.error(res.error_msg || '任务处理失败')
    }
  } catch (error: any) {
    if (error.response && error.response.status === 401) {
      clearInterval(timer)
      return
    }
    console.error('Polling error', error)
    progress.value = Math.min(progress.value + 5, 95)
  }
}

const simulateProgress = () => {
  timer = setInterval(() => {
    pollStatus()
  }, 3000)
}

onMounted(() => {
  progress.value = 0
  status.value = ''
  simulateProgress()
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.processing-container {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 100%;
  padding: 40px;
}
.percentage-value {
  display: block;
  font-size: 28px;
  font-weight: bold;
}
.percentage-label {
  display: block;
  font-size: 14px;
  color: #909399;
  margin-top: 10px;
}
.status-text {
  margin-top: 20px;
  color: #606266;
  font-size: 16px;
}
</style>