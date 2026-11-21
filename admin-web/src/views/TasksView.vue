<template>
  <div class="card">
    <div class="card-title">
      <span>📝 批改记录与质检中心（共 {{ total }} 条）</span>
      <button class="btn btn-sm" @click="load">刷新列表</button>
    </div>

    <div class="toolbar">
      <select v-model="status" class="select" @change="resetAndLoad">
        <option value="">全部状态</option>
        <option value="completed">已完成</option>
        <option value="failed">失败异常</option>
        <option value="running">批改中</option>
      </select>
      <select v-model="examType" class="select" @change="resetAndLoad">
        <option value="">全部题型</option>
        <option value="shenlun_short">申论小题</option>
        <option value="shenlun_essay">申论大作文</option>
        <option value="kaoyan_english">考研英语</option>
      </select>
      <input v-model="keyword" class="input" placeholder="搜索任务ID / 真题ID / 标题" style="width:240px;" @keyup.enter="resetAndLoad" />
      <button class="btn btn-primary" @click="resetAndLoad">筛选</button>
    </div>

    <table class="tbl">
      <thead>
        <tr>
          <th>任务 ID</th>
          <th>用户</th>
          <th>题目</th>
          <th>状态</th>
          <th>得分</th>
          <th>原图</th>
          <th>时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="t in items" :key="t.task_id">
          <td><code>{{ t.task_id }}</code></td>
          <td>#{{ t.user_id }}</td>
          <td style="max-width:260px;">{{ t.question_title }}</td>
          <td>
            <span :class="['badge', t.status === 'completed' ? 'badge-green' : t.status === 'failed' ? 'badge-red' : 'badge-amber']">
              {{ t.status }}
            </span>
          </td>
          <td><b>{{ t.final_score ?? "-" }}</b> / {{ t.full_score ?? "-" }}</td>
          <td><span v-if="t.has_image" class="badge badge-blue">有手写图</span><span v-else style="color:#94a3b8;">纯文本</span></td>
          <td style="font-size:12px;color:#64748b;">{{ formatTime(t.created_at) }}</td>
          <td>
            <button class="btn btn-sm btn-primary" @click="openDetail(t.task_id)">查看详情</button>
            <button class="btn btn-sm" @click="refund(t.task_id)">退还1次</button>
          </td>
        </tr>
      </tbody>
    </table>

    <div class="pager">
      <span>第 {{ page }} 页 / 共 {{ Math.max(1, Math.ceil(total / pageSize)) }} 页</span>
      <div style="display:flex;gap:8px;">
        <button class="btn btn-sm" :disabled="page <= 1" @click="page--; load()">上一页</button>
        <button class="btn btn-sm" :disabled="page * pageSize >= total" @click="page++; load()">下一页</button>
      </div>
    </div>
  </div>

  <!-- 抽屉：查看手写原图 + 作答原文 + 完整 AI 红笔批改详情 -->
  <div v-if="detail" class="modal-mask" @click.self="detail = null">
    <div class="drawer">
      <div class="drawer-head">
        <div>
          <div style="font-weight:700;font-size:16px;">{{ detail.question_title }}</div>
          <div style="font-size:12px;color:#64748b;margin-top:4px;">
            任务 {{ detail.task_id }} ｜ 用户 #{{ detail.user_id }} ({{ detail.user_nickname }}) ｜ 得分 {{ detail.final_score ?? "-" }} / {{ detail.full_score ?? "-" }}
          </div>
        </div>
        <button class="btn btn-sm" @click="detail = null">关闭</button>
      </div>
      <div class="drawer-body">
        <div v-if="detail.error_message" class="card" style="background:#fef2f2;border:1px solid #fecaca;color:#b91c1c;">
          <b>失败报错信息：</b>{{ detail.error_message }}
        </div>

        <div v-if="detail.image_filename" class="detail-sec">
          <h4>📷 用户上传的手写答卷原图</h4>
          <a v-if="detailImageUrl" :href="detailImageUrl" target="_blank">
            <img :src="detailImageUrl" style="max-width:100%;max-height:360px;border-radius:8px;border:1px solid #e2e8f0;" />
          </a>
          <div v-else style="font-size:12px;color:#64748b;">正在加载原图...</div>
        </div>

        <div class="detail-sec">
          <h4>✍️ 考生作答原文（{{ detail.student_answer.length }} 字符）</h4>
          <div class="text-block">{{ detail.student_answer }}</div>
        </div>

        <div v-if="detail.report?.shenlun_detail" class="detail-sec">
          <h4>🎯 采分点命中明细</h4>
          <table class="tbl">
            <thead><tr><th>编号</th><th>判定</th><th>原文依据</th><th>点评</th></tr></thead>
            <tbody>
              <tr v-for="m in detail.report.shenlun_detail.point_matches" :key="m.point_id">
                <td><b>{{ m.point_id }}</b></td>
                <td><span :class="['badge', m.status==='hit'?'badge-green':m.status==='partial'?'badge-amber':'badge-red']">{{ m.status }}</span></td>
                <td>{{ m.evidence_quote || "—" }}</td>
                <td>{{ m.comment }}</td>
              </tr>
            </tbody>
          </table>
        </div>

        <div v-if="detail.report?.annotations?.length" class="detail-sec">
          <h4>🖊️ 逐句红笔批注</h4>
          <div v-for="(a, idx) in detail.report.annotations" :key="idx" class="ann-card">
            <span class="badge badge-red">{{ a.sentence_id }} · {{ a.issue_type }}</span>
            <span style="margin-left:8px;">{{ a.comment }}</span>
            <div style="color:#1d4ed8;margin-top:4px;">建议改写：{{ a.suggestion }}</div>
          </div>
        </div>

        <div v-if="detail.report?.upgraded_answer" class="detail-sec">
          <h4>✨ 同思路高分升格范文</h4>
          <div class="text-block" style="background:#f0f9ff;border-color:#bae6fd;">{{ detail.report.upgraded_answer }}</div>
        </div>
      </div>
      <div class="drawer-foot">
        <button class="btn btn-danger" @click="refund(detail.task_id)">售后退还该用户 1 次额度</button>
        <button class="btn btn-primary" @click="detail = null">完成关闭</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { adminFetch, fetchUploadImageBlobUrl } from "../api";

const status = ref("");
const examType = ref("");
const keyword = ref("");
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const items = ref<any[]>([]);
const detail = ref<any>(null);
const detailImageUrl = ref("");

function revokeDetailImg() {
  if (detailImageUrl.value) {
    URL.revokeObjectURL(detailImageUrl.value);
    detailImageUrl.value = "";
  }
}

watch(detail, (val) => {
  if (!val) revokeDetailImg();
});

onBeforeUnmount(revokeDetailImg);

function formatTime(v: string) {
  return v ? v.replace("T", " ").slice(0, 16) : "";
}

async function load() {
  const qs = new URLSearchParams({ page: String(page.value), page_size: String(pageSize) });
  if (status.value) qs.set("status", status.value);
  if (examType.value) qs.set("exam_type", examType.value);
  if (keyword.value.trim()) qs.set("keyword", keyword.value.trim());
  const res = await adminFetch(`/api/admin/tasks?${qs.toString()}`);
  total.value = res.total;
  items.value = res.items;
}

function resetAndLoad() {
  page.value = 1;
  load();
}

async function openDetail(taskId: string) {
  revokeDetailImg();
  const data = await adminFetch(`/api/admin/tasks/${encodeURIComponent(taskId)}`);
  detail.value = data;
  if (data.image_filename) {
    try {
      detailImageUrl.value = await fetchUploadImageBlobUrl(data.image_filename);
    } catch {
      detailImageUrl.value = "";
    }
  }
}

async function refund(taskId: string) {
  if (!confirm("确认为该批改任务的提交用户退还 1 次付费精批额度吗？")) return;
  const res = await adminFetch(`/api/admin/tasks/${encodeURIComponent(taskId)}/refund`, { method: "POST" });
  alert(`已退还！用户 #${res.user_id} 当前付费余次：${res.paid_quota}`);
}

onMounted(load);
</script>

<style scoped>
.detail-sec { margin-bottom: 20px; }
.detail-sec h4 { margin: 0 0 8px; font-size: 14px; color: #1e293b; }
.text-block {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 8px;
  padding: 14px;
  white-space: pre-wrap;
  line-height: 1.75;
  font-size: 13px;
}
.ann-card {
  padding: 10px 12px;
  background: #fff5f5;
  border-left: 3px solid #ef4444;
  border-radius: 6px;
  margin-bottom: 8px;
  font-size: 13px;
}
</style>
