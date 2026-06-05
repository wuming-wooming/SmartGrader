<template>
  <div class="ocr-confirm-container">
    <!-- 等待状态 -->
    <div v-if="!ocrDone" class="processing-state">
      <el-progress 
        type="dashboard" 
        :percentage="progress" 
        :status="status" 
        :color="customColors"
      >
        <template #default="{ percentage }">
          <span class="percentage-value">{{ percentage }}%</span>
          <span class="percentage-label">ocr 与 切题中</span>
        </template>
      </el-progress>
      <p class="status-text">{{ statusText }}</p>
    </div>

    <!-- 完成后的确认页面 -->
    <div v-else class="results-container">
      <!-- 上方：图片预览 -->
      <el-card class="image-card">
        <template #header>
          <div class="card-header">
            <span>图片预览</span>
          </div>
        </template>
        <div class="preview-wrapper">
          <el-row :gutter="20">
            <el-col :span="12">
              <div class="preview-section">
                <h4>裁剪后原图</h4>
                <el-image :src="getImageUrl(rawImageUrl)" fit="contain" :preview-src-list="[getImageUrl(rawImageUrl)]" class="preview-img" />
              </div>
            </el-col>
            <el-col :span="12">
              <div class="preview-section">
                <h4>清洗后图片</h4>
                <el-image :src="getImageUrl(processedImageUrl)" fit="contain" :preview-src-list="[getImageUrl(processedImageUrl)]" class="preview-img" />
              </div>
            </el-col>
          </el-row>
        </div>
      </el-card>

      <!-- 下方：识别结果确认 -->
      <el-card class="questions-card">
        <template #header>
          <div class="card-header">
            <span>切题与识别结果确认</span>
            <el-button type="primary" @click="submitGrading" :loading="submitting">提交批改</el-button>
          </div>
        </template>
        
        <div v-if="questions.length === 0 && ocrDone" class="empty-state">
          <el-empty description="未能识别出题目" />
        </div>
        
        <div v-else class="q-list">
          <div v-for="(q, index) in questions" :key="index" class="q-item">
            <div class="q-header">
              <span class="q-title">第 {{ index + 1 }} 题</span>
              <div class="q-meta">
                <span class="score-label">满分：</span>
                <el-input-number v-model="q.full_score" :min="1" :max="100" size="small" controls-position="right" style="width: 100px" />
              </div>
            </div>
            <div class="q-body">
              <div class="q-image" v-if="q.question_image">
                <el-image :src="getImageUrl(q.question_image)" fit="contain" :preview-src-list="[getImageUrl(q.question_image)]" />
              </div>
              <div class="q-text">
                <el-input type="textarea" v-model="q.question_text" :rows="4" placeholder="识别出的题目文本" />
              </div>
            </div>
          </div>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import api, { baseURL } from '../utils/api'

const props = defineProps<{
  taskId: number | null
  rawImageUrl: string
}>()

const emit = defineEmits<{
  (e: 'submit', assignmentTaskId: number): void
}>()

const ocrDone = ref(false)
const progress = ref(0)
const status = ref<'' | 'success' | 'exception'>('')
const statusText = ref('正在获取切题结果...')
let pollTimer: any = null

const customColors = [
  { color: '#f56c6c', percentage: 20 },
  { color: '#e6a23c', percentage: 40 },
  { color: '#5cb87a', percentage: 60 },
  { color: '#1989fa', percentage: 80 },
  { color: '#6f7ad3', percentage: 100 },
]

const submitting = ref(false)
const questions = ref<any[]>([])

const getImageUrl = (url: string) => {
  if (!url) return ''
  if (url.startsWith('http')) return url
  const cleanUrl = url.startsWith('/') ? url.slice(1) : url
  return `${baseURL}/${cleanUrl}`
}

const processedImageUrl = computed(() => {
  if (!props.rawImageUrl) return ''
  const parts = props.rawImageUrl.split('/')
  const filename = parts.pop() || ''
  const nameWithoutExt = filename.includes('.') ? filename.substring(0, filename.lastIndexOf('.')) : filename
  return props.rawImageUrl.replace('raw_images', 'processed_images').replace(filename, `cleaned_${nameWithoutExt}.png`)
})

const fetchOcrResult = async () => {
  if (!props.taskId) return
  try {
    const res: any = await api.get(`/images/${props.taskId}/cuts`)
    questions.value = (res.cuts || []).map((q: any) => ({
      ...q,
      question_image: q.image_url,
      full_score: q.full_score || 10,
      subject: q.subject || 'math'
    }))
    
    progress.value = 100
    status.value = 'success'
    statusText.value = '识别与切题完成！'
    setTimeout(() => {
      ocrDone.value = true
    }, 500)
  } catch (error: any) {
    if (error.response && error.response.status === 401) {
      return
    }
    if (error.response && error.response.status === 404) {
      // 检查任务状态，看是否因为报错而导致没有数据
      try {
        const statusRes: any = await api.get(`/grading/status/${props.taskId}`)
        if (statusRes.task_status === 3) {
          status.value = 'exception'
          statusText.value = statusRes.error_msg || 'OCR 识别与切题失败'
          ElMessage.error(statusRes.error_msg || 'OCR 识别与切题失败')
          return
        }
      } catch (statusError) {
        // 忽略状态检查的错误，继续走重试逻辑
      }
      
      // 如果 404 且任务没失败，说明 OCR 还在后台处理中，继续轮询
      progress.value = Math.min(progress.value + 15, 95)
      pollTimer = setTimeout(() => {
        fetchOcrResult()
      }, 2000)
    } else {
      status.value = 'exception'
      statusText.value = '获取识别结果失败'
      ElMessage.error('获取识别结果失败')
      console.error(error)
    }
  }
}

const submitGrading = async () => {
  submitting.value = true
  try {
    const payload = {
      task_type: 2,
      total_pages: 1,
      original_file: props.rawImageUrl,
      processed_file: processedImageUrl.value,
      questions: questions.value.map(q => ({
        page_num: q.page_num || 1,
        question_index: q.question_index,
        subject: q.subject,
        question_text: q.question_text,
        question_image: q.question_image,
        full_score: q.full_score
      }))
    }
    
    const res: any = await api.post('/grading/submit', payload)
    ElMessage.success('已提交批改任务')
    emit('submit', res.assignment_task_id)
  } catch (error) {
    ElMessage.error('提交批改失败')
    console.error(error)
  } finally {
    submitting.value = false
  }
}

onMounted(() => {
  fetchOcrResult()
})

onUnmounted(() => {
  if (pollTimer) clearTimeout(pollTimer)
})
</script>

<style scoped>
.processing-state {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  height: 60vh;
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

.ocr-confirm-container {
  padding: 10px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: bold;
}
.results-container {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.image-card {
  height: 600px;
  display: flex;
  flex-direction: column;
}
.questions-card {
  height: 600px;
  display: flex;
  flex-direction: column;
}
:deep(.el-card__body) {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}
.preview-wrapper {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}
.preview-section {
  text-align: center;
}
.preview-section h4 {
  margin-top: 0;
  margin-bottom: 10px;
  color: #303133;
}
.preview-img {
  width: 100%;
  max-height: 500px;
  background-color: #f5f7fa;
  border-radius: 4px;
}
.q-list {
  flex: 1;
  overflow-y: auto;
  padding-right: 10px;
}
.q-item {
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 15px;
  margin-bottom: 15px;
}
.q-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 10px;
  align-items: center;
}
.q-title {
  font-weight: bold;
  color: #409EFF;
}
.q-meta {
  display: flex;
  align-items: center;
}
.score-label {
  font-size: 14px;
  color: #606266;
  margin-right: 5px;
}
.q-body {
  display: flex;
  flex-direction: column;
  gap: 15px;
}
.q-image {
  max-height: 250px;
  background-color: #fafafa;
  display: flex;
  justify-content: center;
  align-items: center;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 5px;
}
.q-image .el-image {
  max-height: 240px;
  max-width: 100%;
}
.q-text {
  display: flex;
  flex-direction: column;
}
.q-text .el-textarea {
  width: 100%;
}
.empty-state {
  flex: 1;
  display: flex;
  justify-content: center;
  align-items: center;
}
</style>
