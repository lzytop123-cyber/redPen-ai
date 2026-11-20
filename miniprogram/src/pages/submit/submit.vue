<template>
  <view class="page">
    <view v-if="!ready" class="card">
      <view class="q-prompt">{{ loadError || "正在打开作答页…" }}</view>
      <button v-if="loadError" class="text-btn" @click="loadEditor">重新加载</button>
    </view>
    <template v-else>
      <view v-if="question" class="card">
        <view class="q-title">{{ question.title }}</view>
        <view class="q-prompt">{{ question.prompt }}</view>
        <QuestionFigure :question-id="qid" />
        <view class="q-actions">
          <button v-if="materialSections.length" class="text-btn inline-btn" @click="openReader">查看给定材料</button>
          <button class="pdf-btn" size="mini" :loading="pdfLoading" @click="downloadQuestionPdf">
            📄 下载/打印原题 PDF
          </button>
        </view>
      </view>

      <view v-if="isCustomMode" class="card">
        <view class="section-title">批改题型</view>
        <view class="type-row">
          <button v-for="t in examTypes" :key="t.value"
            :class="['type-pill', { active: customExamType === t.value }]"
            :disabled="busy" @click="switchType(t.value)">{{ t.label }}</button>
        </view>
        <view class="section-header custom-label">
          <text class="section-title">题目要求</text>
          <button class="ocr-btn" size="mini" :disabled="busy" :loading="promptOcrLoading" @click="ocrToPrompt">拍照识题</button>
        </view>
        <textarea v-model="customPrompt" class="prompt-input" maxlength="1000" :disabled="submissionLocked" placeholder="输入题目要求，或拍照识别题干" />
        <button class="text-btn" @click="showCustomMaterial = !showCustomMaterial">
          {{ showCustomMaterial ? "收起参考材料" : "补充材料或参考答案（选填）" }}
        </button>
        <textarea v-if="showCustomMaterial" v-model="customMaterial" class="prompt-input" maxlength="3000" :disabled="submissionLocked" placeholder="粘贴给定材料或参考答案" />
      </view>

      <view v-if="sourceTask" class="card">
        <view class="section-header">
          <text class="section-title">上次作答</text>
          <button class="text-btn inline-btn" @click="showOriginal = !showOriginal">{{ showOriginal ? "收起原文" : "展开原文" }}</button>
        </view>
        <view v-if="showOriginal" class="q-prompt original-text">{{ originalAnswer }}</view>
      </view>

      <view id="answer-card" class="card">
        <view class="section-header">
          <text class="section-title">{{ sourceTask ? "我的重写稿" : "我的作答" }}</text>
          <button v-if="materialSections.length" class="ocr-btn" size="mini" @click="openReader">查阅材料</button>
        </view>

        <!-- 默认态：拍照优先大卡片（贴合纸质手写后拍照上传的主流场景） -->
        <view v-if="!showTextEditor" class="camera-hero">
          <view class="camera-box" @click="chooseAndOcr">
            <view class="camera-icon">📷</view>
            <view class="camera-title">{{ ocrLoading ? "正在识别手写答卷…" : "拍照 / 上传手写答卷" }}</view>
            <view class="camera-desc">纸质方格纸写完直接拍，支持连拍 1～4 页自动识字</view>
          </view>
          <button class="switch-text-btn" @click="manualInputExpanded = true">
            已有电子稿？点此直接粘贴或手动输入 ›
          </button>
        </view>

        <!-- 校对态 / 手动输入态 -->
        <template v-else>
          <view class="answer-tools">
            <button class="ocr-btn" size="mini" :disabled="busy" :loading="ocrLoading" @click="chooseAndOcr">
              📷 {{ previewImages.length ? "继续加拍一页" : "拍照录入手写稿" }}
            </button>
            <text class="tip">最多 4 页，点缩略图可放大核对错字</text>
          </view>
          <view v-if="previewImages.length" class="thumb-row">
            <view v-for="(img, idx) in previewImages" :key="img" class="thumb-item">
              <image :src="img" mode="aspectFill" class="thumb-img" @click="previewPhoto(idx)" />
              <text class="thumb-del" @click="removePhoto(idx)">×</text>
            </view>
          </view>
          <textarea v-if="!showMaterial" v-model="answerText" class="answer-input" maxlength="4000" :cursor="answerCursor"
            :disabled="submissionLocked" @blur="rememberCursor" placeholder="在这里核对识别文字，或粘贴你的作答" />
          <view v-else class="answer-input" />
          <view class="word-bar">
            <text :class="{ 'word-warn': wordWarnTag }">{{ currentWordCount }} {{ countUnit }}{{ wordWarnTag }}</text>
            <text v-if="wordRequirement">要求：{{ wordRequirement }}</text>
          </view>
          <view v-if="draftStatus" class="draft-status">{{ draftStatus }}</view>
        </template>
      </view>

      <view v-if="!showMaterial" class="footer-bar">
        <button v-if="submittedTask" class="submit-btn" type="primary" @click="openReport">查看批改进度</button>
        <button v-else class="submit-btn" type="primary" :disabled="busy" :loading="submitting" @click="handleSubmit">
          {{ sourceTask ? "提交重写稿" : "提交批改" }}
        </button>
      </view>

      <view v-if="showMaterial" class="reader">
        <view class="reader-head">
          <text class="section-title">给定材料</text>
          <view class="reader-actions">
            <button v-if="question" class="pdf-btn" size="mini" :loading="pdfLoading" @click="downloadQuestionPdf">📄 下载 PDF</button>
            <button class="ocr-btn" size="mini" @click="closeReader">返回作答</button>
          </view>
        </view>
        <scroll-view v-if="materialSections.length > 1" scroll-x class="mat-tabs" :scroll-into-view="'tab-' + activeMatIndex">
          <view class="mat-tab-list">
            <button v-for="(sec, idx) in materialSections" :key="idx" :id="'tab-' + idx"
              :class="['mat-tab', { 'mat-tab-active': activeMatIndex === idx }]"
              @click="selectSection(idx)">{{ sec.label }}</button>
          </view>
        </scroll-view>
        <template v-for="(sec, idx) in materialSections" :key="idx">
          <scroll-view v-if="idx === activeMatIndex" scroll-y class="reader-body"
            :scroll-top="readerTop" @scroll="rememberScroll(idx, $event)">
            <view class="reader-text">{{ sec.content }}</view>
          </scroll-view>
        </template>
      </view>
    </template>
  </view>
</template>

<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";
import { onHide, onLoad, onUnload } from "@dcloudio/uni-app";
import QuestionFigure from "@/components/QuestionFigure.vue";
import { draftKey, readDraft } from "@/utils/drafts";
import { API_BASE_URL, ensureLogin, request, uploadHandwriting } from "@/utils/request";
import { formatWordLimits } from "@/utils/wordLimits";

const examTypes = [
  { label: "申论小题", value: "shenlun_short" },
  { label: "申论大作文", value: "shenlun_essay" },
  { label: "考研英语", value: "kaoyan_english" },
];

interface Question {
  question_id: string;
  exam_type: string;
  title: string;
  prompt: string;
  material_summary: string;
  min_words: number;
  max_words: number;
  word_requirement?: string;
}

const isCustomMode = ref(false);
const qid = ref("");
const sourceTask = ref("");
const question = ref<Question | null>(null);
const originalAnswer = ref("");
const showOriginal = ref(false);
const ready = ref(false);
const loadError = ref("");
const showMaterial = ref(false);
const activeMatIndex = ref(0);
const readerTop = ref(0);
let scrollOffsets: Record<number, number> = {};

const customExamType = ref("shenlun_essay");
const customPrompt = ref("");
const customMaterial = ref("");
const showCustomMaterial = ref(false);
const promptOcrLoading = ref(false);
const answerText = ref("");
const answerCursor = ref(-1);
const imagePath = ref<string | null>(null);
const previewImages = ref<string[]>([]);
const ocrLoading = ref(false);
const pdfLoading = ref(false);
const manualInputExpanded = ref(false);
const submitting = ref(false);
const submittedTask = ref("");
const submissionLocked = computed(() => submitting.value || Boolean(submittedTask.value));
const busy = computed(() => submissionLocked.value || ocrLoading.value || promptOcrLoading.value);
const showTextEditor = computed(
  () => manualInputExpanded.value || Boolean(answerText.value.trim()) || previewImages.value.length > 0
);

const draftStatus = ref("");
const storageKey = computed(() => draftKey(qid.value, customExamType.value, sourceTask.value));
let dirty = false;
let saveTimer: ReturnType<typeof setTimeout> | undefined;
let unloaded = false;

const activeExamType = computed(() =>
  isCustomMode.value ? customExamType.value : question.value?.exam_type
);
const countUnit = computed(() => activeExamType.value === "kaoyan_english" ? "词" : "字");
const wordRequirement = computed(() => {
  const q = question.value;
  if (!q) return "";
  return q.word_requirement ?? formatWordLimits(q.min_words, q.max_words, q.exam_type);
});
const currentWordCount = computed(() => {
  if (countUnit.value === "词") {
    return (answerText.value.match(/[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*/g) || []).length;
  }
  return Array.from(answerText.value.replace(/\s+/g, "")).length;
});
const wordWarnTag = computed(() => {
  const q = question.value;
  const count = currentWordCount.value;
  if (!q || !count) return "";
  if (q.max_words && count > q.max_words) {
    return q.word_requirement?.includes("约") ? "（偏长）" : `（超出 ${count - q.max_words} ${countUnit.value}）`;
  }
  if (q.min_words && count < q.min_words) {
    return q.word_requirement?.includes("约") ? "（偏短）" : `（还差 ${q.min_words - count} ${countUnit.value}）`;
  }
  return "";
});

const materialSections = computed(() => {
  const raw = question.value?.material_summary?.trim();
  if (!raw) return [];
  const headings = [...raw.matchAll(/^(?:[ \t　]*)(?:给定)?(?:材料|资料)[ \t　]*[0-9一二三四五六七八九十]+(?=[：:、\s]|$)/gm)];
  if (!headings.length) return [{ label: "全部材料", content: raw }];
  const sections: { label: string; content: string }[] = [];
  headings.forEach((heading, i) => {
    const start = i === 0 ? 0 : heading.index;
    sections.push({ label: heading[0].trim(), content: raw.slice(start, headings[i + 1]?.index).trim() });
  });
  return sections;
});

function rememberScroll(index: number, e: { detail: { scrollTop: number } }) {
  scrollOffsets[index] = e.detail.scrollTop;
}

function selectSection(index: number) {
  activeMatIndex.value = index;
  readerTop.value = scrollOffsets[index] || 0;
}

function openReader() {
  readerTop.value = scrollOffsets[activeMatIndex.value] || 0;
  showMaterial.value = true;
  uni.hideKeyboard();
}

function closeReader() {
  showMaterial.value = false;
  saveReader();
  nextTick(() => uni.pageScrollTo({ selector: "#answer-card", duration: 0 }));
}

function saveReader() {
  if (!qid.value || !materialSections.value.length) return;
  try {
    uni.setStorageSync(`writing:reader:${qid.value}`, { index: activeMatIndex.value, offsets: scrollOffsets });
  } catch {
    // Reading position remains available in this editor.
  }
}

function rememberCursor(e: { detail: { cursor?: number } }) {
  if (typeof e.detail.cursor === "number") answerCursor.value = e.detail.cursor;
}

function flushDraft() {
  clearTimeout(saveTimer);
  if (!dirty || submittedTask.value) return;
  try {
    uni.setStorageSync(storageKey.value, { answer: answerText.value, prompt: customPrompt.value, material: customMaterial.value });
    dirty = false;
    draftStatus.value = "已保存到本机草稿";
  } catch {
    draftStatus.value = "草稿保存失败，请先复制保留作答";
  }
}

watch([answerText, customPrompt, customMaterial], () => {
  if (!ready.value || submittedTask.value || unloaded) return;
  dirty = true;
  draftStatus.value = "正在保存草稿…";
  clearTimeout(saveTimer);
  saveTimer = setTimeout(flushDraft, 350);
}, { flush: "sync" });

function restoreEditor() {
  const saved = readDraft(storageKey.value);
  answerText.value = saved?.answer ?? originalAnswer.value;
  customPrompt.value = saved?.prompt || "";
  customMaterial.value = saved?.material || "";
  showCustomMaterial.value = Boolean(customMaterial.value);
  draftStatus.value = saved ? "已恢复本机草稿" : "";
  answerCursor.value = -1;
  imagePath.value = null;
  previewImages.value = [];
  ready.value = true;
}

function switchType(type: string) {
  if (busy.value || type === customExamType.value) return;
  flushDraft();
  if (dirty) return;
  ready.value = false;
  customExamType.value = type;
  restoreEditor();
}

async function loadEditor() {
  ready.value = false;
  loadError.value = "";
  try {
    if (!isCustomMode.value) {
      question.value = await request<Question>({ url: `/api/questions/${encodeURIComponent(qid.value)}` });
      if (sourceTask.value) {
        await ensureLogin();
        const task = await request<{ status: string; report?: { question_id: string; student_answer: string } }>({
          url: `/api/grading/tasks/${encodeURIComponent(sourceTask.value)}`,
        });
        if (task.status !== "completed" || task.report?.question_id !== qid.value || !task.report.student_answer) {
          throw new Error("无法读取这次批改的作答原文");
        }
        originalAnswer.value = task.report.student_answer;
      }
      const reader = uni.getStorageSync(`writing:reader:${qid.value}`);
      if (reader && materialSections.value[reader.index]) {
        activeMatIndex.value = reader.index;
        scrollOffsets = reader.offsets || {};
      }
    }
    if (!unloaded) restoreEditor();
  } catch (err) {
    loadError.value = err instanceof Error ? err.message : "无法打开作答页，请稍后重试";
  }
}

onLoad((opts) => {
  qid.value = decodeURIComponent(opts?.qid || "");
  sourceTask.value = decodeURIComponent(opts?.fromTask || "");
  isCustomMode.value = opts?.mode === "custom" || !qid.value;
  const selected = examTypes.find(t => t.value === opts?.examType);
  if (isCustomMode.value && selected) customExamType.value = selected.value;
  uni.setNavigationBarTitle({ title: sourceTask.value ? "重写作答" : isCustomMode.value ? "自由批改" : "真题作答" });
  loadEditor();
});

onHide(() => {
  flushDraft();
  if (showMaterial.value) saveReader();
});

onUnload(() => {
  unloaded = true;
  flushDraft();
  if (showMaterial.value) saveReader();
});

function previewPhoto(idx: number) {
  uni.previewImage({ current: previewImages.value[idx], urls: previewImages.value });
}

function removePhoto(idx: number) {
  previewImages.value.splice(idx, 1);
}

function downloadQuestionPdf() {
  if (!qid.value || pdfLoading.value) return;
  const pdfUrl = `${API_BASE_URL}/api/questions/${encodeURIComponent(qid.value)}/pdf`;
  // #ifdef H5
  window.open(pdfUrl, "_blank");
  return;
  // #endif
  pdfLoading.value = true;
  uni.showLoading({ title: "正在生成 A4 试卷 PDF…" });
  uni.downloadFile({
    url: pdfUrl,
    success: (res) => {
      uni.hideLoading();
      if (res.statusCode === 200 && res.tempFilePath) {
        uni.openDocument({
          filePath: res.tempFilePath,
          fileType: "pdf",
          showMenu: true,
          fail: () => {
            uni.showToast({ title: "PDF 打开失败，请重试", icon: "none" });
          },
        });
      } else {
        uni.showToast({ title: "PDF 生成失败，请稍后重试", icon: "none" });
      }
    },
    fail: () => {
      uni.hideLoading();
      uni.showToast({ title: "下载失败，请检查后端连接", icon: "none" });
    },
    complete: () => {
      pdfLoading.value = false;
    },
  });
}

function ocrToPrompt() {
  if (busy.value) return;
  promptOcrLoading.value = true;
  uni.chooseImage({
    count: 1, sizeType: ["compressed"], sourceType: ["camera", "album"],
    success: async (res) => {
      try {
        const ocrRes = await uploadHandwriting(res.tempFilePaths[0], customExamType.value);
        if (!unloaded) customPrompt.value = ocrRes.recognized_text;
      } catch {
        uni.showToast({ title: "题目识别失败，请重试", icon: "none" });
      } finally {
        promptOcrLoading.value = false;
      }
    },
    fail: () => { promptOcrLoading.value = false; },
  });
}

function chooseAndOcr() {
  if (busy.value) return;
  ocrLoading.value = true;
  uni.chooseImage({
    count: 4, sizeType: ["compressed"], sourceType: ["camera", "album"],
    success: async (res) => {
      try {
        const paths = res.tempFilePaths;
        for (let i = 0; i < paths.length; i++) {
          if (unloaded) break;
          uni.showLoading({ title: `正在识别第 ${i + 1}/${paths.length} 页` });
          const ocrRes = await uploadHandwriting(paths[i], activeExamType.value!);
          if (unloaded) break;
          answerText.value += (answerText.value ? "\n" : "") + ocrRes.recognized_text;
          imagePath.value = ocrRes.image_path;
          previewImages.value.push(paths[i]);
        }
      } catch {
        uni.showToast({ title: "本页识别失败，请重新选择照片", icon: "none" });
      } finally {
        uni.hideLoading();
        ocrLoading.value = false;
      }
    },
    fail: () => { ocrLoading.value = false; },
  });
}

function openReport() {
  uni.redirectTo({ url: `/pages/report/report?taskId=${encodeURIComponent(submittedTask.value)}` });
}

async function handleSubmit() {
  if (!ready.value || busy.value || submittedTask.value) return;
  if (isCustomMode.value && customPrompt.value.trim().length < 5) {
    uni.showToast({ title: "请先输入或拍照识别题目要求", icon: "none" });
    return;
  }
  if (answerText.value.trim().length < 15) {
    uni.showToast({ title: "作答内容太短，请继续输入", icon: "none" });
    return;
  }
  flushDraft();
  submitting.value = true;
  try {
    await ensureLogin();
    const data = isCustomMode.value
      ? { exam_type: customExamType.value, custom_prompt: customPrompt.value, custom_material: customMaterial.value }
      : { question_id: qid.value };
    const res = await request<{ task_id: string }>({
      url: isCustomMode.value ? "/api/grading/submit-custom" : "/api/grading/submit",
      method: "POST",
      data: { ...data, student_answer: answerText.value, image_path: imagePath.value },
    });
    submittedTask.value = res.task_id;
    dirty = false;
    clearTimeout(saveTimer);
    try {
      const saved = readDraft(storageKey.value);
      if (!unloaded || (saved?.answer === answerText.value && saved.prompt === customPrompt.value && saved.material === customMaterial.value)) {
        uni.removeStorageSync(storageKey.value);
      }
    } finally {
      draftStatus.value = "作答已提交";
      if (!unloaded) openReport();
    }
  } finally {
    submitting.value = false;
  }
}
</script>

<style scoped>
.page {
  padding: 20rpx 24rpx 180rpx;
}
.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
}
.q-title {
  font-size: 32rpx;
  font-weight: 700;
  margin-bottom: 12rpx;
}
.q-prompt {
  font-size: 26rpx;
  color: #374151;
  line-height: 1.65;
  white-space: pre-wrap;
}
.type-row {
  display: flex;
  gap: 14rpx;
  margin-top: 14rpx;
}
.type-pill {
  flex: 1;
  text-align: center;
  padding: 14rpx 0;
  border-radius: 12rpx;
  background: #f3f4f6;
  color: #4b5563;
  font-size: 25rpx;
}
.type-pill.active {
  background: #2563eb;
  color: #fff;
  font-weight: 600;
}
.prompt-input {
  width: 100%;
  min-height: 150rpx;
  margin-top: 12rpx;
  background: #f9fafb;
  border: 1rpx solid #e5e7eb;
  border-radius: 12rpx;
  padding: 16rpx;
  box-sizing: border-box;
  font-size: 26rpx;
  line-height: 1.6;
}
.mat-tabs {
  white-space: nowrap;
  margin-bottom: 12rpx;
}
.mat-tab-list {
  display: inline-flex;
  gap: 12rpx;
}
.mat-tab {
  display: inline-block;
  padding: 8rpx 20rpx;
  font-size: 23rpx;
  border-radius: 99rpx;
  background: #f3f4f6;
  color: #4b5563;
}
.mat-tab-active {
  background: #2563eb;
  color: #fff;
  font-weight: 600;
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.section-title {
  font-size: 30rpx;
  font-weight: 700;
}
.ocr-btn {
  background: #eff6ff;
  color: #1d4ed8;
  border: 1rpx solid #93c5fd;
  margin: 0;
}
.tip {
  font-size: 22rpx;
  color: #6b7280;
  margin: 10rpx 0 14rpx;
}
.thumb-row {
  display: flex;
  gap: 14rpx;
  margin-bottom: 14rpx;
  flex-wrap: wrap;
}
.thumb-item {
  position: relative;
  width: 112rpx;
  height: 112rpx;
}
.thumb-img {
  width: 100%;
  height: 100%;
  border-radius: 10rpx;
  border: 1rpx solid #e5e7eb;
}
.thumb-del {
  position: absolute;
  top: -10rpx;
  right: -10rpx;
  width: 34rpx;
  height: 34rpx;
  line-height: 32rpx;
  text-align: center;
  background: #ef4444;
  color: #fff;
  border-radius: 99rpx;
  font-size: 22rpx;
}
.answer-input {
  width: 100%;
  min-height: 320rpx;
  background: #f9fafb;
  border: 1rpx solid #e5e7eb;
  border-radius: 12rpx;
  padding: 18rpx;
  box-sizing: border-box;
  font-size: 27rpx;
  line-height: 1.7;
}
.word-bar {
  display: flex;
  justify-content: space-between;
  margin-top: 12rpx;
  font-size: 24rpx;
  color: #6b7280;
}
.word-warn {
  color: #dc2626;
  font-weight: 600;
}
.footer-bar {
  position: fixed;
  left: 0;
  right: 0;
  bottom: 0;
  z-index: 99;
  background: #fff;
  padding: 18rpx 28rpx calc(24rpx + env(safe-area-inset-bottom));
  box-shadow: 0 -4rpx 16rpx rgba(0, 0, 0, 0.08);
}
.submit-btn {
  background: #2563eb;
  border-radius: 999rpx;
  font-size: 30rpx;
  font-weight: 600;
}
.text-btn {
  padding: 8rpx 0;
  margin: 12rpx 0 0;
  text-align: left;
  line-height: 1.7;
  font-size: 26rpx;
  font-weight: 600;
  color: #1d4ed8;
  background: transparent;
}
.text-btn::after, .type-pill::after, .mat-tab::after { border: 0; }
.inline-btn { margin: 0; }
.answer-tools { display: flex; gap: 18rpx; align-items: center; flex-wrap: wrap; margin: 12rpx 0; }
.answer-tools .tip { margin: 0; }
.custom-label, .original-text { margin-top: 20rpx; }
.word-bar { gap: 12rpx; flex-wrap: wrap; }
.draft-status { font-size: 22rpx; margin-top: 12rpx; color: #667085; }
.reader {
  position: fixed;
  inset: 0;
  top: var(--window-top, 0px);
  z-index: 100;
  background: #fff;
  display: flex;
  flex-direction: column;
  padding-bottom: env(safe-area-inset-bottom);
}
.reader-head { padding: 22rpx 26rpx; display: flex; justify-content: space-between; align-items: center; }
.reader-actions { display: flex; gap: 14rpx; align-items: center; }
.q-actions { display: flex; justify-content: space-between; align-items: center; margin-top: 16rpx; gap: 16rpx; }
.pdf-btn {
  background: #f0fdf4;
  color: #15803d;
  border: 1rpx solid #86efac;
  margin: 0;
  font-weight: 600;
}
.camera-hero { margin-top: 18rpx; }
.camera-box {
  background: linear-gradient(180deg, #f8fbff, #eff6ff);
  border: 2rpx dashed #60a5fa;
  border-radius: 16rpx;
  padding: 56rpx 30rpx;
  text-align: center;
}
.camera-icon { font-size: 64rpx; line-height: 1.1; }
.camera-title { font-size: 32rpx; font-weight: 700; color: #1d4ed8; margin-top: 14rpx; }
.camera-desc { font-size: 24rpx; color: #64748b; margin-top: 10rpx; }
.switch-text-btn {
  margin-top: 16rpx;
  background: transparent;
  color: #6b7280;
  font-size: 24rpx;
  line-height: 1.8;
}
.switch-text-btn::after { border: 0; }
.mat-tabs { flex: none; }
.mat-tab-list { padding: 0 26rpx; }
.mat-tab { margin: 0; line-height: 1.8; }
.reader-body { flex: 1; height: 0; min-height: 0; }
.reader-text { white-space: pre-wrap; font-size: 29rpx; line-height: 1.85; padding: 20rpx 30rpx 48rpx; color: #283746; }
</style>
