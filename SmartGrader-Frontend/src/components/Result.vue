<template>
  <div class="result-container" v-loading="loading">
    <template v-if="result">
      <div class="summary-section">
        <el-row :gutter="20">
          <el-col :span="8">
            <el-card shadow="hover" class="score-card">
              <div class="score-title">总得分</div>
              <div class="score-value">{{ result.report?.total_score || 0 }}</div>
            </el-card>
          </el-col>
          <el-col :span="16">
            <el-card shadow="hover" class="comment-card">
              <div class="comment-title">综合评价</div>
              <div class="comment-content">{{ result.report?.summary || '暂无评价' }}</div>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <el-divider>题目详情</el-divider>

      <div class="details-section">
        <el-collapse v-model="activeNames">
          <el-collapse-item 
            v-for="(item, index) in result.questions" 
            :key="index" 
            :name="index"
          >
            <template #title>
              <div class="item-header">
                <span class="item-title">第 {{ Number(index) + 1 }} 题</span>
                <el-tag :type="item.is_correct ? 'success' : 'danger'" size="small">
                  {{ item.is_correct ? '正确' : '错误' }}
                </el-tag>
                <span class="item-score">得分: {{ item.score || 0 }}</span>
              </div>
            </template>
            <div class="item-content">
              <div class="image-box" v-if="item.question_image">
                <el-image 
                  :src="getImageUrl(item.question_image)" 
                  :preview-src-list="[getImageUrl(item.question_image)]"
                  fit="contain"
                />
              </div>
              <div class="text-box">
                <p><strong>识别文本：</strong> {{ item.question_text }}</p>
                <p><strong>正确答案：</strong> {{ item.correct_answer }}</p>
                <p><strong>批注：</strong> {{ item.comment }}</p>
              </div>
            </div>
          </el-collapse-item>
        </el-collapse>
      </div>

      <div class="actions">
        <el-button type="primary" @click="$emit('reset')">批改下一份作业</el-button>
      </div>
    </template>
    <el-empty v-else description="暂无批改结果" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api, { baseURL } from '../utils/api'

const props = defineProps<{
  taskId: number | null
}>()

const emit = defineEmits<{
  (e: 'reset'): void
}>()

const loading = ref(true)
const result = ref<any>(null)
const activeNames = ref([0])

const getImageUrl = (url: string) => {
  if (!url) return ''
  if (url.startsWith('http')) return url
  const cleanUrl = url.startsWith('/') ? url.slice(1) : url
  return `${baseURL}/${cleanUrl}`
}

const fetchResult = async () => {
  if (!props.taskId) return
  loading.value = true
  try {
    const res: any = await api.get(`/grading/result/${props.taskId}`)
    const data = res.data || res
    console.info(data)
    
    result.value = {
      total_score: data.report?.total_score || 0,
      summary_comment: data.report?.summary || '暂无评价',
      details: (data.questions || []).map((q: any) => ({
        is_correct: q.is_correct,
        score: q.score,
        recognized_text: q.question_text,
        correct_answer: q.correct_answer,
        comment: q.comment
      }))
    }
    console.info(result.value)
  } catch (error) {
    ElMessage.error('获取结果失败')
    console.error(error)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchResult()
})

watch(() => props.taskId, () => {
  fetchResult()
})
</script>

<style scoped>
.result-container {
  padding: 20px 0;
}
.summary-section {
  margin-bottom: 30px;
}
.score-card {
  text-align: center;
  height: 100%;
}
.score-title {
  font-size: 16px;
  color: #909399;
  margin-bottom: 10px;
}
.score-value {
  font-size: 48px;
  font-weight: bold;
  color: #409EFF;
}
.comment-card {
  height: 100%;
}
.comment-title {
  font-size: 16px;
  color: #909399;
  margin-bottom: 10px;
}
.comment-content {
  font-size: 14px;
  line-height: 1.6;
  color: #303133;
}
.item-header {
  display: flex;
  align-items: center;
  gap: 15px;
  width: 100%;
}
.item-title {
  font-weight: bold;
}
.item-score {
  margin-left: auto;
  margin-right: 20px;
  color: #606266;
}
.item-content {
  display: flex;
  gap: 20px;
  background-color: #f8f9fa;
  padding: 15px;
  border-radius: 4px;
}
.image-box {
  width: 200px;
  flex-shrink: 0;
}
.text-box {
  flex: 1;
}
.text-box p {
  margin-top: 0;
  margin-bottom: 10px;
  line-height: 1.5;
}
.actions {
  margin-top: 30px;
  text-align: center;
}
</style>
