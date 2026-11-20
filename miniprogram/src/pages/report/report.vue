<template>
  <view class="page">
    <!-- 批改中：4 步仪式感实时进度条 -->
    <view v-if="status !== 'completed'" class="loading-card">
      <view class="spinner-title">{{ status === "failed" ? "批改遇到问题" : "AI 阅卷组长正在精批中..." }}</view>
      <view class="progress-msg">{{ progressMessage }}</view>

      <view v-if="status !== 'failed'" class="step-list">
        <view
          v-for="(step, idx) in steps"
          :key="step.label"
          :class="['step-item', currentStepIndex > idx ? 'done' : currentStepIndex === idx ? 'active' : '']"
        >
          <text class="step-icon">{{ currentStepIndex > idx ? "✓" : currentStepIndex === idx ? "●" : "○" }}</text>
          <text class="step-text">{{ step.label }}</text>
        </view>
      </view>

      <view v-if="status !== 'failed'" class="tip-box">
        💡 阅卷小贴士：{{ currentTip }}
      </view>
      <view v-if="errorMessage" class="err-msg">{{ errorMessage }}</view>
    </view>

    <!-- 完整红笔报告 -->
    <view v-else-if="report">
      <view class="hero">
        <view class="hero-left">
          <view class="hero-sub">AI 阅卷级精批报告</view>
          <view class="hero-title">{{ report.question_title }}</view>
          <view class="hero-meta">统计字数：{{ report.word_count }}</view>
        </view>
        <view class="hero-right">
          <view class="score-num">{{ report.final_score }}<text class="score-full">/{{ report.full_score }}</text></view>
          <view class="band">{{ report.band_label }}</view>
        </view>
      </view>

      <view v-if="report.word_count_warning" class="warn-box">
        ⚠️ {{ report.word_count_warning }}
      </view>

      <!-- 申论采分点明细 + 命中率可视化条 -->
      <view v-if="report.shenlun_detail" class="card">
        <view class="card-h-row">
          <view class="card-h">一、标准采分点核对</view>
          <text class="hit-summary">命中 {{ hitStats.hit }} / {{ hitStats.total }}（部分 {{ hitStats.partial }}）</text>
        </view>

        <view v-if="hitStats.total > 0" class="meter-wrap">
          <view class="meter-bar">
            <view class="meter-fill" :style="{ width: hitStats.percent + '%' }" />
          </view>
          <text class="meter-pct">{{ hitStats.percent }}%</text>
        </view>

        <view v-for="m in report.shenlun_detail.point_matches" :key="m.point_id" class="point-row">
          <view class="point-head">
            <text class="pid">{{ m.point_id }}</text>
            <text :class="['badge', m.status]">{{ statusLabel[m.status] || m.status }}</text>
          </view>
          <view v-if="m.status !== 'miss' && m.evidence_quote" class="quote-box">
            作答原文：{{ m.evidence_quote }}
          </view>
          <view class="point-comment">{{ m.comment }}</view>
        </view>
      </view>

      <!-- 大作文 / 考研英语维度定档 -->
      <view v-if="report.shenlun_essay_detail || report.kaoyan_detail" class="card">
        <view class="card-h">一、官方评分维度定档</view>
        <view
          v-for="d in (report.shenlun_essay_detail || report.kaoyan_detail).dimensions"
          :key="d.dimension"
          class="point-row"
        >
          <view class="point-head">
            <text class="pid">{{ d.dimension }}</text>
            <text class="badge hit">第 {{ d.level }} 档 / 5 档</text>
          </view>
          <view class="point-comment">{{ d.comment }}</view>
        </view>
      </view>

      <!-- 逐句红笔批注（支持只看扣分句筛选） -->
      <view class="card">
        <view class="card-h-row">
          <view class="card-h">二、逐句红笔批注</view>
          <view class="filter-toggle" @click="onlyIssues = !onlyIssues">
            {{ onlyIssues ? "显示全部句子" : "只看批注句" }}
          </view>
        </view>
        <view
          v-for="s in visibleSentences"
          :key="s.sentence_id"
          :class="['sent-box', hasIssue(s.sentence_id) ? 'sent-red' : '']"
        >
          <view class="sent-text">
            <text class="sid">{{ s.sentence_id }}</text>{{ s.text }}
          </view>
          <view v-for="(ann, i) in getAnnotations(s.sentence_id)" :key="i" class="ann-note">
            <text :class="['ann-tag', ann.severity === 'positive' ? 'ann-tag-good' : '']">
              {{ issueLabel[ann.issue_type] || ann.issue_type }}
            </text>
            <text>{{ ann.comment }}</text>
            <view class="ann-suggest">建议改写：{{ ann.suggestion }}</view>
          </view>
        </view>
      </view>

      <!-- 同思路升格范文（带一键复制） -->
      <view class="card">
        <view class="card-h-row">
          <view class="card-h">三、同思路高分升格版</view>
          <button class="copy-btn" size="mini" @click="copyUpgraded">📋 一键复制</button>
        </view>
        <view class="upgrade-box">{{ report.upgraded_answer }}</view>
        <view class="imp-title">核心提分改动：</view>
        <view v-for="(imp, idx) in report.key_improvements" :key="idx" class="imp-item">
          • {{ imp }}
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad, onUnload } from "@dcloudio/uni-app";
import { request } from "@/utils/request";

const statusLabel: Record<string, string> = { hit: "命中", partial: "部分命中", miss: "未命中" };
const issueLabel: Record<string, string> = {
  grammar: "语法/拼写",
  expression: "表达规范",
  missing_point: "漏采分点",
  logic: "逻辑问题",
  redundancy: "啰嗦超字",
  highlight: "亮点句",
};

const steps = [
  { label: "校验答卷与字数红线" },
  { label: "对照真题采分点与官方量表核对" },
  { label: "生成逐句红笔批注与反幻觉核验" },
  { label: "撰写同思路高分升格范文" },
];

const writingTips = [
  "申论小题每条句首加 4~6 字规范总括词，阅卷老师扫一眼就能给分。",
  "考研英语大作文避免反复使用 more and more / very important，换成地道学术词立刻升档。",
  "申论大作文切忌脱离给定材料自说自话，至少引用 2~3 个材料原案例作论据。",
  "字数红线非常关键：申论小题超上限 20 字以上通常会被硬性扣分。",
];

const taskId = ref("");
const status = ref("pending");
const progressMessage = ref("正在排队...");
const errorMessage = ref("");
const report = ref<any>(null);
const onlyIssues = ref(false);
const tickCount = ref(0);
let timer: any = null;

const currentTip = computed(() => writingTips[tickCount.value % writingTips.length]);

const currentStepIndex = computed(() => {
  if (status.value === "completed") return 4;
  const msg = progressMessage.value || "";
  if (msg.includes("Step 2") || msg.includes("升格")) return 2;
  if (msg.includes("Step 1") || msg.includes("采分点")) return 1;
  return Math.min(2, Math.floor(tickCount.value / 3));
});

const hitStats = computed(() => {
  const list = report.value?.shenlun_detail?.point_matches || [];
  const total = list.length;
  const hit = list.filter((m: any) => m.status === "hit").length;
  const partial = list.filter((m: any) => m.status === "partial").length;
  const percent = total > 0 ? Math.round(((hit + partial * 0.5) / total) * 100) : 0;
  return { total, hit, partial, percent };
});

function getAnnotations(sid: string) {
  return (report.value?.annotations || []).filter((a: any) => a.sentence_id === sid);
}

function hasIssue(sid: string) {
  return getAnnotations(sid).some((a: any) => a.severity !== "positive");
}

const visibleSentences = computed(() => {
  const all = report.value?.sentences || [];
  if (!onlyIssues.value) return all;
  return all.filter((s: any) => getAnnotations(s.sentence_id).length > 0);
});

function copyUpgraded() {
  if (!report.value?.upgraded_answer) return;
  uni.setClipboardData({
    data: report.value.upgraded_answer,
    success: () => {
      uni.showToast({ title: "升格范文已复制，快去背诵吧", icon: "none" });
    },
  });
}

async function pollTask() {
  tickCount.value += 1;
  const res = await request<any>({ url: `/api/grading/tasks/${encodeURIComponent(taskId.value)}` });
  status.value = res.status;
  progressMessage.value = res.progress_message || "";
  errorMessage.value = res.error_message || "";
  if (res.status === "completed") {
    report.value = res.report;
    if (timer) clearInterval(timer);
  } else if (res.status === "failed") {
    if (timer) clearInterval(timer);
  }
}

onLoad((opts: any) => {
  taskId.value = decodeURIComponent(opts?.taskId || "");
  if (taskId.value) {
    pollTask();
    timer = setInterval(pollTask, 2000);
  }
});

onUnload(() => {
  if (timer) clearInterval(timer);
});
</script>

<style scoped>
.page {
  padding: 20rpx 24rpx 60rpx;
}
.loading-card {
  background: #fff;
  border-radius: 18rpx;
  padding: 48rpx 32rpx;
  margin-top: 32rpx;
  box-shadow: 0 4rpx 18rpx rgba(0, 0, 0, 0.05);
}
.spinner-title {
  font-size: 34rpx;
  font-weight: 700;
  color: #1e3a8a;
  text-align: center;
}
.progress-msg {
  margin-top: 14rpx;
  color: #2563eb;
  font-size: 25rpx;
  text-align: center;
}
.step-list {
  margin-top: 36rpx;
  padding: 20rpx 24rpx;
  background: #f8fafc;
  border-radius: 14rpx;
}
.step-item {
  display: flex;
  align-items: center;
  padding: 12rpx 0;
  color: #9ca3af;
  font-size: 26rpx;
}
.step-item.done {
  color: #16a34a;
  font-weight: 600;
}
.step-item.active {
  color: #2563eb;
  font-weight: 700;
}
.step-icon {
  width: 40rpx;
  font-size: 28rpx;
}
.tip-box {
  margin-top: 28rpx;
  padding: 18rpx 20rpx;
  background: #eff6ff;
  border-radius: 12rpx;
  font-size: 24rpx;
  color: #1e40af;
  line-height: 1.55;
}
.err-msg {
  margin-top: 20rpx;
  color: #dc2626;
  font-size: 24rpx;
  text-align: center;
}
.hero {
  background: linear-gradient(135deg, #1e3a8a, #2563eb);
  color: #fff;
  border-radius: 18rpx;
  padding: 28rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.hero-left {
  flex: 1;
  padding-right: 16rpx;
}
.hero-sub {
  font-size: 22rpx;
  opacity: 0.85;
}
.hero-title {
  font-size: 30rpx;
  font-weight: 700;
  margin: 8rpx 0;
}
.hero-meta {
  font-size: 22rpx;
  opacity: 0.9;
}
.hero-right {
  text-align: right;
}
.score-num {
  font-size: 56rpx;
  font-weight: 800;
  line-height: 1;
}
.score-full {
  font-size: 26rpx;
  font-weight: 400;
}
.band {
  font-size: 22rpx;
  margin-top: 8rpx;
}
.warn-box {
  background: #fff7ed;
  border: 1rpx solid #fdba74;
  color: #c2410c;
  padding: 16rpx 20rpx;
  border-radius: 12rpx;
  margin-top: 16rpx;
  font-size: 24rpx;
}
.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-top: 20rpx;
}
.card-h-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16rpx;
}
.card-h {
  font-size: 30rpx;
  font-weight: 700;
  border-left: 8rpx solid #2563eb;
  padding-left: 14rpx;
}
.hit-summary {
  font-size: 23rpx;
  color: #2563eb;
  font-weight: 600;
}
.meter-wrap {
  display: flex;
  align-items: center;
  gap: 14rpx;
  margin-bottom: 16rpx;
}
.meter-bar {
  flex: 1;
  height: 16rpx;
  background: #e5e7eb;
  border-radius: 99rpx;
  overflow: hidden;
}
.meter-fill {
  height: 100%;
  background: linear-gradient(90deg, #2563eb, #16a34a);
  border-radius: 99rpx;
}
.meter-pct {
  font-size: 24rpx;
  font-weight: 700;
  color: #16a34a;
}
.filter-toggle {
  font-size: 23rpx;
  color: #2563eb;
  background: #eff6ff;
  padding: 6rpx 16rpx;
  border-radius: 99rpx;
}
.copy-btn {
  background: #eff6ff;
  color: #1d4ed8;
  border: 1rpx solid #93c5fd;
  margin: 0;
  line-height: 1.8;
}
.point-row {
  padding: 14rpx 0;
  border-bottom: 1rpx solid #f3f4f6;
}
.point-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.pid {
  font-weight: 700;
  font-size: 26rpx;
}
.badge {
  font-size: 22rpx;
  padding: 4rpx 14rpx;
  border-radius: 99rpx;
}
.badge.hit {
  background: #dcfce7;
  color: #166534;
}
.badge.partial {
  background: #fef3c7;
  color: #92400e;
}
.badge.miss {
  background: #fee2e2;
  color: #991b1b;
}
.quote-box {
  margin-top: 8rpx;
  padding: 8rpx 12rpx;
  background: #f0fdf4;
  border-left: 4rpx solid #22c55e;
  font-size: 23rpx;
  color: #166534;
  border-radius: 6rpx;
}
.point-comment {
  font-size: 24rpx;
  color: #4b5563;
  margin-top: 8rpx;
  line-height: 1.5;
}
.sent-box {
  background: #f9fafb;
  padding: 16rpx;
  border-radius: 10rpx;
  margin-bottom: 14rpx;
  line-height: 1.65;
}
.sent-red {
  background: #fff5f5;
  border-left: 6rpx solid #ef4444;
}
.sid {
  font-size: 22rpx;
  font-weight: 700;
  color: #6b7280;
  margin-right: 10rpx;
}
.ann-note {
  margin-top: 10rpx;
  padding: 12rpx;
  background: #fff;
  border: 1rpx dashed #fca5a5;
  border-radius: 8rpx;
  font-size: 24rpx;
}
.ann-tag {
  background: #ef4444;
  color: #fff;
  font-size: 20rpx;
  padding: 2rpx 10rpx;
  border-radius: 6rpx;
  margin-right: 10rpx;
}
.ann-tag-good {
  background: #22c55e;
}
.ann-suggest {
  color: #1d4ed8;
  margin-top: 6rpx;
  font-weight: 500;
}
.upgrade-box {
  background: #f0f9ff;
  border: 1rpx solid #bae6fd;
  padding: 20rpx;
  border-radius: 12rpx;
  line-height: 1.8;
  white-space: pre-wrap;
  font-size: 27rpx;
}
.imp-title {
  font-weight: 700;
  margin: 18rpx 0 10rpx;
  font-size: 26rpx;
}
.imp-item {
  font-size: 25rpx;
  color: #374151;
  line-height: 1.65;
  margin-bottom: 6rpx;
}
</style>
