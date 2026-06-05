<template>
    <el-drawer v-model="visible" title="历史批改记录" size="400px" @close="handleClose">
        <div class="history-container" v-loading="loading">
            <el-empty v-if="tasks.length === 0 && !loading" description="暂无历史记录" />
            <div v-else class="task-list">
                <el-card v-for="task in tasks" :key="task.assignment_task_id" class="task-card" shadow="hover">
                    <div class="task-header">
                        <span class="task-id">任务 ID: {{ task.assignment_task_id }}</span>
                        <el-tag :type="getStatusType(task.task_status)" size="small">
                            {{ getStatusText(task.task_status) }}
                        </el-tag>
                    </div>
                    <div class="task-body">
                        <p>创建时间: {{ formatDate(task.created_at) }}</p>
                        <p>题目数量: {{ task.total_questions || 0 }} 题</p>
                    </div>
                    <div class="task-footer">
                        <el-button type="primary" link @click="viewResult(task)" :disabled="task.task_status !== 2">
                            查看报告
                        </el-button>
                    </div>
                </el-card>
            </div>
        </div>
    </el-drawer>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import api from '../utils/api'

const props = defineProps<{
    modelValue: boolean
}>()

const emit = defineEmits<{
    (e: 'update:modelValue', value: boolean): void
    (e: 'view-result', taskId: number): void
}>()

const visible = ref(false)
const loading = ref(false)
const tasks = ref<any[]>([])

watch(() => props.modelValue, (val) => {
    visible.value = val
    if (val) {
        fetchTasks()
    }
})

const handleClose = () => {
    emit('update:modelValue', false)
}

const fetchTasks = async () => {
    loading.value = true
    try {
        const res: any = await api.get('/grading/tasks?limit=50&offset=0')
        tasks.value = res.tasks || []
    } catch (error) {
        console.error(error)
        ElMessage.error('获取历史记录失败')
    } finally {
        loading.value = false
    }
}

const getStatusType = (status: number) => {
    switch (status) {
        case 0: return 'info'
        case 1: return 'warning'
        case 2: return 'success'
        case 3: return 'danger'
        default: return 'info'
    }
}

const getStatusText = (status: number) => {
    switch (status) {
        case 0: return '等待处理'
        case 1: return '处理中'
        case 2: return '批改完成'
        case 3: return '处理失败'
        default: return '未知状态'
    }
}

const formatDate = (dateStr: string) => {
    if (!dateStr) return '未知'
    const date = new Date(dateStr)
    return date.toLocaleString()
}

const viewResult = (task: any) => {
    if (task.task_status === 2) {
        emit('view-result', task.assignment_task_id)
        visible.value = false
    }
}
</script>

<style scoped>
.history-container {
    padding: 0 10px;
    height: 100%;
    overflow-y: auto;
}

.task-list {
    display: flex;
    flex-direction: column;
    gap: 15px;
}

.task-card {
    margin-bottom: 10px;
}

.task-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 10px;
    font-weight: bold;
}

.task-body {
    font-size: 13px;
    color: #606266;
    line-height: 1.6;
}

.task-body p {
    margin: 5px 0;
}

.task-footer {
    margin-top: 10px;
    text-align: right;
    border-top: 1px solid #ebeef5;
    padding-top: 10px;
}
</style>
