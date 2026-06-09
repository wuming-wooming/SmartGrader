<template>
  <div class="slide-content">
    <template v-for="(block, idx) in contents" :key="idx">
      <!-- 标题 -->
      <h1 v-if="block.type === 'title'" class="sb-title">{{ block.text }}</h1>

      <!-- 副标题 -->
      <h3 v-else-if="block.type === 'subtitle'" class="sb-subtitle">{{ block.text }}</h3>

      <!-- 正文 -->
      <p v-else-if="block.type === 'text'" class="sb-text">{{ block.text }}</p>

      <!-- 要点列表 -->
      <div v-else-if="block.type === 'bullet'" class="sb-bullet-group">
        <p class="sb-bullet-parent">{{ block.text }}</p>
        <ul v-if="block.children?.length" class="sb-bullet-children">
          <li v-for="(child, ci) in block.children" :key="ci">
            <template v-if="child.type === 'bullet'">
              {{ child.text }}
              <ul v-if="child.children?.length" class="sb-bullet-grandchildren">
                <li v-for="(gc, gi) in child.children" :key="gi">{{ gc.text }}</li>
              </ul>
            </template>
          </li>
        </ul>
      </div>

      <!-- 高亮块 -->
      <el-alert
        v-else-if="block.type === 'highlight'"
        :title="block.text"
        type="warning"
        :closable="false"
        show-icon
        class="sb-highlight"
      />

      <!-- 代码块 -->
      <pre v-else-if="block.type === 'code'" class="sb-code"><code>{{ block.text }}</code></pre>
    </template>
  </div>
</template>

<script setup lang="ts">
import type { ContentBlock } from '../../data/presentation'

defineProps<{
  contents: ContentBlock[]
}>()
</script>

<style scoped>
.slide-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.sb-title {
  font-size: 42px;
  font-weight: 700;
  color: #303133;
  margin: 0 0 16px 0;
  text-align: center;
  line-height: 1.3;
}

.sb-subtitle {
  font-size: 22px;
  font-weight: 500;
  color: #606266;
  margin: 0 0 8px 0;
  text-align: center;
}

.sb-text {
  font-size: 17px;
  color: #404248;
  line-height: 1.8;
  margin: 4px 0;
  text-align: center;
}

.sb-bullet-group {
  margin: 4px 0;
}

.sb-bullet-parent {
  font-size: 18px;
  font-weight: 600;
  color: #303133;
  margin: 8px 0 4px 0;
}

.sb-bullet-children {
  margin: 2px 0 6px 12px;
  padding: 0;
  list-style: none;
}

.sb-bullet-children > li {
  font-size: 16px;
  color: #404248;
  line-height: 1.9;
  padding: 2px 0;
  position: relative;
  padding-left: 20px;
}

.sb-bullet-children > li::before {
  content: '▸';
  position: absolute;
  left: 0;
  color: #409eff;
  font-size: 12px;
  top: 7px;
}

.sb-bullet-grandchildren {
  margin: 2px 0 4px 16px;
  padding: 0;
  list-style: none;
}

.sb-bullet-grandchildren > li {
  font-size: 14px;
  color: #606266;
  line-height: 1.8;
  padding: 1px 0;
  padding-left: 18px;
  position: relative;
}

.sb-bullet-grandchildren > li::before {
  content: '·';
  position: absolute;
  left: 2px;
  color: #909399;
  font-weight: bold;
}

.sb-highlight {
  margin: 8px 0;
  font-size: 15px;
}

.sb-code {
  background: #1e1e2e;
  color: #cdd6f4;
  padding: 16px 24px;
  border-radius: 8px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 14px;
  line-height: 1.6;
  margin: 8px 0;
  overflow-x: auto;
}

.sb-code code {
  background: none;
  padding: 0;
}
</style>
