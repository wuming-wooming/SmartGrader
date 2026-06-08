<template>
    <div class="upload-container">
        <el-card class="upload-card">
            <el-upload v-if="!previewUrl" class="upload-area" drag :auto-upload="false" :show-file-list="false"
                :on-change="handleFileChange" accept="image/jpeg,image/png">
                <el-icon class="el-icon--upload"><upload-filled /></el-icon>
                <div class="el-upload__text">
                    拖拽图片到此处，或 <em>点击选择</em>
                </div>
                <template #tip>
                    <div class="el-upload__tip">支持 jpg/png 格式，且不超过 10MB</div>
                </template>
            </el-upload>

            <div v-else class="preview-area">
                <h3 class="preview-title">裁剪并预览图片</h3>
                <div class="image-wrapper">
                    <img ref="imageRef" :src="previewUrl" alt="Preview" class="crop-img" />
                </div>
                <div class="preview-actions">
                    <el-button @click="resetUpload">重新选择</el-button>
                    <el-button type="primary" :loading="uploading" @click="confirmUpload">
                        确认裁剪并上传
                    </el-button>
                </div>
            </div>
        </el-card>
    </div>
</template>

<script setup lang="ts">
import { ref, nextTick, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled } from '@element-plus/icons-vue'
import Cropper from 'cropperjs'
import 'cropperjs/dist/cropper.css'
import api from '../utils/api'

const emit = defineEmits<{
    (e: 'uploaded', taskId: number): void
}>()

const previewUrl = ref('')
const selectedFile = ref<File | null>(null)
const uploading = ref(false)
const imageRef = ref<HTMLImageElement | null>(null)
let cropper: Cropper | null = null

const handleFileChange = async (uploadFile: any) => {
    const file = uploadFile.raw
    const isImage = file.type === 'image/jpeg' || file.type === 'image/png'
    const isLt10M = file.size / 1024 / 1024 < 10

    if (!isImage) {
        ElMessage.error('只能上传 JPG/PNG 格式的图片!')
        return false
    }
    if (!isLt10M) {
        ElMessage.error('图片大小不能超过 10MB!')
        return false
    }

    selectedFile.value = file
    previewUrl.value = URL.createObjectURL(file)

    await nextTick()
    if (imageRef.value) {
        imageRef.value.onload = () => {
            cropper = new Cropper(imageRef.value!, {
                viewMode: 1 as any,
                dragMode: 'crop' as any,
                autoCropArea: 0.9,
                restore: false,
                guides: true,
                center: true,
                highlight: false,
                cropBoxMovable: true,
                cropBoxResizable: true,
                toggleDragModeOnDblclick: false,
            } as any)
        }
    }
}

const resetUpload = () => {
    if (cropper) {
        cropper.destroy()
        cropper = null
    }
    selectedFile.value = null
    previewUrl.value = ''
}

const confirmUpload = async () => {
    if (!cropper || !selectedFile.value) return
    uploading.value = true

    const canvas = (cropper as any).getCroppedCanvas({
        maxWidth: 4096,
        maxHeight: 4096
    })

    canvas.toBlob(async (blob: Blob | null) => {
        if (!blob) {
            ElMessage.error('裁剪图片失败')
            uploading.value = false
            return
        }

        const croppedFile = new File([blob], selectedFile.value!.name, { type: selectedFile.value!.type })
        const formData = new FormData()
        formData.append('file', croppedFile)

        try {
            const res: any = await api.post('/baidu-homework/submit', formData, {
                headers: { 'Content-Type': 'multipart/form-data' }
            })
            ElMessage.success('上传成功，开始百度批改...')
            emit('uploaded', res.assignment_task_id)
        } catch (error) {
            ElMessage.error('上传失败，请重试')
            console.error(error)
        } finally {
            uploading.value = false
        }
    }, selectedFile.value.type)
}

onBeforeUnmount(() => {
    if (cropper) {
        cropper.destroy()
    }
})
</script>

<style scoped>
.upload-container {
    display: flex;
    justify-content: center;
    padding: 20px;
}

.upload-card {
    width: 100%;
    max-width: 900px;
    text-align: center;
}

.upload-area {
    width: 100%;
}

.preview-area {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
}

.preview-title {
    margin-top: 0;
    color: #303133;
}

.image-wrapper {
    width: 100%;
    height: 60vh;
    min-height: 400px;
    margin: 20px 0;
    border: 1px solid #dcdfe6;
    border-radius: 4px;
    background-color: #f0f2f5;
    overflow: hidden;
}

.crop-img {
    display: block;
    max-width: 100%;
}

.preview-actions {
    display: flex;
    gap: 20px;
    margin-top: 10px;
}
</style>
