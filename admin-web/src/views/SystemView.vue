<template>
  <div class="card" v-if="info">
    <div class="card-title">
      <span>⚙️ 系统配置与 AI 模型健康检查</span>
      <button class="btn btn-primary" :disabled="pinging" @click="pingLlm">
        {{ pinging ? "正在测试连通性..." : "🔌 一键检测文本模型余额与连通性" }}
      </button>
    </div>

    <div v-if="pingResult" :class="['ping-banner', pingResult.ok ? 'ping-ok' : 'ping-err']">
      {{ pingResult.ok ? "✅" : "❌" }} {{ pingResult.detail }}
    </div>

    <table class="tbl">
      <tbody>
        <tr><th style="width:220px;">文本精批模型</th><td><b>{{ info.llm_model }}</b>（{{ info.llm_base_url }}）</td></tr>
        <tr><th>文本模型 API Key</th><td><code>{{ info.llm_key_masked }}</code></td></tr>
        <tr><th>手写拍照视觉模型 (VLM)</th><td><b>{{ info.vlm_model }}</b>（{{ info.vlm_base_url }}）</td></tr>
        <tr><th>视觉模型 API Key</th><td>
          <span :class="['badge', info.vlm_key_masked === '未配置' ? 'badge-amber' : 'badge-green']">{{ info.vlm_key_masked }}</span>
          <span v-if="info.vlm_key_masked === '未配置'" style="color:#b45309;font-size:12px;margin-left:8px;">上线前请配置阿里云 qwen-vl-max Key，否则拍照识别走 Mock</span>
        </td></tr>
        <tr><th>当前数据库</th><td><span class="badge badge-blue">{{ info.database_type }}</span></td></tr>
        <tr><th>Mock 演示兜底开关</th><td>
          <span :class="['badge', info.mock_fallback_enabled ? 'badge-amber' : 'badge-green']">
            {{ info.mock_fallback_enabled ? "已开启（上线前建议设为 false）" : "已关闭（生产严格模式）" }}
          </span>
        </td></tr>
        <tr><th>微信小程序 AppID / Secret</th><td>
          <span :class="['badge', info.wx_appid_configured ? 'badge-green' : 'badge-amber']">
            {{ info.wx_appid_configured ? "已配置正式凭证" : "未配置（当前为开发测试登录）" }}
          </span>
        </td></tr>
      </tbody>
    </table>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { adminFetch } from "../api";

const info = ref<any>(null);
const pinging = ref(false);
const pingResult = ref<{ ok: boolean; detail: string } | null>(null);

async function pingLlm() {
  pinging.value = true;
  pingResult.value = null;
  try {
    pingResult.value = await adminFetch("/api/admin/system/ping-llm", { method: "POST" });
  } finally {
    pinging.value = false;
  }
}

onMounted(async () => {
  info.value = await adminFetch("/api/admin/system");
});
</script>

<style scoped>
.ping-banner {
  padding: 12px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 13px;
  font-weight: 600;
}
.ping-ok { background: #dcfce7; color: #166534; }
.ping-err { background: #fee2e2; color: #991b1b; }
</style>
