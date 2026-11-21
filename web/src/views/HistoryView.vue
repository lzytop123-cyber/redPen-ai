<template>
  <div class="history-page">
    <div v-if="!userState.user" class="guest-box paper-card">
      <h2>登录后查看个人精批记录与薄弱项画像</h2>
      <p>系统会自动沉淀你历次申论与考研英语作文的得分曲线与高频扣分项。</p>
      <div class="guest-actions">
        <button class="btn btn-primary" @click="openAuthModal('login')">立即登录</button>
        <button class="btn btn-outline" @click="openAuthModal('register')">免费注册领 3 次精批</button>
      </div>
    </div>

    <template v-else>
      <!-- 顶部统计概览 -->
      <section class="stats-row">
        <div class="stat-card paper-card">
          <div class="stat-label">累计精批篇数</div>
          <div class="stat-val">{{ items.length }}</div>
          <div class="stat-sub">已完成 {{ completedCount }} 篇</div>
        </div>
        <div class="stat-card paper-card">
          <div class="stat-label">平均得分率</div>
          <div class="stat-val">{{ avgRateText }}</div>
          <div class="stat-sub">基于已完成报告统计</div>
        </div>
        <div class="stat-card paper-card">
          <div class="stat-label">最高频扣分薄弱项</div>
          <div class="stat-val small">{{ weaknesses[0]?.tag || "暂无数据" }}</div>
          <div class="stat-sub">
            {{ weaknesses[0] ? `累计出现 ${weaknesses[0].count} 次` : "完成首次批改后生成画像" }}
          </div>
        </div>
      </section>

      <!-- 薄弱项分布 -->
      <section v-if="weaknesses.length" class="paper-card block-card">
        <div class="block-head">
          <h2>我的高频扣分薄弱项画像</h2>
          <span class="block-sub">按历史精批报告自动聚合</span>
        </div>
        <div class="weakness-bars">
          <div v-for="w in weaknesses" :key="w.tag" class="w-row">
            <span class="w-tag"># {{ w.tag }}</span>
            <div class="w-track">
              <div
                class="w-fill"
                :style="{ width: `${Math.max(12, Math.round((w.count / maxWeaknessCount) * 100))}%` }"
              ></div>
            </div>
            <span class="w-cnt">{{ w.count }} 次</span>
          </div>
        </div>
      </section>

      <!-- 历史精批记录 -->
      <section class="paper-card block-card">
        <div class="block-head">
          <h2>历史精批记录（{{ items.length }}）</h2>
          <button class="btn btn-outline btn-sm" :disabled="loading" @click="loadHistory">
            {{ loading ? "刷新中..." : "刷新列表" }}
          </button>
        </div>

        <div v-if="loading && items.length === 0" class="empty-tip">正在加载历史记录...</div>
        <div v-else-if="items.length === 0" class="empty-tip">
          还没有批改记录，快去真题精批库练一篇吧。
        </div>

        <div v-else class="history-table">
          <div
            v-for="item in items"
            :key="item.task_id"
            class="h-row"
            @click="$emit('openReport', item.task_id)"
          >
            <div class="h-main">
              <div class="h-title-line">
                <span class="h-type">{{ examTypeName(item.exam_type) }}</span>
                <span class="h-title">{{ item.question_title }}</span>
              </div>
              <div class="h-meta">
                <span>{{ formatTime(item.created_at) }}</span>
                <span v-if="item.weakness_tags?.length" class="h-tags">
                  <span v-for="t in item.weakness_tags.slice(0, 3)" :key="t" class="mini-tag">
                    {{ t }}
                  </span>
                </span>
              </div>
            </div>

            <div class="h-right">
              <div v-if="item.status === 'completed' && item.final_score !== null" class="h-score-box">
                <span class="h-score">{{ item.final_score }}<small>/{{ item.full_score }}</small></span>
                <span class="h-band">{{ item.band_label }}</span>
              </div>
              <span v-else :class="['status-pill', item.status]">
                {{ statusText(item.status) }}
              </span>

              <button
                v-if="item.status === 'completed'"
                class="btn btn-outline btn-sm"
                @click.stop="$emit('rewriteQuestion', item.question_id, item.task_id)"
              >
                二刷重写
              </button>
              <button class="btn btn-ghost btn-sm">查看报告 →</button>
            </div>
          </div>
        </div>
      </section>
    </template>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { apiRequest } from "../api/client";
import { openAuthModal, userState } from "../stores/auth";
import type { HistoryItem, HistoryResp } from "../types";

defineEmits<{
  (e: "openReport", taskId: string): void;
  (e: "rewriteQuestion", questionId: string, fromTaskId: string): void;
}>();

const loading = ref(false);
const weaknesses = ref<Array<{ tag: string; count: number }>>([]);
const items = ref<HistoryItem[]>([]);

const completedItems = computed(() =>
  items.value.filter((i) => i.status === "completed" && i.final_score !== null && i.full_score)
);

const completedCount = computed(() => completedItems.value.length);

const avgRateText = computed(() => {
  if (!completedItems.value.length) return "—";
  const sum = completedItems.value.reduce(
    (acc, cur) => acc + ((cur.final_score || 0) / (cur.full_score || 1)),
    0
  );
  return `${Math.round((sum / completedItems.value.length) * 100)}%`;
});

const maxWeaknessCount = computed(() =>
  Math.max(1, ...weaknesses.value.map((w) => w.count))
);

function examTypeName(t: string) {
  if (t === "shenlun_short") return "申论小题";
  if (t === "shenlun_essay") return "申论大作文";
  if (t === "kaoyan_english") return "考研英语";
  if (t === "kaoyan_396") return "396经综";
  return t;
}

function statusText(s: string) {
  if (s === "pending") return "排队中";
  if (s === "running") return "批改中";
  if (s === "failed") return "批改失败";
  return s;
}

function formatTime(iso: string) {
  if (!iso) return "";
  const d = new Date(iso.endsWith("Z") ? iso : `${iso}Z`);
  if (Number.isNaN(d.getTime())) return iso.slice(0, 16).replace("T", " ");
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function loadHistory() {
  if (!userState.user) return;
  loading.value = true;
  try {
    const res = await apiRequest<HistoryResp>("/api/grading/history");
    weaknesses.value = res.top_weaknesses || [];
    items.value = res.items || [];
  } finally {
    loading.value = false;
  }
}

watch(
  () => userState.user?.user_id,
  (uid) => {
    if (uid) loadHistory();
    else {
      weaknesses.value = [];
      items.value = [];
    }
  }
);

onMounted(() => {
  if (userState.user) loadHistory();
});
</script>

<style scoped>
.history-page {
  max-width: 1180px;
  margin: 0 auto;
  padding: 24px 24px 48px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.guest-box {
  padding: 56px 24px;
  text-align: center;
}

.guest-box h2 {
  margin: 0 0 8px;
  font-family: var(--font-serif);
}

.guest-box p {
  margin: 0 0 20px;
  color: var(--ink-muted);
}

.guest-actions {
  display: flex;
  justify-content: center;
  gap: 12px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.stat-card {
  padding: 20px 24px;
}

.stat-label {
  font-size: 12.5px;
  color: var(--ink-muted);
  font-weight: 500;
}

.stat-val {
  font-family: var(--font-serif);
  font-size: 32px;
  font-weight: 900;
  color: var(--ink-primary);
  margin: 6px 0 4px;
}

.stat-val.small {
  font-size: 20px;
  color: var(--red-pen);
}

.stat-sub {
  font-size: 12px;
  color: var(--ink-muted);
}

.block-card {
  padding: 22px 24px;
}

.block-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.block-head h2 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 17px;
}

.block-sub {
  font-size: 12px;
  color: var(--ink-muted);
}

.weakness-bars {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.w-row {
  display: grid;
  grid-template-columns: 160px 1fr 56px;
  align-items: center;
  gap: 14px;
}

.w-tag {
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.w-track {
  height: 10px;
  border-radius: 99px;
  background: var(--bg-inset);
  overflow: hidden;
}

.w-fill {
  height: 100%;
  border-radius: 99px;
  background: linear-gradient(90deg, var(--brand), var(--red-pen));
}

.w-cnt {
  text-align: right;
  font-size: 12.5px;
  color: var(--ink-secondary);
  font-weight: 600;
}

.empty-tip {
  padding: 40px 0;
  text-align: center;
  color: var(--ink-muted);
}

.history-table {
  display: flex;
  flex-direction: column;
}

.h-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 15px 12px;
  border-bottom: 1px solid var(--bg-inset);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background 0.15s ease;
}

.h-row:hover {
  background: var(--bg-subtle);
}

.h-main {
  min-width: 0;
  flex: 1;
}

.h-title-line {
  display: flex;
  align-items: center;
  gap: 8px;
}

.h-type {
  font-size: 11.5px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 4px;
  background: var(--brand-soft);
  color: var(--brand);
  flex-shrink: 0;
}

.h-title {
  font-size: 14.5px;
  font-weight: 600;
  color: var(--ink-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.h-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 6px;
  font-size: 12px;
  color: var(--ink-muted);
}

.h-tags {
  display: flex;
  gap: 6px;
}

.mini-tag {
  background: var(--red-pen-soft);
  color: var(--red-pen);
  padding: 1px 7px;
  border-radius: 99px;
}

.h-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.h-score-box {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
}

.h-score {
  font-family: var(--font-serif);
  font-size: 20px;
  font-weight: 900;
  color: var(--brand);
  line-height: 1.1;
}

.h-score small {
  font-size: 12px;
  font-weight: 500;
  color: var(--ink-muted);
}

.h-band {
  font-size: 11.5px;
  color: var(--ink-secondary);
}

.status-pill {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 99px;
  font-weight: 600;
}

.status-pill.pending,
.status-pill.running {
  background: var(--brand-soft);
  color: var(--brand);
}

.status-pill.failed {
  background: var(--red-pen-soft);
  color: var(--red-pen);
}

@media (max-width: 760px) {
  .stats-row {
    grid-template-columns: 1fr;
  }
  .h-row {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
