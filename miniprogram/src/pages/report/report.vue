<template>
  <view class="page">
    <view v-if="status !== 'completed'" class="loading-card">
      <view class="spinner-title">{{ status === "failed" ? "这次批改未完成" : status === "pending" ? "答卷已提交" : "正在批改答卷" }}</view>
      <view v-if="status !== 'failed'" class="progress-msg">{{ stageText }}</view>
      <view v-if="status !== 'failed'" class="tip-box">可以先离开，稍后在「批改记录」查看结果。</view>
      <view v-if="errorMessage" class="err-msg">{{ errorMessage }}</view>
    </view>

    <!-- 完整红笔报告 -->
    <view v-else-if="report">
      <view class="hero">
        <view class="hero-left">
          <view class="hero-sub">练习报告 · AI 批改</view>
          <view class="hero-title">{{ report.question_title }}</view>
        </view>
        <view class="hero-right">
          <view class="score-num">{{ report.final_score }}<text class="score-full">/{{ report.full_score }}</text></view>
          <view class="hero-detail">
            <view class="band">{{ report.band_label }}</view>
            <view class="hero-meta">本次作答 {{ report.word_count }} {{ englishReport ? "词" : "字" }}</view>
          </view>
        </view>
      </view>

      <view class="card advice-card">
        <view class="advice-label">下一步怎么改</view>
        <view class="advice-title">{{ advice.title }}</view>
        <view v-if="advice.cue" class="advice-cue">{{ advice.cue }}</view>
        <view class="advice-text">{{ advice.text }}</view>
        <view class="advice-actions">
          <button v-if="advice.target" class="detail-btn" size="mini" @click="openAdvice">{{ advice.link }}</button>
          <button v-if="report.question_id" class="rewrite-btn" size="mini" @click="rewrite">重写这道题</button>
        </view>
      </view>

      <view v-if="wordWarning" class="warn-box">
        {{ wordWarning }}
      </view>

      <!-- 申论采分点明细 + 命中率可视化条 -->
      <view v-if="report.shenlun_detail" class="card">
        <view class="card-h-row">
          <view class="card-h">采分点</view>
          <text class="hit-summary">命中 {{ hitStats.hit }} / {{ hitStats.total }}（部分 {{ hitStats.partial }}）</text>
        </view>

        <view v-if="hitStats.total > 0" class="meter-wrap">
          <view class="meter-bar">
            <view class="meter-fill" :style="{ width: hitStats.percent + '%' }" />
          </view>
          <text class="meter-pct">{{ hitStats.percent }}%</text>
        </view>

        <view v-for="(m, idx) in report.shenlun_detail.point_matches" :id="'point-' + idx" :key="m.point_id" class="point-row">
          <view class="point-head">
            <text class="pid">{{ m.point_id }} {{ m.keyword }}</text>
            <text :class="['badge', m.status]">{{ statusLabel[m.status] || m.status }}</text>
          </view>
          <view v-if="m.status !== 'miss' && m.evidence_quote" class="quote-box">
            作答原文：{{ m.evidence_quote }}
          </view>
          <view v-if="m.material_quote" class="material-cue">{{ m.material_section || "材料原文" }}：{{ m.material_quote }}</view>
          <view class="point-comment">{{ m.comment }}</view>
        </view>
      </view>

      <!-- 大作文 / 考研英语维度定档 -->
      <view v-if="report.shenlun_essay_detail || report.kaoyan_detail" class="card">
        <view class="card-h">分项评分</view>
        <view
          v-for="(d, idx) in (report.shenlun_essay_detail || report.kaoyan_detail).dimensions"
          :id="'dimension-' + idx"
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
          <view class="card-h">逐句批注</view>
          <view class="filter-toggle" @click="onlyIssues = !onlyIssues">
            {{ onlyIssues ? "显示全部句子" : "只看批注句" }}
          </view>
        </view>
        <view
          v-for="s in visibleSentences"
          :id="'sentence-' + s.sentence_id"
          :key="s.sentence_id"
          :class="['sent-box', hasIssue(s.sentence_id) ? 'sent-red' : '']"
        >
          <view class="sent-text">
            <text class="sid">{{ s.sentence_id }}</text>{{ s.text }}
          </view>
          <view v-for="(ann, i) in getAnnotations(s.sentence_id)" :key="i" class="ann-note">
            <text :class="['ann-tag', ann.severity === 'positive' ? 'ann-tag-good' : '']">
              {{ englishReport && ann.issue_type === 'redundancy' ? '表达冗长' : issueLabel[ann.issue_type] || ann.issue_type }}
            </text>
            <text>{{ ann.comment }}</text>
            <view class="ann-suggest">建议改写：{{ ann.suggestion }}</view>
          </view>
        </view>
      </view>

      <!-- 同思路升格范文（带一键复制） -->
      <view id="upgrade" class="card">
        <view class="card-h-row">
          <view class="card-h">参考改写</view>
          <button class="copy-btn" size="mini" @click="copyUpgraded">复制全文</button>
        </view>
        <view class="upgrade-box">{{ report.upgraded_answer }}</view>
        <view class="imp-title">改写说明</view>
        <view v-for="(imp, idx) in report.key_improvements" :key="idx" class="imp-item">
          • {{ imp }}
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from "vue";
import { onLoad, onUnload } from "@dcloudio/uni-app";
import { request } from "@/utils/request";
import { formatReportWarning, selectReportAdvice } from "@/utils/reportAdvice";

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
const onlyIssues = ref(false);
let timer: any = null;

const advice = computed(() => selectReportAdvice(report.value || {}));
const englishReport = computed(() => report.value?.exam_type === "kaoyan_english");
const wordWarning = computed(() => formatReportWarning(report.value?.word_count_warning, englishReport.value));

async function openAdvice() {
  const target = advice.value.target;
  if (!target) return;
  if (target.startsWith("sentence-") && onlyIssues.value) {
    onlyIssues.value = false;
    await nextTick();
  }
  uni.pageScrollTo({ selector: `#${target}`, duration: 250 });
}

function rewrite() {
  const qid = encodeURIComponent(report.value.question_id);
  const fromTask = encodeURIComponent(taskId.value);
  uni.navigateTo({ url: `/pages/submit/submit?qid=${qid}&fromTask=${fromTask}` });
}

const stageText = computed(() => {
  if (status.value === "pending") return "等待开始批改。";
  if (progressMessage.value.includes("Step 0")) return "正在整理材料和采分点。";
  return "正在核对作答并整理批注。";
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
      uni.showToast({ title: "已复制参考改写", icon: "none" });
    },
  });
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
.page { padding: 32rpx 36rpx 68rpx; overflow-wrap: anywhere; }
.hero { padding: 10rpx 0 24rpx; border-bottom: 3rpx solid var(--ink); }
.hero-left { min-width: 0; }
.hero-title, .score-num, .card-h, .spinner-title { font-family: var(--display); }
.hero-title { font-size: 39rpx; line-height: 1.4; font-weight: 700; margin: 10rpx 0; }
.hero-meta, .hero-sub, .band, .hit-summary, .sid, .meter-pct { color: var(--muted); font-size: 24rpx; }
.hero-right { display: flex; align-items: center; flex-wrap: wrap; gap: 20rpx; margin-top: 18rpx; }
.hero-detail { border-left: 1rpx solid var(--rule); padding-left: 18rpx; }
.score-num { color: var(--mark); font-size: 68rpx; line-height: 1.1; }
.score-full { font-family: sans-serif; font-size: 25rpx; color: var(--muted); }
.card { padding: 32rpx 0; border-bottom: 1rpx solid var(--rule); }
.card-h-row, .point-head, .meter-wrap, .advice-actions { display: flex; align-items: center; justify-content: space-between; gap: 14rpx; flex-wrap: wrap; }
.card-h { font-weight: 700; font-size: 35rpx; }
.advice-card { margin-top: 22rpx; background: #f0eee6; padding: 26rpx; border-bottom: 0; }
.advice-label { color: var(--mark); font-size: 25rpx; font-weight: 600; }
.advice-title { margin: 8rpx 0; font-size: 33rpx; font-weight: 700; }
.advice-text, .point-comment, .imp-item { font-size: 28rpx; line-height: 1.7; }
.advice-actions { justify-content: flex-start; margin-top: 22rpx; }
.advice-actions button, .copy-btn, .filter-toggle { margin: 0; font-size: 25rpx; line-height: 2; border-radius: 4rpx; }
.advice-actions button { padding: 8rpx 20rpx; }
.detail-btn, .copy-btn, .filter-toggle { background: transparent; color: var(--action); text-decoration: underline; text-underline-offset: 5rpx; }
.detail-btn::after, .copy-btn::after { border: 0; }
.rewrite-btn { background: var(--action); color: white; }
.meter-wrap { margin: 14rpx 0; }
.meter-bar { flex: 1; height: 5rpx; background: var(--rule); }
.meter-fill { height: 100%; background: var(--action); }
.point-row, .sent-box { padding: 20rpx 0; border-bottom: 1rpx solid var(--rule); }
.point-row:last-child, .sent-box:last-child { border: 0; padding-bottom: 0; }
.pid { font-weight: 600; }
.badge { font-size: 23rpx; color: var(--muted); }
.badge.partial, .badge.miss, .warn-box, .err-msg { color: var(--mark); }
.quote-box, .material-cue, .advice-cue { font-size: 26rpx; line-height: 1.75; margin: 12rpx 0; padding: 0 0 0 16rpx; border-left: 3rpx solid var(--rule); color: var(--muted); }
.point-comment { margin-top: 8rpx; }
.sent-text, .upgrade-box { font-size: 30rpx; line-height: 1.85; }
.sid { margin-right: 12rpx; }
.ann-note { padding-left: 16rpx; border-left: 3rpx solid var(--rule); margin-top: 14rpx; font-size: 26rpx; }
.sent-red .ann-note { border-color: #c59888; }
.ann-tag { color: var(--mark); font-weight: 600; margin-right: 12rpx; }
.ann-tag-good, .ann-suggest { color: var(--action); }
.ann-suggest { margin-top: 6rpx; }
.upgrade-box { white-space: pre-wrap; margin-top: 16rpx; }
.imp-title { font-weight: 600; margin: 22rpx 0 8rpx; }
.loading-card { padding: 54rpx 0 30rpx; border-bottom: 2rpx solid var(--rule); }
.spinner-title { font-size: 44rpx; font-weight: 700; }
.progress-msg, .tip-box, .warn-box, .err-msg { margin-top: 16rpx; font-size: 27rpx; }
.tip-box { color: var(--muted); }
</style>
