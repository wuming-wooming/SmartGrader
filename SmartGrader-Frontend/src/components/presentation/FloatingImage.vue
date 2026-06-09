<template>
  <div
    class="floating-image"
    :class="[
      `float-pos--${position}`,
      `float-size--${size}`,
      animate === 'float' ? 'float-animate' : '',
      animate === 'fade-in' ? 'fade-in-animate' : '',
    ]"
  >
    <el-image
      :src="src"
      :alt="alt || ''"
      fit="contain"
      :preview-src-list="[src]"
      lazy
    />
  </div>
</template>

<script setup lang="ts">
withDefaults(
  defineProps<{
    src: string
    alt?: string
    position?: 'left' | 'center' | 'right'
    size?: 'small' | 'medium' | 'large'
    animate?: 'float' | 'fade-in' | 'none'
  }>(),
  {
    position: 'center',
    size: 'medium',
    animate: 'none',
  }
)
</script>

<style scoped>
.floating-image {
  display: flex;
  justify-content: center;
  align-items: center;
}

.float-pos--left {
  justify-content: flex-start;
}
.float-pos--center {
  justify-content: center;
}
.float-pos--right {
  justify-content: flex-end;
}

.float-size--small :deep(.el-image) {
  max-width: 200px;
  max-height: 200px;
}
.float-size--medium :deep(.el-image) {
  max-width: 400px;
  max-height: 400px;
}
.float-size--large :deep(.el-image) {
  max-width: 600px;
  max-height: 500px;
}

.float-animate {
  animation: floatAnim 3s ease-in-out infinite;
}

.fade-in-animate {
  animation: fadeInAnim 0.8s ease-out forwards;
}

@keyframes floatAnim {
  0%, 100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-12px);
  }
}

@keyframes fadeInAnim {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
</style>
