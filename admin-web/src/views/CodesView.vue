<template>
  <div class="card">
    <div class="card-title">
      <span>🎁 兑换码与卡密发货中心（共 {{ total }} 个）</span>
      <a class="btn btn-success" :href="exportCodesCsvUrl()" target="_blank">⬇️ 导出可用卡密 CSV（小红书/淘宝发货）</a>
    </div>

    <div class="gen-box">
      <div class="toolbar" style="margin-bottom:0;">
        <input v-model="planName" class="input" placeholder="套餐名称" style="width:180px;" />
        <span>生成</span>
        <input v-model.number="count" type="number" class="input" style="width:72px;" />
        <span>个 ｜ 加次数</span>
        <input v-model.number="addQuota" type="number" class="input" style="width:72px;" />
        <span>次 ｜ 加月卡</span>
        <input v-model.number="addVipDays" type="number" class="input" style="width:72px;" />
        <span>天</span>
        <button class="btn btn-primary" :disabled="generating" @click="genCodes">
          {{ generating ? "生成中..." : "一键批量生成" }}
        </button>
      </div>
      <div v-if="latestCodes.length" class="latest-box">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;">
          <b>刚刚生成的 {{ latestCodes.length }} 个兑换码：</b>
          <button class="btn btn-sm btn-primary" @click="copyLatest">📋 一键全部复制</button>
        </div>
        <pre style="margin:0;font-family:monospace;">{{ latestCodes.join("\n") }}</pre>
      </div>
    </div>

    <div class="toolbar">
      <select v-model="status" class="select" @change="resetAndLoad">
        <option value="all">全部状态</option>
        <option value="unused">仅看可用</option>
        <option value="used">仅看已核销</option>
      </select>
      <button class="btn btn-sm" @click="load">刷新</button>
    </div>

    <table class="tbl">
      <thead>
        <tr>
          <th>兑换码</th>
          <th>套餐名称</th>
          <th>权益</th>
          <th>状态</th>
          <th>核销用户</th>
          <th>创建时间</th>
          <th>操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="r in items" :key="r.code">
          <td><code style="font-weight:700;">{{ r.code }}</code></td>
          <td>{{ r.plan_name }}</td>
          <td>+{{ r.add_quota }} 次 / +{{ r.add_vip_days }} 天</td>
          <td><span :class="['badge', r.is_used ? 'badge-gray' : 'badge-green']">{{ r.is_used ? "已核销" : "可用" }}</span></td>
          <td>{{ r.used_by_user_id ? `#${r.used_by_user_id}` : "-" }}</td>
          <td style="font-size:12px;color:#64748b;">{{ (r.created_at || "").replace("T", " ").slice(0, 16) }}</td>
          <td>
            <button v-if="!r.is_used" class="btn btn-sm" @click="copyOne(r.code)">复制</button>
            <button v-if="!r.is_used" class="btn btn-sm btn-danger" @click="deleteCode(r.code)">作废</button>
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
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { adminFetch, exportCodesCsvUrl } from "../api";

const planName = ref("冲刺体验包(5次)");
const count = ref(10);
const addQuota = ref(5);
const addVipDays = ref(0);
const generating = ref(false);
const latestCodes = ref<string[]>([]);

const status = ref("all");
const page = ref(1);
const pageSize = 30;
const total = ref(0);
const items = ref<any[]>([]);

async function load() {
  const qs = new URLSearchParams({ status: status.value, page: String(page.value), page_size: String(pageSize) });
  const res = await adminFetch(`/api/admin/codes?${qs.toString()}`);
  total.value = res.total;
  items.value = res.items;
}

function resetAndLoad() {
  page.value = 1;
  load();
}

async function genCodes() {
  generating.value = true;
  try {
    const res = await adminFetch("/api/admin/codes", {
      method: "POST",
      body: JSON.stringify({
        plan_name: planName.value,
        count: count.value,
        add_quota: addQuota.value,
        add_vip_days: addVipDays.value,
      }),
    });
    latestCodes.value = res.created;
    load();
  } finally {
    generating.value = false;
  }
}

function copyLatest() {
  navigator.clipboard.writeText(latestCodes.value.join("\n"));
  alert("已复制全部新生成的兑换码！");
}

function copyOne(code: string) {
  navigator.clipboard.writeText(code);
  alert(`已复制兑换码：${code}`);
}

async function deleteCode(code: string) {
  if (!confirm(`确认作废兑换码 ${code} 吗？`)) return;
  await adminFetch(`/api/admin/codes/${encodeURIComponent(code)}`, { method: "DELETE" });
  load();
}

onMounted(load);
</script>

<style scoped>
.gen-box {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 10px;
  padding: 16px;
  margin-bottom: 18px;
}
.latest-box {
  margin-top: 14px;
  padding: 14px;
  background: #f0fdf4;
  border: 1px solid #86efac;
  border-radius: 8px;
}
</style>
