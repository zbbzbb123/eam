<script setup>
defineProps({
  visible: Boolean,
  analysis: Object,
  loading: Boolean,
  title: { type: String, default: 'AI 分析结果' },
})
defineEmits(['close'])

function actionColor(action) {
  const map = { hold: '#4fc3f7', add: '#00c853', reduce: '#ff9800', sell: '#ff5252' }
  return map[(action || '').toLowerCase()] || '#8892a4'
}
</script>

<template>
  <Teleport to="body">
    <div v-if="visible" class="ai-modal-overlay" @click.self="$emit('close')">
      <div class="ai-modal">
        <div class="ai-modal-header">
          <h3>{{ title }}</h3>
          <button class="ai-modal-close" @click="$emit('close')">&times;</button>
        </div>
        <div class="ai-modal-body">
          <div v-if="loading" class="ai-loading">AI 分析中...</div>
          <div v-else-if="!analysis" class="ai-loading">无分析数据</div>
          <template v-else>
            <div v-if="analysis.symbol" class="ai-field">
              <span class="ai-label">标的</span>
              <span class="ai-value" style="font-weight:700;color:#fff">{{ analysis.symbol }}</span>
            </div>
            <div v-if="analysis.status_assessment" class="ai-field">
              <span class="ai-label">状态评估</span>
              <span class="ai-value">{{ analysis.status_assessment }}</span>
            </div>
            <div v-if="analysis.recommended_action" class="ai-field">
              <span class="ai-label">建议操作</span>
              <span class="ai-value ai-action" :style="{ color: actionColor(analysis.recommended_action) }">
                {{ analysis.recommended_action }}
              </span>
            </div>
            <div v-if="analysis.key_concerns" class="ai-field">
              <span class="ai-label">关键关注点</span>
              <ul class="ai-list">
                <li v-if="Array.isArray(analysis.key_concerns)" v-for="(c, i) in analysis.key_concerns" :key="i">{{ c }}</li>
                <li v-else>{{ analysis.key_concerns }}</li>
              </ul>
            </div>
            <div v-if="analysis.next_catalyst" class="ai-field">
              <span class="ai-label">下一催化剂</span>
              <span class="ai-value">{{ analysis.next_catalyst }}</span>
            </div>
            <div v-if="analysis.confidence != null" class="ai-field">
              <span class="ai-label">信心度</span>
              <div class="ai-confidence">
                <div class="ai-confidence-bar" :style="{ width: (analysis.confidence * 100) + '%' }"></div>
              </div>
              <span class="ai-value">{{ (analysis.confidence * 100).toFixed(0) }}%</span>
            </div>
            <!-- Fallback for unexpected structure -->
            <div v-if="analysis.advice || analysis.text || analysis.content" class="ai-field">
              <span class="ai-label">建议</span>
              <div class="ai-text">{{ analysis.advice || analysis.text || analysis.content }}</div>
            </div>
            <div v-if="analysis.summary" class="ai-field">
              <span class="ai-label">摘要</span>
              <div class="ai-text">{{ analysis.summary }}</div>
            </div>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.ai-modal-overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.6); z-index: 1000;
  display: flex; align-items: center; justify-content: center;
}
.ai-modal {
  background: #16213e; border-radius: 12px; width: 520px; max-width: 92vw;
  max-height: 80vh; overflow-y: auto; box-shadow: 0 8px 32px rgba(0,0,0,0.5);
}
.ai-modal-header {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 20px; border-bottom: 1px solid #2a3a5e;
}
.ai-modal-header h3 { margin: 0; color: #fff; font-size: 16px; }
.ai-modal-close {
  background: none; border: none; color: #8892a4; font-size: 24px; cursor: pointer; line-height: 1;
}
.ai-modal-close:hover { color: #fff; }
.ai-modal-body { padding: 20px; }
.ai-loading { color: #8892a4; text-align: center; padding: 40px 0; font-size: 15px; }
.ai-field { margin-bottom: 16px; }
.ai-label { display: block; color: #8892a4; font-size: 12px; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
.ai-value { color: #e0e6ed; font-size: 14px; }
.ai-action { font-weight: 700; font-size: 16px; text-transform: uppercase; }
.ai-list { color: #e0e6ed; font-size: 14px; margin: 4px 0 0 16px; padding: 0; }
.ai-list li { margin-bottom: 4px; }
.ai-text { color: #e0e6ed; font-size: 14px; white-space: pre-wrap; line-height: 1.6; }
.ai-confidence { background: #2a3a5e; border-radius: 4px; height: 8px; width: 100%; margin: 6px 0; }
.ai-confidence-bar { background: linear-gradient(90deg, #4fc3f7, #00c853); height: 100%; border-radius: 4px; transition: width 0.3s; }
</style>
