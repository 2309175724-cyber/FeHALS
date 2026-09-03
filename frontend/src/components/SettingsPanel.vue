<script setup>
import { onMounted, ref } from 'vue'
import { useHeliosAPI } from '../composables/useHeliosAPI'

const api = useHeliosAPI()
const cacheData = ref(null)
const envData = ref(null)
const loading = ref(false)
const envLoading = ref(false)

async function loadCache() {
  loading.value = true
  try {
    const res = await api.listCache()
    cacheData.value = res.cache
  } catch (e) {
    console.error(e)
  }
  loading.value = false
}

async function clearCache(type) {
  try {
    await api.clearCache(type)
    await loadCache()
  } catch (e) {
    console.error(e)
  }
}

async function loadEnvDiag() {
  envLoading.value = true
  try {
    envData.value = await api.diagnoseEnv()
  } catch (e) {
    console.error(e)
  }
  envLoading.value = false
}

function fmtSize(bytes) {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1)
  return (bytes / Math.pow(1024, i)).toFixed(1) + ' ' + units[i]
}

const statusText = { ok: '正常', warning: '警告', error: '错误' }
const statusIcon = { ok: '✓', warning: '!', error: '✗' }

onMounted(() => {
  loadEnvDiag()
  loadCache()
})
</script>

<template>
  <!-- 环境诊断 -->
  <section class="panel settings-panel">
    <div class="panel-head">
      <h3 class="panel-title">环境诊断</h3>
      <button class="btn btn-sm" :disabled="envLoading" @click="loadEnvDiag">
        {{ envLoading ? '检测中...' : '重新检测' }}
      </button>
    </div>

    <div v-if="envLoading" class="settings-loading">正在检测 HELIOS++ 运行环境...</div>
    <div v-else-if="!envData" class="settings-loading">无法加载环境诊断信息</div>
    <template v-else>
      <!-- 整体状态 -->
      <div class="env-overall" :class="'env-overall-' + envData.overall">
        <span class="env-status-icon">{{ statusIcon[envData.overall] }}</span>
        <span class="env-status-text">{{ statusText[envData.overall] }}</span>
        <span class="env-summary">{{ envData.summary }}</span>
      </div>

      <!-- 可执行文件 -->
      <div class="env-section">
        <div class="env-section-title">
          可执行文件
          <span class="env-badge" :class="'env-badge-' + envData.helios_executable.status">
            {{ statusIcon[envData.helios_executable.status] }}
            {{ statusText[envData.helios_executable.status] }}
          </span>
        </div>
        <div class="env-detail-row">
          <span class="env-detail-label">配置路径</span>
          <span class="env-detail-value">{{ envData.helios_executable.path }}</span>
        </div>
        <div class="env-detail-row" v-if="envData.helios_executable.resolved_path">
          <span class="env-detail-label">实际路径</span>
          <span class="env-detail-value">{{ envData.helios_executable.resolved_path }}</span>
        </div>
        <div class="env-detail-row" v-if="envData.helios_executable.version">
          <span class="env-detail-label">版本</span>
          <span class="env-detail-value">{{ envData.helios_executable.version }}</span>
        </div>
        <div class="env-detail-row" v-if="envData.helios_executable.status !== 'ok'">
          <span class="env-detail-hint">{{ envData.helios_executable.message }}</span>
        </div>
      </div>

      <!-- 资源目录 -->
      <div class="env-section">
        <div class="env-section-title">
          资源目录完整性
          <span
            class="env-badge"
            :class="'env-badge-' + (envData.resource_dirs.some(d => d.status === 'error') ? 'error' : (envData.resource_dirs.some(d => d.status === 'warning') ? 'warning' : 'ok'))"
          >
            {{ statusText[envData.resource_dirs.some(d => d.status === 'error') ? 'error' : (envData.resource_dirs.some(d => d.status === 'warning') ? 'warning' : 'ok')] }}
          </span>
        </div>
        <div v-for="dir in envData.resource_dirs" :key="dir.name" class="env-sub-group">
          <div class="env-sub-title" :class="{ 'env-text-error': dir.status === 'error' }">
            {{ dir.name }}
            <span class="env-sub-path">{{ dir.path }}</span>
          </div>
          <div v-if="dir.message" class="env-sub-message" :class="'env-text-' + dir.status">{{ dir.message }}</div>
          <!-- 仓库子目录 -->
          <div v-if="dir.subdirs" class="env-check-list">
            <div
              v-for="sub in dir.subdirs"
              :key="sub.path"
              class="env-check-item"
            >
              <span class="env-check-icon" :class="'env-icon-' + sub.status">{{ statusIcon[sub.status] }}</span>
              <span class="env-check-path">{{ sub.path }}</span>
              <span class="env-check-desc">{{ sub.description }}</span>
            </div>
          </div>
          <!-- pyhelios 文件 -->
          <div v-if="dir.files" class="env-check-list">
            <div
              v-for="f in dir.files"
              :key="f.path"
              class="env-check-item"
            >
              <span class="env-check-icon" :class="'env-icon-' + f.status">{{ statusIcon[f.status] }}</span>
              <span class="env-check-path">{{ f.path }}</span>
              <span class="env-check-desc">{{ f.description }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Assets 搜索路径 -->
      <div class="env-section" v-if="envData.assets && envData.assets.length">
        <div class="env-section-title">Assets 搜索路径</div>
        <div v-for="a in envData.assets" :key="a.index" class="env-check-item">
          <span class="env-check-icon" :class="'env-icon-' + a.status">{{ statusIcon[a.status] }}</span>
          <span class="env-check-path">{{ a.path }}</span>
        </div>
      </div>

      <!-- 静态工作目录 -->
      <div class="env-section">
        <div class="env-section-title">
          静态工作目录
          <span class="env-badge" :class="'env-badge-' + (envData.static_dirs.some(d => d.status === 'error') ? 'error' : 'ok')">
            {{ statusText[envData.static_dirs.some(d => d.status === 'error') ? 'error' : 'ok'] }}
          </span>
        </div>
        <div class="env-check-list">
          <div
            v-for="d in envData.static_dirs"
            :key="d.name"
            class="env-check-item"
          >
            <span class="env-check-icon" :class="'env-icon-' + d.status">{{ statusIcon[d.status] }}</span>
            <span class="env-check-path">{{ d.label }}</span>
            <span class="env-check-desc">{{ d.message }}</span>
          </div>
        </div>
      </div>
    </template>
  </section>

  <!-- 缓存管理 -->
  <section class="panel settings-panel">
    <h3 class="panel-title">缓存管理</h3>
    <div v-if="loading" class="settings-loading">加载中...</div>
    <div v-else-if="!cacheData" class="settings-loading">无法加载缓存信息</div>
    <div v-else class="cache-list">
      <div v-for="(item, key) in cacheData" :key="key" class="cache-item">
        <span class="cache-label">{{ item.label }}</span>
        <span class="cache-info">{{ item.count }} 个文件 / {{ fmtSize(item.size) }}</span>
        <button class="btn btn-sm" @click="clearCache(key)">清理</button>
      </div>
    </div>
  </section>
</template>