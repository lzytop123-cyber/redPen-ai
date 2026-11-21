<template>
  <div class="report-page print-full">
    <div class="report-topbar no-print">
      <button class="btn btn-ghost btn-sm" @click="$emit('back')">← 返回</button>
      <div v-if="status === 'completed' && report" class="top-actions">
        <button
          v-if="report.question_id"
          class="btn btn-outline btn-sm"
          @click="$emit('rewrite', report.question_id, taskId)"
        >
          重写这道题
        </button>
        <button class="btn btn-primary btn-sm" @click="openShareCard">✦ 生成打卡图</button>
        <button class="btn btn-outline btn-sm" @click="printReport">打印 / 导出 PDF</button>
      </div>
    </div>

    <!-- 批改进行中 / 失败态 -->
    <section v-if="status !== 'completed'" class="progress-shell paper-card">
      <h2 aria-live="polite">{{ pollTimeout ? "暂未收到批改结果" : status === "failed" ? "这次批改未完成" : status === "pending" ? "答卷已提交" : "正在批改答卷" }}</h2>
      <p v-if="progressMessage && !pollTimeout" class="prog-msg">{{ progressMessage }}</p>
      <p v-if="status !== 'failed' && !pollTimeout" class="prog-sub">可以先离开，稍后在「批改记录」查看报告。</p>

      <div v-if="status === 'failed'" class="fail-actions">
        <div v-if="pollTimeout" class="fail-note">
          当前任务等待超时，您可以稍后在「批改记录」中查看结果。
        </div>
        <div class="btn-group">
          <button class="btn btn-primary" @click="retryPoll">刷新任务状态</button>
          <button class="btn btn-outline" @click="$emit('back')">返回工作台</button>
        </div>
      </div>
    </section>

    <!-- 完整双栏红笔精批报告 -->
    <template v-else-if="report">
      <!-- 成绩与下一步行动横幅 -->
      <section class="score-hero paper-card">
        <div class="hero-main">
          <div class="hero-eyebrow">练习报告 · AI 批改</div>
          <h1>{{ report.question_title }}</h1>
          <div class="hero-meta">
            <span>本次作答 {{ report.word_count }} {{ englishReport ? "词" : "字" }}</span>
            <span v-if="wordWarning" class="warn-chip">{{ wordWarning }}</span>
          </div>

          <div class="advice-strip">
            <div class="advice-kicker">下一步怎么改</div>
            <div class="advice-body">
              <div class="advice-title">{{ advice.title }}</div>
              <div v-if="advice.cue" class="advice-cue">{{ advice.cue }}</div>
              <div class="advice-desc">{{ advice.text }}</div>
            </div>
            <button
              v-if="advice.target"
              class="btn btn-outline btn-sm no-print"
              @click="scrollToTarget(advice.target)"
            >
              {{ advice.link }}
            </button>
          </div>
        </div>

        <div class="hero-score-panel">
          <div class="score-big">
            {{ report.final_score }}<span class="score-full">/{{ report.full_score }}</span>
          </div>
          <div class="band-pill">{{ report.band_label }}</div>
        </div>
      </section>

      <!-- 双栏主体：左栏采分点+红笔批注，右栏吸顶升格范文 -->
      <div class="report-columns">
        <div class="col-left">
          <!-- 一、申论小题标准采分点核对 -->
          <section v-if="report.shenlun_detail" class="paper-card section-card">
            <div class="sec-head">
              <h2>采分点</h2>
              <span class="hit-stat">
                命中 <strong>{{ hitStats.hit }}</strong> / {{ hitStats.total }}
                <template v-if="hitStats.partial > 0">（部分命中 {{ hitStats.partial }}）</template>
              </span>
            </div>

            <div v-if="hitStats.total > 0" class="meter-row">
              <div class="meter-track">
                <div class="meter-fill" :style="{ width: `${hitStats.percent}%` }"></div>
              </div>
              <span class="meter-pct">{{ hitStats.percent }}%</span>
            </div>

            <div class="point-list">
              <div
                v-for="(m, idx) in report.shenlun_detail.point_matches"
                :id="`point-${idx}`"
                :key="m.point_id"
                class="point-item"
              >
                <div class="point-top">
                  <span class="point-name">{{ m.point_id }} · {{ m.keyword }}</span>
                  <span :class="['status-badge', m.status]">
                    {{ statusLabel[m.status] || m.status }}
                  </span>
                </div>
                <div v-if="m.status !== 'miss' && m.evidence_quote" class="quote-line answer">
                  <strong>作答原文：</strong>{{ m.evidence_quote }}
                </div>
                <div v-if="m.material_quote" class="quote-line material">
                  <strong>{{ m.material_section || "材料溯源" }}：</strong>{{ m.material_quote }}
                </div>
                <p class="point-comment">{{ m.comment }}</p>
              </div>
            </div>
          </section>

          <!-- 一、大作文 / 考研英语维度定档 -->
          <section v-if="dimensions.length" class="paper-card section-card">
            <div class="sec-head">
              <h2>分项评分</h2>
            </div>
            <div class="dim-grid">
              <div
                v-for="(d, idx) in dimensions"
                :id="`dimension-${idx}`"
                :key="d.dimension"
                class="dim-item"
              >
                <div class="point-top">
                  <span class="point-name">{{ d.dimension }}</span>
                  <span class="status-badge hit">第 {{ d.level }} 档 / 5 档</span>
                </div>
                <p class="point-comment">{{ d.comment }}</p>
              </div>
            </div>
          </section>

          <!-- 二、逐句红笔批注 -->
          <section class="paper-card section-card">
            <div class="sec-head">
              <h2>逐句批注</h2>
              <button class="btn btn-outline btn-sm no-print" @click="onlyIssues = !onlyIssues">
                {{ onlyIssues ? "显示全部句子" : "只看批注句" }}
              </button>
            </div>

            <div class="sentence-list">
              <div
                v-for="s in visibleSentences"
                :id="`sentence-${s.sentence_id}`"
                :key="s.sentence_id"
                :class="['sentence-box', hasIssue(s.sentence_id) ? 'has-issue' : '']"
              >
                <div class="sent-origin">
                  <span class="sent-id">{{ s.sentence_id }}</span>
                  <span>{{ s.text }}</span>
                </div>

                <div
                  v-for="(ann, i) in getAnnotations(s.sentence_id)"
                  :key="i"
                  :class="['ann-card', ann.severity === 'positive' ? 'positive' : 'issue']"
                >
                  <div class="ann-head">
                    <span class="ann-type">
                      {{
                        englishReport && ann.issue_type === "redundancy"
                          ? "表达冗长"
                          : issueLabel[ann.issue_type] || ann.issue_type
                      }}
                    </span>
                    <span class="ann-comment">{{ ann.comment }}</span>
                  </div>
                  <div v-if="ann.suggestion" class="ann-suggest">
                    <strong>建议改写：</strong>{{ ann.suggestion }}
                  </div>
                </div>
              </div>
            </div>
          </section>
        </div>

        <!-- 右栏：同思路高分升格范文（吸顶对照） -->
        <aside class="col-right">
          <div id="upgrade" class="paper-card section-card sticky-panel">
            <div class="sec-head">
              <h2>参考改写</h2>
              <button class="btn btn-outline btn-sm no-print" @click="copyUpgraded">
                复制全文
              </button>
            </div>

            <div class="upgraded-text">{{ report.upgraded_answer }}</div>

            <div v-if="report.key_improvements?.length" class="imp-block">
              <h3>改写说明</h3>
              <ul>
                <li v-for="(imp, idx) in report.key_improvements" :key="idx">{{ imp }}</li>
              </ul>
            </div>

            <div v-if="report.weakness_tags?.length" class="weak-block">
              <h3>下次练习可留意</h3>
              <div class="weak-chips">
                <span v-for="tag in report.weakness_tags" :key="tag" class="weak-chip">
                  # {{ tag }}
                </span>
              </div>
            </div>

            <div class="ai-disclaimer">
              <div class="report-brand-foot">
                <img src="/favicon.svg" alt="知行岛" class="foot-logo" />
                <span>知行岛·自习室 AI 精批工作台</span>
              </div>
              评分和参考改写由 AI 辅助生成，供练习使用。
            </div>
          </div>
        </aside>
      </div>
    </template>
    <!-- 小红书 3:4 打卡成绩卡预览弹窗 -->
    <div v-if="shareCardUrl" class="share-mask no-print" @click.self="shareCardUrl = ''">
      <div class="share-modal paper-card">
        <div class="share-head">
          <span>3:4 宣纸精批打卡卡（适合发小红书 / 朋友圈）</span>
          <button class="btn btn-ghost btn-sm" @click="shareCardUrl = ''">关闭</button>
        </div>
        <div class="share-preview-wrap">
          <img :src="shareCardUrl" alt="精批打卡成绩卡" class="share-preview-img" />
        </div>
        <div class="share-foot">
          <button class="btn btn-primary" @click="downloadShareCard">⬇️ 保存高清 PNG 打卡图</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { apiRequest } from "../api/client";
import { showToast } from "../stores/auth";
import type { GradingReport, TaskStatusResp } from "../types";
import { formatReportWarning, selectReportAdvice } from "../utils/reportAdvice";
import { renderShareCardDataUrl } from "../utils/shareCard";

const props = defineProps<{
  taskId: string;
}>();

defineEmits<{
  (e: "back"): void;
  (e: "rewrite", questionId: string, fromTaskId: string): void;
}>();

const statusLabel: Record<string, string> = {
  hit: "命中",
  partial: "部分命中",
  miss: "未命中",
};

const issueLabel: Record<string, string> = {
  grammar: "语法/拼写",
  expression: "表达规范",
  missing_point: "漏采分点",
  logic: "逻辑问题",
  redundancy: "啰嗦超字",
  highlight: "亮点句",
};

const status = ref("pending");
const progressMessage = ref("等待批改");
const report = ref<GradingReport | null>(null);
const onlyIssues = ref(false);
const tickCount = ref(0);
const pollTimeout = ref(false);

let pollTimer: number | undefined;
let polling = false;
const MAX_POLL_TICKS = 90; // 最多轮询 3 分钟

const englishReport = computed(() => report.value?.exam_type === "kaoyan_english");
const wordWarning = computed(() =>
  formatReportWarning(report.value?.word_count_warning, englishReport.value)
);
const advice = computed(() => selectReportAdvice(report.value || {}));
const dimensions = computed(
  () => (report.value?.shenlun_essay_detail || report.value?.kaoyan_detail)?.dimensions || []
);

const hitStats = computed(() => {
  const list = report.value?.shenlun_detail?.point_matches || [];
  const total = list.length;
  const hit = list.filter((m) => m.status === "hit").length;
  const partial = list.filter((m) => m.status === "partial").length;
  const percent = total > 0 ? Math.round(((hit + partial * 0.5) / total) * 100) : 0;
  return { total, hit, partial, percent };
});

function getAnnotations(sid: string) {
  return (report.value?.annotations || []).filter((a) => a.sentence_id === sid);
}

function hasIssue(sid: string) {
  return getAnnotations(sid).some((a) => a.severity !== "positive");
}

const visibleSentences = computed(() => {
  const all = report.value?.sentences || [];
  if (!onlyIssues.value) return all;
  return all.filter((s) => getAnnotations(s.sentence_id).length > 0);
});

async function scrollToTarget(targetId: string) {
  if (targetId.startsWith("sentence-") && onlyIssues.value) {
    onlyIssues.value = false;
    await nextTick();
  }
  const el = document.getElementById(targetId);
  if (el) {
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("flash-highlight");
    window.setTimeout(() => el.classList.remove("flash-highlight"), 1400);
  }
}

async function copyUpgraded() {
  if (!report.value?.upgraded_answer) return;
  try {
    await navigator.clipboard.writeText(report.value.upgraded_answer);
    showToast("已复制参考改写", "success");
  } catch {
    showToast("复制失败，请手动选中复制", "warn");
  }
}

const shareCardUrl = ref("");

function openShareCard() {
  if (!report.value) return;
  try {
    shareCardUrl.value = renderShareCardDataUrl(report.value);
  } catch {
    showToast("生成打卡图失败，请稍后重试", "error");
  }
}

function downloadShareCard() {
  if (!shareCardUrl.value || !report.value) return;
  const a = document.createElement("a");
  a.href = shareCardUrl.value;
  a.download = `知行岛精批打卡_${report.value.final_score}分.png`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  showToast("打卡图已保存！", "success");
}

function printReport() {
  window.print();
}

function stopPolling() {
  if (pollTimer) {
    window.clearInterval(pollTimer);
    pollTimer = undefined;
  }
}

async function pollOnce() {
  if (polling) return;
  polling = true;
  tickCount.value += 1;

  if (tickCount.value > MAX_POLL_TICKS) {
    stopPolling();
    pollTimeout.value = true;
    status.value = "failed";
    progressMessage.value = "批改耗时较长，请稍后刷新状态或在历史记录中查看";
    polling = false;
    return;
  }

  try {
    const res = await apiRequest<TaskStatusResp>(
      `/api/grading/tasks/${encodeURIComponent(props.taskId)}`
    );
    status.value = res.status;
    progressMessage.value = res.progress_message || "";
    if (res.status === "completed" && res.report) {
      report.value = res.report;
      stopPolling();
    } else if (res.status === "failed") {
      stopPolling();
    }
  } catch {
    // 轮询期间偶发网络抖动静默等待下一拍，避免刷屏弹窗
  } finally {
    polling = false;
  }
}

function startPolling() {
  stopPolling();
  tickCount.value = 0;
  pollTimeout.value = false;
  pollOnce();
  pollTimer = window.setInterval(pollOnce, 2000);
}

function retryPoll() {
  status.value = "running";
  progressMessage.value = "正在重新获取批改状态...";
  startPolling();
}

onMounted(() => {
  startPolling();
});

onBeforeUnmount(() => {
  stopPolling();
});
</script>

<style scoped>
.report-page {
  max-width: 1360px;
  margin: 0 auto;
  padding: 18px 24px 56px;
}

.report-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.top-actions {
  display: flex;
  gap: 10px;
}

/* 进度等待卡片 */
.progress-shell {
  max-width: 680px;
  margin: 48px auto;
  padding: 40px 36px;
  text-align: center;
}

.progress-shell h2 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 22px;
}

.prog-msg {
  margin: 10px 0 24px;
  color: var(--brand);
  font-size: 14px;
  font-weight: 500;
}

.fail-actions {
  margin-top: 20px;
}

.fail-note {
  margin-bottom: 14px;
  font-size: 13px;
  color: var(--ink-muted);
}

.btn-group {
  display: flex;
  justify-content: center;
  gap: 12px;
}

/* 顶部成绩横幅（轻学院红笔阅卷印章感） */
.score-hero {
  display: flex;
  justify-content: space-between;
  align-items: stretch;
  gap: 24px;
  padding: 26px 30px;
  margin-bottom: 18px;
  background: var(--bg-surface);
}

.hero-main {
  flex: 1;
  min-width: 0;
}

.hero-eyebrow {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  font-weight: 700;
  color: var(--brand);
  background: var(--brand-soft);
  padding: 2px 10px;
  border-radius: 99px;
  letter-spacing: 0.6px;
}

.hero-main h1 {
  margin: 8px 0 8px;
  font-family: var(--font-serif);
  font-size: 22px;
  line-height: 1.35;
}

.hero-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 13px;
  color: var(--ink-muted);
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.warn-chip {
  background: var(--warn-amber-soft);
  border: 1px solid var(--warn-amber-border);
  color: var(--warn-amber);
  padding: 2px 10px;
  border-radius: 99px;
  font-weight: 600;
}

.advice-strip {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 13px 16px;
  border-radius: var(--radius-md);
  background: #fdfcf8;
  border: 1px solid var(--border-subtle);
  border-left: 4px solid var(--red-pen);
}

.advice-kicker {
  font-size: 12px;
  font-weight: 700;
  color: var(--red-pen);
  background: var(--red-pen-soft);
  padding: 2px 8px;
  border-radius: 6px;
  white-space: nowrap;
}

.advice-body {
  flex: 1;
  min-width: 0;
}

.advice-title {
  font-weight: 700;
  font-size: 14px;
  color: var(--ink-primary);
}

.advice-cue {
  font-size: 12.5px;
  color: var(--ink-secondary);
  margin-top: 2px;
}

.advice-desc {
  font-size: 13px;
  color: var(--ink-secondary);
  margin-top: 2px;
}

.hero-score-panel {
  width: 204px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border-left: 1px solid var(--border-strong);
  padding: 18px 16px;
}

.score-big {
  font-family: var(--font-serif);
  font-size: 48px;
  font-weight: 900;
  color: var(--brand);
  line-height: 1;
}

.score-full {
  font-size: 18px;
  font-weight: 500;
  color: var(--ink-muted);
  margin-left: 2px;
}

.band-pill {
  margin-top: 10px;
  background: var(--brand);
  color: #fff;
  font-size: 12.5px;
  font-weight: 600;
  padding: 4px 14px;
  border-radius: 99px;
}

/* 双栏报告正文 */
.report-columns {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) minmax(340px, 0.95fr);
  gap: 18px;
  align-items: start;
}

.col-left {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.sticky-panel {
  position: sticky;
  top: calc(var(--nav-height) + 16px);
}

.section-card {
  padding: 22px 24px;
}

.sec-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.sec-head h2 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 17px;
  color: var(--ink-primary);
}

.hit-stat {
  font-size: 13px;
  color: var(--ink-secondary);
}

.meter-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.meter-track {
  flex: 1;
  height: 10px;
  border-radius: 99px;
  background: var(--bg-inset);
  overflow: hidden;
}

.meter-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--brand), var(--hit-green));
  border-radius: 99px;
}

.meter-pct {
  font-weight: 700;
  font-size: 13px;
  color: var(--brand);
}

.point-list,
.dim-grid {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.point-item,
.dim-item {
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  background: var(--bg-subtle);
  transition: box-shadow 0.3s ease;
}

.point-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.point-name {
  font-weight: 700;
  font-size: 14px;
  color: var(--ink-primary);
}

.status-badge {
  font-size: 12px;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 99px;
  flex-shrink: 0;
}

.status-badge.hit {
  background: var(--hit-green-soft);
  color: var(--hit-green);
  border: 1px solid var(--hit-green-border);
}

.status-badge.partial {
  background: var(--warn-amber-soft);
  color: var(--warn-amber);
  border: 1px solid var(--warn-amber-border);
}

.status-badge.miss {
  background: var(--red-pen-soft);
  color: var(--red-pen);
  border: 1px solid var(--red-pen-border);
}

.quote-line {
  font-size: 12.5px;
  padding: 7px 10px;
  border-radius: var(--radius-sm);
  margin-bottom: 6px;
  line-height: 1.6;
}

.quote-line.answer {
  background: #fff;
  border-left: 3px solid var(--brand);
  color: var(--ink-primary);
}

.quote-line.material {
  background: #fffdf5;
  border-left: 3px solid var(--warn-amber);
  color: var(--ink-secondary);
}

.point-comment {
  margin: 4px 0 0;
  font-size: 13.5px;
  color: var(--ink-secondary);
  line-height: 1.65;
}

/* 逐句红笔批注 */
.sentence-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.sentence-box {
  padding: 14px 16px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  background: #fff;
}

.sentence-box.has-issue {
  border-color: var(--red-pen-border);
  background: #fffafa;
}

.sent-origin {
  font-size: 14.5px;
  line-height: 1.75;
  color: var(--ink-primary);
}

.sent-id {
  display: inline-block;
  font-size: 11.5px;
  font-weight: 700;
  color: var(--ink-muted);
  background: var(--bg-inset);
  padding: 0 6px;
  border-radius: 4px;
  margin-right: 8px;
}

.ann-card {
  margin-top: 10px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  line-height: 1.65;
}

.ann-card.issue {
  background: var(--red-pen-soft);
  border-left: 3px solid var(--red-pen);
}

.ann-card.positive {
  background: var(--hit-green-soft);
  border-left: 3px solid var(--hit-green);
}

.ann-head {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.ann-type {
  font-size: 11.5px;
  font-weight: 700;
  padding: 1px 7px;
  border-radius: 4px;
  background: var(--red-pen);
  color: #fff;
  flex-shrink: 0;
}

.ann-card.positive .ann-type {
  background: var(--hit-green);
}

.ann-comment {
  color: var(--ink-primary);
}

.ann-suggest {
  margin-top: 6px;
  color: var(--brand);
}

/* 升格范文右栏 */
.upgraded-text {
  padding: 16px 18px;
  border-radius: var(--radius-md);
  background: #fffdf7;
  border: 1px solid var(--border-subtle);
  font-size: 14.5px;
  line-height: 1.9;
  color: var(--ink-primary);
  white-space: pre-wrap;
}

.imp-block,
.weak-block {
  margin-top: 18px;
}

.imp-block h3,
.weak-block h3 {
  margin: 0 0 8px;
  font-size: 13.5px;
  color: var(--ink-primary);
}

.imp-block ul {
  margin: 0;
  padding-left: 18px;
  font-size: 13px;
  color: var(--ink-secondary);
  line-height: 1.75;
}

.weak-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.weak-chip {
  font-size: 12px;
  font-weight: 600;
  padding: 3px 10px;
  border-radius: 99px;
  background: var(--red-pen-soft);
  color: var(--red-pen);
}

.ai-disclaimer {
  margin-top: 20px;
  padding-top: 14px;
  border-top: 1px solid var(--bg-inset);
  font-size: 11.5px;
  color: var(--ink-muted);
}

.report-brand-foot {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
  font-family: var(--font-serif);
  font-size: 12.5px;
  font-weight: 600;
  color: var(--ink-secondary);
}

.foot-logo {
  height: 16px;
  width: auto;
  opacity: 0.85;
}

.flash-highlight {
  box-shadow: 0 0 0 3px rgba(200, 50, 40, 0.35) !important;
}

@media (max-width: 1024px) {
  .score-hero {
    flex-direction: column;
  }
  .hero-score-panel {
    width: 100%;
    border-left: none;
    border-top: 1px solid var(--border-subtle);
    padding-left: 0;
    padding-top: 16px;
    flex-direction: row;
    gap: 16px;
  }
  .report-columns {
    grid-template-columns: 1fr;
  }
  .sticky-panel {
    position: static;
  }
}
/* 小红书 3:4 打卡成绩卡预览弹窗 */
.share-mask {
  position: fixed;
  inset: 0;
  z-index: 140;
  background: rgba(20, 24, 22, 0.56);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.share-modal {
  width: 100%;
  max-width: 460px;
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  padding: 18px 20px;
  box-shadow: var(--shadow-lg);
}

.share-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 13.5px;
  font-weight: 600;
  color: var(--ink-primary);
  margin-bottom: 12px;
}

.share-preview-wrap {
  flex: 1;
  min-height: 0;
  overflow: auto;
  display: flex;
  justify-content: center;
  background: #f2eee5;
  border-radius: 10px;
  padding: 12px;
}

.share-preview-img {
  max-width: 100%;
  max-height: 66vh;
  border-radius: 6px;
  box-shadow: var(--shadow-md);
  object-fit: contain;
}

.share-foot {
  margin-top: 14px;
  display: flex;
  justify-content: center;
}

@media (max-width: 700px) {
  .report-page { padding: 12px 14px 36px; }
  .report-topbar, .top-actions, .sec-head, .point-top { flex-wrap: wrap; gap: 8px; }
  .score-hero, .section-card { padding: 17px; }
  .advice-strip { flex-direction: column; align-items: flex-start; gap: 8px; }
  .report-columns { grid-template-columns: minmax(0, 1fr); }
  .band-pill { margin: 0; }
}
</style>
