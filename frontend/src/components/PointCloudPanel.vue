<script setup>
import { computed } from 'vue'
import { useSceneStore } from '../stores/scene'
import { useSimulationStore } from '../stores/simulation'

const sceneStore = useSceneStore()
const simStore = useSimulationStore()

// 特征统计（旧响应可能无 stats 字段，空点云时仅有 count）
const st = computed(() => simStore.result?.stats || {})

const fmt = (v, d = 2) => (v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(d))
const fmtInt = (v) => (v == null ? '—' : Number(v).toLocaleString('en-US'))
const fmtRange = (a, b) => `${fmt(a)} ~ ${fmt(b)}`

function downloadPointCloud() {
  if (!simStore.taskId) return
  const url = `/api/results/${simStore.taskId}/download`
  const a = document.createElement('a')
  a.href = url
  a.download = `fehals_${simStore.taskId}.xyz`
  a.click()
}
</script>

<template>
  <section class="panel pointcloud-panel">
    <h3 class="panel-title">点云</h3>

    <div v-if="!simStore.result" class="pc-empty">暂无点云数据，请先执行仿真</div>

    <template v-if="simStore.result">
      <div class="section-divider">特征统计</div>
      <div class="stat-list">
        <div class="stat-item">
          <span class="stat-label">点数</span>
          <span class="stat-value">{{ fmtInt(simStore.result.point_count) }}</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">平均高度</span>
          <span class="stat-value">{{ fmt(st.mean_z) }} m</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">高度标准差</span>
          <span class="stat-value">{{ fmt(st.std_z) }} m</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">X 范围</span>
          <span class="stat-value">{{ fmtRange(simStore.result.bounds?.[0], simStore.result.bounds?.[3]) }} m</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Y 范围</span>
          <span class="stat-value">{{ fmtRange(simStore.result.bounds?.[1], simStore.result.bounds?.[4]) }} m</span>
        </div>
        <div class="stat-item">
          <span class="stat-label">Z 范围</span>
          <span class="stat-value">{{ fmtRange(simStore.result.bounds?.[2], simStore.result.bounds?.[5]) }} m</span>
        </div>
      </div>

      <div class="section-divider">渲染属性</div>

      <div class="field">
        <label>大小</label>
        <input
          v-model.number="sceneStore.pointOptions.size"
          type="range"
          min="0.01"
          max="1"
          step="0.01"
        />
      </div>

      <div class="field">
        <label>透明度</label>
        <input
          v-model.number="sceneStore.pointOptions.opacity"
          type="range"
          min="0.05"
          max="1"
          step="0.05"
        />
      </div>

      <div class="field">
        <label>着色</label>
        <select v-model="sceneStore.pointOptions.colorMode">
          <option value="height">按高度</option>
          <option value="intensity">按强度</option>
          <option value="fixed">固定颜色</option>
        </select>
      </div>

      <div class="field" v-if="sceneStore.pointOptions.colorMode === 'fixed'">
        <label>颜色</label>
        <input v-model="sceneStore.pointOptions.fixedColor" type="color" />
      </div>

      <button class="btn" style="width: 100%; margin-top: 8px" @click="downloadPointCloud">
        下载点云
      </button>
    </template>
  </section>
</template>
