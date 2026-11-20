<template>
  <div class="card">
    <div class="card-title">
      <span>👥 用户管理（共 {{ total }} 人）</span>
      <button class="btn btn-sm" @click="load">刷新</button>
    </div>

    <div class="toolbar">
      <input v-model="keyword" class="input" placeholder="搜索昵称或 OpenID" style="width:240px;" @keyup.enter="resetAndLoad" />
      <label style="display:flex;align-items:center;gap:6px;font-size:13px;cursor:pointer;">
        <input v-model="vipOnly" type="checkbox" @change="resetAndLoad" /> 仅看月卡生效用户
      </label>
      <button class="btn btn-primary" @click="resetAndLoad">搜索</button>
    </div>

    <table class="tbl">
      <thead>
        <tr>
          <th>ID</th>
          <th>昵称</th>
          <th>OpenID</th>
          <th>累计批改</th>
          <th>免费余次</th>
          <th>付费余次</th>
          <th>月卡状态</th>
          <th>注册时间</th>
          <th>售后操作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in items" :key="u.user_id">
          <td>#{{ u.user_id }}</td>
          <td><b>{{ u.nickname }}</b></td>
          <td><code style="font-size:12px;">{{ u.openid }}</code></td>
          <td><span class="badge badge-blue">{{ u.task_count }} 篇</span></td>
          <td>{{ u.free_quota }}</td>
          <td><b>{{ u.paid_quota }}</b></td>
          <td>
            <span v-if="u.is_vip" class="badge badge-green">至 {{ (u.vip_expire_at || "").slice(0, 10) }}</span>
            <span v-else style="color:#94a3b8;">未开通</span>
          </td>
          <td style="font-size:12px;color:#64748b;">{{ (u.created_at || "").replace("T", " ").slice(0, 16) }}</td>
          <td>
            <button class="btn btn-sm btn-primary" @click="adjust(u.user_id, 5, 0)">+5次</button>
            <button class="btn btn-sm btn-success" @click="adjust(u.user_id, 0, 30)">+30天月卡</button>
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
import { adminFetch } from "../api";

const keyword = ref("");
const vipOnly = ref(false);
const page = ref(1);
const pageSize = 20;
const total = ref(0);
const items = ref<any[]>([]);

async function load() {
  const qs = new URLSearchParams({
    page: String(page.value),
    page_size: String(pageSize),
    vip_only: String(vipOnly.value),
  });
  if (keyword.value.trim()) qs.set("keyword", keyword.value.trim());
  const res = await adminFetch(`/api/admin/users?${qs.toString()}`);
  total.value = res.total;
  items.value = res.items;
}

function resetAndLoad() {
  page.value = 1;
  load();
}

async function adjust(uid: number, addQuota: number, addVipDays: number) {
  const desc = addVipDays > 0 ? `开通/延长 ${addVipDays} 天月卡` : `增加 ${addQuota} 次精批额度`;
  if (!confirm(`确认为用户 #${uid} ${desc} 吗？`)) return;
  await adminFetch(`/api/admin/users/${uid}/adjust`, {
    method: "POST",
    body: JSON.stringify({ add_quota: addQuota, add_vip_days: addVipDays }),
  });
  load();
}

onMounted(load);
</script>
