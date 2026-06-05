<template>
  <div class="image-clean-container">
    <div v-if="!cleaningDone" class="processing-state">
      <el-progress 
        type="dashboard" 
        :percentage="progress" 
        :status="status" 
        :color="customColors"
      >
        <template #default="{ percentage }">
          <span class="percentage-value">{{ percentage }}%</span>
          <span class="percentage-label">图片清洗中</span>
        </template>
      </el-progress>
      <p class="status-text">{{ statusText }}</p>
    </div>

    <div v-else class="comparison-state">
      <el-row :gutter="20">
        <!-- 左侧：裁剪后的原图 -->
        <el-col :span="12">
          <el-card class="image-card" shadow="never">
            <template #header>
              <div class="card-header">
                <span>裁剪后原图</span>
              </div>
            </template>
            <div class="image-container">
              <el-image 
                :src="getImageUrl(rawImageUrl)" 
                fit="contain" 
                class="preview-image"
                :preview-src-list="[getImageUrl(rawImageUrl)]"
              >
                <template #error>
                  <div class="image-slot">
                    <el-icon><Picture /></el-icon>
                  </div>
                </template>
              </el-image>
            </div>
          </el-card>
        </el-col>

        <!-- 右侧：清洗后的图片 -->
        <el-col :span="12">
          <el-card class="image-card" shadow="never">
            <template #header>
              <div class="card-header">
                <span>清洗后图片</span>
              </div>
            </template>
            <div class="image-container">
              <el-image 
                :src="getImageUrl(processedImageUrl)" 
                fit="contain" 
                class="preview-image"
                :preview-src-list="[getImageUrl(processedImageUrl)]"
              >
                <template #error>
                  <div class="image-slot">
                    <el-icon><Picture /></el-icon>
                  </div>
                </template>
              </el-image>
            </div>
          </el-card>
        </el-col>
      </el-row>
      
      <div class="action-bar">
        <el-button type="primary" size="large" @click="handleSubmit">
          提交切题
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Picture } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import api from '../utils/api'

const props = defineProps<{
  taskId: number | null
  rawImageUrl: string
}>()

const emit = defineEmits<{
  (e: 'complete'): void
}>()

const cleaningDone = ref(false)
const progress = ref(0)
const status = ref<'' | 'success' | 'exception'>('')
const statusText = ref('初始化中...')
let timer: any = null

const rawImageUrl = ref('')
const processedImageUrl = ref('')

const customColors = [
  { color: '#f56c6c', percentage: 20 },
  { color: '#e6a23c', percentage: 40 },
  { color: '#5cb87a', percentage: 60 },
  { color: '#1989fa', percentage: 80 },
  { color: '#6f7ad3', percentage: 100 },
]

const getImageUrl = (path: string) => {
  if (!path) return ''
  const cleanPath = path.startsWith('/') ? path.slice(1) : path
  return `/api/${cleanPath}`
}

const pollStatus = async () => {
  if (!props.taskId) return
  
  try {
    const res: any = await api.get(`/grading/status/${props.taskId}`)
    const taskStatus = res.task_status
    
    if (taskStatus === 0 || taskStatus === 1) {
      progress.value = Math.min(progress.value + 15, 95)
      statusText.value = '正在进行图片清洗...'
    } else if (taskStatus === 2) {
      progress.value = 100
      status.value = 'success'
      statusText.value = '清洗完成！'
      clearInterval(timer)
      
      rawImageUrl.value = props.rawImageUrl
      try {
        const processedRes: any = await api.get(`/images/${props.taskId}/processed`)
        processedImageUrl.value = processedRes.processed_image_url
      } catch (error) {
        console.error('获取处理后图片失败', error)
      }
      
      setTimeout(() => {
        cleaningDone.value = true
      }, 500)
    } else if (taskStatus === 3) {
      status.value = 'exception'
      statusText.value = res.error_msg || '图片清洗失败'
      clearInterval(timer)
      ElMessage.error(res.error_msg || '图片清洗失败')
    }
  } catch (error: any) {
    if (error.response && error.response.status === 401) {
      clearInterval(timer)
      return
    }
    console.error('Polling error', error)
    progress.value = Math.min(progress.value + 10, 95)
  }
}

const simulateProgress = () => {
  timer = setInterval(() => {
    pollStatus()
  }, 2000)
}

const handleSubmit = () => {
  emit('complete')
}

onMounted(() => {
  if (props.taskId) {
    pollStatus()
    simulateProgress()
  }
})

onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<style scoped>
.image-clean-container {
  height: 100%;
}
.processing-state {
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

.comparison-state {
  padding: 20px 0;
}
.image-card {
  height: 60vh;
  min-height: 500px;
  display: flex;
  flex-direction: column;
}
:deep(.el-card__body) {
  flex: 1;
  display: flex;
  padding: 0;
  overflow: hidden;
}
.card-header {
  font-weight: bold;
  text-align: center;
}
.image-container {
  flex: 1;
  width: 100%;
  height: 100%;
  background-color: #f5f7fa;
  display: flex;
  justify-content: center;
  align-items: center;
  overflow: hidden;
}
.preview-image {
  width: 100%;
  height: 100%;
}
.image-slot {
  display: flex;
  justify-content: center;
  align-items: center;
  width: 100%;
  height: 100%;
  background: #f5f7fa;
  color: #909399;
  font-size: 30px;
}
.action-bar {
  margin-top: 30px;
  display: flex;
  justify-content: center;
}
</style>
