<template>
  <view class="page">
    <!-- 批改中进度卡片 -->
    <view v-if="status !== 'completed'" class="loading-card">
      <view class="spinner-title">{{ status === "failed" ? "批改失败" : "AI 阅卷组长正在精批..." }}</view>
      <view class="progress-msg">{{ progressMessage }}</view>
      <view v-if="errorMessage" class="err-msg">{{ errorMessage }}</view>
    </view>

    <!-- 完整红笔报告 -->
    <view v-else-if="report">
      <view class="hero">
        <view class="hero-left">
          <view class="hero-sub">AI 阅卷级精批报告</view>
          <view class="hero-title">{{ report.question_title }}</view>
          <view class="hero-meta">字数：{{ report.word_count }}</view>
        </view>
        <view class="hero-right">
          <view class="score-num">{{ report.final_score }}<text class="score-full">/{{ report.full_score }}</text></view>
          <view class="band">{{ report.band_label }}</view>
        </view>
      </view>

      <view v-if="report.word_count_warning" class="warn-box">
        ⚠️ {{ report.word_count_warning }}
      </view>

      <!-- 申论采分点明细 -->
      <view v-if="report.shenlun_detail" class="card">
        <view class="card-h">一、标准采分点核对</view>
        <view v-for="m in report.shenlun_detail.point_matches" :key="m.point_id" class="point-row">
          <view class="point-head">
            <text class="pid">{{ m.point_id }}</text>
            <text :class="['badge', m.status]">{{ statusLabel[m.status] || m.status }}</text>
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

      <!-- 逐句红笔批注 -->
      <view class="card">
        <view class="card-h">二、逐句红笔批注</view>
        <view
          v-for="s in report.sentences"
          :key="s.sentence_id"
          :class="['sent-box', hasIssue(s.sentence_id) ? 'sent-red' : '']"
        >
          <view class="sent-text">
            <text class="sid">{{ s.sentence_id }}</text>{{ s.text }}
          </view>
          <view v-for="(ann, i) in getAnnotations(s.sentence_id)" :key="i" class="ann-note">
            <text class="ann-tag">{{ issueLabel[ann.issue_type] || ann.issue_type }}</text>
            <text>{{ ann.comment }}</text>
            <view class="ann-suggest">建议改写：{{ ann.suggestion }}</view>
          </view>
        </view>
      </view>

      <!-- 同思路升格范文 -->
      <view class="card">
        <view class="card-h">三、同思路高分升格版</view>
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
import { ref } from "vue";
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

const taskId = ref("");
const status = ref("pending");
const progressMessage = ref("正在排队...");
const errorMessage = ref("");
const report = ref<any>(null);
let timer: any = null;

function getAnnotations(sid: string) {
  return (report.value?.annotations || []).filter((a: any) => a.sentence_id === sid);
}

function hasIssue(sid: string) {
  return getAnnotations(sid).some((a: any) => a.severity !== "positive");
}

async function pollTask() {
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
  border-radius: 16rpx;
  padding: 80rpx 36rpx;
  text-align: center;
  margin-top: 60rpx;
}
.spinner-title {
  font-size: 34rpx;
  font-weight: 700;
  color: #1e3a8a;
}
.progress-msg {
  margin-top: 20rpx;
  color: #4b5563;
  font-size: 26rpx;
}
.err-msg {
  margin-top: 16rpx;
  color: #dc2626;
  font-size: 24rpx;
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
.card-h {
  font-size: 30rpx;
  font-weight: 700;
  border-left: 8rpx solid #2563eb;
  padding-left: 14rpx;
  margin-bottom: 18rpx;
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
