<template>
  <div class="presentation-container" @click.self="handleContainerClick">
    <!-- 背景装饰 -->
    <div class="bg-decor" />

    <!-- 顶部栏 -->
    <div class="top-bar">
      <el-button link type="info" @click="exitPresentation" class="exit-btn">
        <el-icon><Close /></el-icon>
        退出演示
      </el-button>
      <span class="slide-counter">{{ currentSlideIndex + 1 }} / {{ slides.length }}</span>
    </div>

    <!-- 幻灯片区域 -->
    <div class="slide-stage">
      <Transition :name="transitionName" mode="out-in">
        <div
          class="slide-panel"
          :key="currentSlideIndex"
          :class="`slide-layout--${currentSlide.layout}`"
        >
          <!-- 封面布局 -->
          <template v-if="currentSlide.layout === 'cover'">
            <div class="cover-content">
              <SlideContent :contents="currentSlide.contents" />
            </div>
          </template>

          <!-- 结尾布局 -->
          <template v-else-if="currentSlide.layout === 'end'">
            <div class="end-content">
              <SlideContent :contents="currentSlide.contents" />
            </div>
          </template>

          <!-- 双栏布局 -->
          <template v-else-if="currentSlide.layout === 'two-column'">
            <div class="slide-header">
              <h1 class="slide-title">{{ currentSlide.title }}</h1>
              <p v-if="currentSlide.subtitle" class="slide-subtitle">{{ currentSlide.subtitle }}</p>
            </div>
            <div class="two-column-body">
              <SlideContent :contents="leftColumn" />
              <SlideContent :contents="rightColumn" />
            </div>
          </template>

          <!-- 内容布局（默认） -->
          <template v-else>
            <div class="slide-header">
              <h1 class="slide-title">{{ currentSlide.title }}</h1>
              <p v-if="currentSlide.subtitle" class="slide-subtitle">{{ currentSlide.subtitle }}</p>
            </div>
            <div class="slide-body">
              <SlideContent :contents="currentSlide.contents" />
            </div>
          </template>

          <!-- 图片区域（如有） -->
          <div v-if="currentSlide.images?.length" class="slide-images">
            <FloatingImage
              v-for="(img, i) in currentSlide.images"
              :key="i"
              v-bind="img"
            />
          </div>
        </div>
      </Transition>
    </div>

    <!-- 底部导航栏 -->
    <div class="bottom-bar">
      <div class="nav-left">
        <el-button
          :disabled="currentSlideIndex === 0"
          @click="prevSlide"
          circle
          size="large"
          class="nav-btn"
        >
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
      </div>

      <div class="nav-dots">
        <span
          v-for="(slide, idx) in slides"
          :key="slide.id"
          class="nav-dot"
          :class="{ active: idx === currentSlideIndex }"
          @click="goToSlide(idx)"
        />
      </div>

      <div class="nav-right">
        <el-button
          :disabled="currentSlideIndex === slides.length - 1"
          @click="nextSlide"
          circle
          size="large"
          class="nav-btn"
        >
          <el-icon><ArrowRight /></el-icon>
        </el-button>
      </div>
    </div>

    <!-- 演讲者备注（可选，按 T 切换） -->
    <div v-if="showNotes && currentSlide.speakerNotes" class="speaker-notes">
      📝 {{ currentSlide.speakerNotes }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { presentationSlides } from '../../data/presentation'
import type { Slide } from '../../data/presentation'
import SlideContent from './SlideContent.vue'
import FloatingImage from './FloatingImage.vue'

const emit = defineEmits<{
  (e: 'exit'): void
}>()

const slides = presentationSlides as Slide[]
const currentSlideIndex = ref(0)
const direction = ref<'forward' | 'backward'>('forward')
const showNotes = ref(false)

const currentSlide = computed(() => slides[currentSlideIndex.value])

const transitionName = computed(() =>
  direction.value === 'forward' ? 'slide-forward' : 'slide-backward'
)

// 双栏布局：将 contents 平分为左右两栏
const leftColumn = computed(() => {
  if (currentSlide.value.layout !== 'two-column') return []
  const mid = Math.ceil(currentSlide.value.contents.length / 2)
  return currentSlide.value.contents.slice(0, mid)
})

const rightColumn = computed(() => {
  if (currentSlide.value.layout !== 'two-column') return []
  const mid = Math.ceil(currentSlide.value.contents.length / 2)
  return currentSlide.value.contents.slice(mid)
})

const nextSlide = () => {
  if (currentSlideIndex.value < slides.length - 1) {
    direction.value = 'forward'
    currentSlideIndex.value++
  }
}

const prevSlide = () => {
  if (currentSlideIndex.value > 0) {
    direction.value = 'backward'
    currentSlideIndex.value--
  }
}

const goToSlide = (idx: number) => {
  direction.value = idx > currentSlideIndex.value ? 'forward' : 'backward'
  currentSlideIndex.value = idx
}

const exitPresentation = () => {
  emit('exit')
}

const handleContainerClick = () => {
  // 点击幻灯片空白区域的默认行为：前进
  // 此处留空，避免误触
}

const handleKeydown = (e: KeyboardEvent) => {
  switch (e.key) {
    case 'ArrowRight':
    case 'ArrowDown':
    case ' ':
      e.preventDefault()
      nextSlide()
      break
    case 'ArrowLeft':
    case 'ArrowUp':
      e.preventDefault()
      prevSlide()
      break
    case 'Escape':
      exitPresentation()
      break
    case 'Home':
      e.preventDefault()
      goToSlide(0)
      break
    case 'End':
      e.preventDefault()
      goToSlide(slides.length - 1)
      break
    case 't':
    case 'T':
      showNotes.value = !showNotes.value
      break
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
  document.body.style.overflow = 'hidden'
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  document.body.style.overflow = ''
})
</script>

<style scoped>
/* ===== 容器 ===== */
.presentation-container {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  flex-direction: column;
  background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 40%, #16213e 100%);
  color: #e0e0e0;
  overflow: hidden;
  user-select: none;
}

.bg-decor {
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    radial-gradient(ellipse at 20% 50%, rgba(64, 158, 255, 0.08) 0%, transparent 50%),
    radial-gradient(ellipse at 80% 50%, rgba(103, 194, 58, 0.06) 0%, transparent 50%);
}

/* ===== 顶部栏 ===== */
.top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 28px;
  position: relative;
  z-index: 10;
}

.exit-btn {
  color: #909399;
  font-size: 14px;
  transition: color 0.2s;
}
.exit-btn:hover {
  color: #f56c6c;
}

.slide-counter {
  font-size: 14px;
  color: #909399;
  font-variant-numeric: tabular-nums;
}

/* ===== 幻灯片舞台 ===== */
.slide-stage {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 80px;
  position: relative;
  z-index: 5;
  overflow: hidden;
}

.slide-panel {
  width: 100%;
  max-width: 960px;
  max-height: 75vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.slide-panel::-webkit-scrollbar {
  width: 4px;
}
.slide-panel::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 2px;
}

/* ===== 幻灯片头部 ===== */
.slide-header {
  text-align: center;
}

.slide-title {
  font-size: 32px;
  font-weight: 700;
  color: #ffffff;
  margin: 0;
  line-height: 1.4;
}

.slide-subtitle {
  font-size: 18px;
  color: #a0a8c0;
  margin: 8px 0 0 0;
}

/* ===== 幻灯片主体 ===== */
.slide-body {
  flex: 1;
}

/* ===== 封面 ===== */
.cover-content {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.cover-content :deep(.sb-title) {
  font-size: 56px;
  background: linear-gradient(135deg, #409eff, #67c23a);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.cover-content :deep(.sb-subtitle) {
  font-size: 24px;
  color: #a0a8c0;
}

.cover-content :deep(.sb-text) {
  color: #909399;
}

/* ===== 结尾 ===== */
.end-content {
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}

.end-content :deep(.sb-title) {
  font-size: 52px;
  color: #ffffff;
}

.end-content :deep(.sb-subtitle) {
  font-size: 22px;
  color: #a0a8c0;
}

.end-content :deep(.sb-text) {
  font-size: 18px;
  color: #909399;
}

/* ===== 双栏 ===== */
.two-column-body {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 40px;
}

/* ===== 内容暗色覆盖 ===== */
.slide-panel :deep(.sb-title) {
  color: #ffffff;
}
.slide-panel :deep(.sb-subtitle) {
  color: #a0a8c0;
}
.slide-panel :deep(.sb-text) {
  color: #c0c4cc;
}
.slide-panel :deep(.sb-bullet-parent) {
  color: #e0e0e0;
}
.slide-panel :deep(.sb-bullet-children > li) {
  color: #c0c4cc;
}
.slide-panel :deep(.sb-bullet-grandchildren > li) {
  color: #909399;
}
.slide-panel :deep(.sb-highlight) {
  background: rgba(230, 162, 60, 0.12);
  border: 1px solid rgba(230, 162, 60, 0.3);
}
.slide-panel :deep(.sb-highlight .el-alert__title) {
  color: #e6a23c;
}

/* ===== 图片区域 ===== */
.slide-images {
  margin-top: 8px;
}

/* ===== 底部栏 ===== */
.bottom-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 28px 24px;
  position: relative;
  z-index: 10;
}

.nav-dots {
  display: flex;
  gap: 8px;
  align-items: center;
}

.nav-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.2);
  cursor: pointer;
  transition: all 0.3s ease;
}

.nav-dot:hover {
  background: rgba(255, 255, 255, 0.4);
  transform: scale(1.2);
}

.nav-dot.active {
  background: #409eff;
  box-shadow: 0 0 6px rgba(64, 158, 255, 0.5);
  width: 28px;
  border-radius: 5px;
}

.nav-btn {
  --el-button-bg-color: rgba(255, 255, 255, 0.08);
  --el-button-border-color: rgba(255, 255, 255, 0.12);
  --el-button-text-color: #c0c4cc;
  --el-button-hover-bg-color: rgba(255, 255, 255, 0.16);
  --el-button-hover-border-color: rgba(255, 255, 255, 0.2);
  --el-button-hover-text-color: #ffffff;
  font-size: 18px;
}

.nav-left,
.nav-right {
  width: 60px;
  display: flex;
  justify-content: center;
}

/* ===== 演讲者备注 ===== */
.speaker-notes {
  position: fixed;
  bottom: 80px;
  left: 50%;
  transform: translateX(-50%);
  background: rgba(0, 0, 0, 0.85);
  color: #e6a23c;
  padding: 10px 24px;
  border-radius: 8px;
  font-size: 14px;
  max-width: 700px;
  text-align: center;
  z-index: 20;
  animation: fadeIn 0.3s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateX(-50%) translateY(8px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}

/* ===== 幻灯片过渡动画 ===== */
.slide-forward-enter-active,
.slide-forward-leave-active,
.slide-backward-enter-active,
.slide-backward-leave-active {
  transition: all 0.45s cubic-bezier(0.4, 0, 0.2, 1);
}

.slide-forward-enter-from {
  opacity: 0;
  transform: translateX(60px) scale(0.97);
}

.slide-forward-leave-to {
  opacity: 0;
  transform: translateX(-60px) scale(0.97);
}

.slide-backward-enter-from {
  opacity: 0;
  transform: translateX(-60px) scale(0.97);
}

.slide-backward-leave-to {
  opacity: 0;
  transform: translateX(60px) scale(0.97);
}
</style>
