<template>
  <div class="workspace-shell" :class="{ 'focus-mode': focusMode }" @paste="handleGlobalPaste" @keydown.esc="focusMode = false">
    <!-- 顶部面包屑与操作条 -->
    <div class="ws-topbar">
      <div class="ws-topbar-left">
        <button class="btn btn-ghost btn-sm" @click="$emit('back')">← 返回真题库</button>
        <span class="ws-divider"></span>
        <span class="ws-mode-badge">
          {{ fromTaskId ? "重写" : isCustom ? "自选题" : "真题作答" }}
        </span>
      </div>
      <div class="ws-topbar-right">
        <!-- 考场计时器 -->
        <div class="exam-timer" :class="timerStateClass" title="考场限时计时器">
          <span class="timer-clock">{{ formattedTimer }}</span>
          <button type="button" class="timer-btn" @click="toggleTimer">
            {{ timerRunning ? "暂停" : "计时" }}
          </button>
          <button
            v-if="timerElapsed > 0"
            type="button"
            class="timer-btn"
            title="重置计时"
            @click="resetTimer"
          >
            重置
          </button>
        </div>

        <button
          type="button"
          class="btn btn-outline btn-sm focus-toggle-btn"
          @click="focusMode = !focusMode"
        >
          {{ focusMode ? "退出专注" : "专注模式" }}
        </button>

        <a
          v-if="question && !isCustom"
          class="btn btn-outline btn-sm"
          :href="apiUrl(`/api/questions/${encodeURIComponent(question.question_id)}/pdf`)"
          target="_blank"
          rel="noopener"
        >
          原题 PDF
        </a>
        <span v-if="draftStatus" class="draft-pill">{{ draftStatus }}</span>
      </div>
    </div>

    <div v-if="loading" class="ws-loading paper-card">正在加载题目与给定材料...</div>
    <div v-else-if="loadError" class="ws-loading paper-card error">
      <p>{{ loadError }}</p>
      <button class="btn btn-outline btn-sm" @click="loadData">重新加载</button>
    </div>

    <template v-else>
      <div class="pane-switch" role="group" aria-label="切换作答区域">
        <button :aria-pressed="mobilePane === 'material'" @click="mobilePane = 'material'">{{ isCustom ? "题目要求" : "题目与材料" }}</button>
        <button :aria-pressed="mobilePane === 'answer'" @click="mobilePane = 'answer'">我的作答</button>
      </div>
      <div class="split-pane" :data-pane="mobilePane">
      <!-- 左栏：题干与给定材料（或自定义题干配置） -->
      <section class="left-pane paper-card">
        <template v-if="!isCustom && question">
          <div class="pane-head">
            <div>
              <div class="q-meta-tags">
                <span class="meta-tag">{{ question.sub_type || examLabel }}</span>
                <span class="meta-tag neutral">满分 {{ question.full_score }} 分</span>
                <span v-if="wordRequirement" class="meta-tag neutral">{{ wordRequirement }}</span>
              </div>
              <h2 class="q-heading">{{ formatQuestionTitle(question) }}</h2>
            </div>
          </div>

          <div class="prompt-box">
            <div class="box-label">作答要求</div>
            <div class="prompt-text">{{ question.prompt }}</div>
            <div v-if="figureInfo" class="figure-card">
              <div class="figure-head">
                <span>练习示意图 · 依题干绘制</span>
                <button class="btn btn-ghost btn-sm" @click="lightboxUrl = figureInfo.url">放大查看</button>
              </div>
              <img
                :src="figureInfo.url"
                :alt="figureInfo.caption"
                class="figure-img"
                @click="lightboxUrl = figureInfo.url"
              />
              <div class="figure-caption">{{ figureInfo.caption }}</div>
            </div>
          </div>

          <!-- 二刷模式：可展开上次作答原文 -->
          <div v-if="originalAnswer" class="original-card">
            <div class="original-head" @click="showOriginal = !showOriginal">
              <span>上次作答原文（对照修改）</span>
              <span class="toggle-link">{{ showOriginal ? "收起 ▲" : "展开 ▼" }}</span>
            </div>
            <div v-if="showOriginal" class="original-body">{{ originalAnswer }}</div>
          </div>

          <!-- 给定材料沉浸式阅读器 -->
          <div v-if="materialSections.length" class="material-reader">
            <div class="reader-toolbar">
              <div class="mat-tabs">
                <button
                  v-for="(sec, idx) in materialSections"
                  :key="idx"
                  :class="['mat-tab', activeMatIndex === idx ? 'active' : '', sectionHitCounts[idx] > 0 ? 'has-hit' : '']"
                  @click="activeMatIndex = idx"
                >
                  {{ activeExamType === "kaoyan_396" && materialSections.length === 1 ? "原题给定材料" : sec.label }}<span v-if="sectionHitCounts[idx] > 0" class="tab-hit">{{ sectionHitCounts[idx] }}</span>
                </button>
              </div>
              <div class="reader-controls">
                <input
                  v-if="activeExamType !== 'kaoyan_396' || materialSections.length > 1"
                  v-model="materialSearch"
                  type="text"
                  class="mat-search"
                  placeholder="跨全部材料查找关键词，回车跳下一份..."
                  @keyup.enter="jumpNextHitSection"
                />
                <button
                  v-if="totalSearchHits > 0"
                  type="button"
                  class="btn btn-ghost btn-sm"
                  @click="jumpNextHitSection"
                >
                  共 {{ totalSearchHits }} 处 · 下一份
                </button>
                <div class="font-switch" title="调节阅读字号">
                  <button :class="{ active: fontSize === 14 }" @click="fontSize = 14">小</button>
                  <button :class="{ active: fontSize === 15.5 }" @click="fontSize = 15.5">中</button>
                  <button :class="{ active: fontSize === 17.5 }" @click="fontSize = 17.5">大</button>
                </div>
              </div>
            </div>

            <div class="reader-content" :style="{ fontSize: `${fontSize}px` }">
              <p
                v-for="(para, pIdx) in currentMaterialParagraphs"
                :key="pIdx"
                class="mat-para"
                v-html="highlightText(para)"
              ></p>
            </div>
          </div>
        </template>

        <!-- 自由批改模式左栏 -->
        <template v-else>
          <div class="custom-left">
            <h2 class="q-heading">自己的题目</h2>
            <p class="custom-tip">适用于模拟卷、机构押题、随手练笔等不在真题库里的题目。</p>

            <div class="field-block">
              <label class="box-label">1. 选择批改题型</label>
              <div class="type-pills">
                <button
                  v-for="t in examTypes"
                  :key="t.value"
                  :class="['type-pill', customExamType === t.value ? 'active' : '']"
                  @click="switchCustomType(t.value)"
                >
                  {{ t.label }}
                </button>
              </div>
            </div>

            <div class="field-block">
              <div class="label-row">
                <label class="box-label">2. 题目要求（必填）</label>
                <label class="btn btn-outline btn-sm upload-inline">
                  {{ promptOcrLoading ? "识题中..." : "识别题目照片" }}
                  <input
                    type="file"
                    accept="image/*"
                    hidden
                    :disabled="promptOcrLoading"
                    @change="handlePromptOcrUpload"
                  />
                </label>
              </div>
              <textarea
                v-model="customPrompt"
                class="custom-textarea"
                rows="5"
                maxlength="1200"
                placeholder="输入或粘贴题目要求（例如：根据给定资料，概括当前基层治理面临的主要问题，不超过 250 字）"
              ></textarea>
            </div>

            <div class="field-block flex-grow">
              <div class="label-row">
                <label class="box-label">3. 给定材料或参考答案（选填，提供材料后批改更精准）</label>
                <span class="mat-limit-tip">{{ customMaterial.length }} / 15000 字</span>
              </div>
              <textarea
                v-model="customMaterial"
                class="custom-textarea tall"
                maxlength="15000"
                placeholder="可选：粘贴整套给定材料或参考答案（支持最多 15000 字）..."
              ></textarea>
            </div>
          </div>
        </template>
      </section>

      <!-- 右栏：作答编辑器 + 拖拽/粘贴手写照片 OCR -->
      <section
        class="right-pane paper-card"
        :class="{ dragging: isDragging }"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleDropFiles"
      >
        <div class="editor-head">
          <div class="editor-title-group">
            <h3>{{ fromTaskId ? "我的重写稿" : "我的作答" }}</h3>
            <span class="paste-hint">也可以拖入或粘贴答卷照片。</span>
          </div>

          <div class="editor-tools">
            <button
              type="button"
              :class="['btn', 'btn-sm', linedPaper ? 'btn-primary' : 'btn-outline']"
              title="切换宣纸稿纸横线底纹"
              @click="linedPaper = !linedPaper"
            >
              稿纸线
            </button>
            <label class="btn btn-outline btn-sm upload-inline" :class="{ disabled: ocrLoading }">
              {{ ocrLoading ? "手写识别中..." : "上传手写稿（最多 4 页）" }}
              <input
                type="file"
                accept="image/*"
                multiple
                hidden
                :disabled="ocrLoading || submitting"
                @change="handleAnswerImageInput"
              />
            </label>
          </div>
        </div>

        <!-- 已上传的手写照片缩略图条 -->
        <div v-if="previewPhotos.length" class="thumb-bar">
          <div v-for="(p, idx) in previewPhotos" :key="p.url" class="thumb-item">
            <img :src="p.url" class="thumb-img" @click="lightboxUrl = p.url" />
            <span class="thumb-index">第 {{ idx + 1 }} 页</span>
            <button class="thumb-del" @click="removePhoto(idx)" title="移除">×</button>
          </div>
          <span class="thumb-note">点击缩略图可放大核对识别错别字</span>
          <button
            v-if="!answerText.trim() && previewPhotos.some((p) => p.text)"
            type="button"
            class="btn btn-outline btn-sm"
            @click="restoreOcrText"
          >
            恢复识别文字
          </button>
        </div>

        <div class="textarea-wrap">
          <textarea
            v-model="answerText"
            class="answer-editor"
            :class="{ 'lined-paper': linedPaper }"
            maxlength="4500"
            :disabled="submitting"
            placeholder="在这里写答案，或粘贴已有的作答。"
          ></textarea>
          <div v-if="isDragging" class="drop-overlay">
            松开后识别答卷文字
          </div>
        </div>

        <!-- 底部吸底状态与提交栏 -->
        <div class="editor-footer">
          <div class="word-meter">
            <span :class="['wc-num', wordWarnTag ? 'warn' : '']">
              已写 <strong>{{ currentWordCount }}</strong> {{ countUnit }}
              <span v-if="wordWarnTag" class="wc-warn-badge">{{ wordWarnTag }}</span>
            </span>
            <span v-if="wordRequirement" class="wc-req">要求：{{ wordRequirement }}</span>
          </div>

          <div class="submit-actions">
            <span v-if="userState.user && !userState.user.is_vip" class="quota-hint">
              剩余 {{ userState.user.free_quota + userState.user.paid_quota }} 次额度
            </span>
            <button
              class="btn btn-primary btn-lg"
              :disabled="submitting || ocrLoading"
              @click="handleSubmit"
            >
              {{ submitting ? "正在提交…" : fromTaskId ? "提交重写稿" : "提交批改" }}
            </button>
          </div>
        </div>
      </section>
    </div>

    </template>

    <!-- 图片放大灯箱 -->
    <div v-if="lightboxUrl" class="lightbox" @click="lightboxUrl = ''">
      <img :src="lightboxUrl" class="lightbox-img" @click.stop />
      <button class="lightbox-close" @click="lightboxUrl = ''">×</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { apiRequest, apiUrl, uploadOcrImage } from "../api/client";
import practiceFigures from "../data/practice_figures.json";
import { openAccountModal, openAuthModal, refreshUser, showToast, userState } from "../stores/auth";
import type { ExamType, QuestionDetail, TaskStatusResp } from "../types";
import { draftStorageKey, formatWordLimits, readDraft } from "../utils/reportAdvice";
import { formatQuestionTitle } from "../utils/questionFormat";

const props = defineProps<{
  questionId?: string;
  fromTaskId?: string;
  customMode?: boolean;
  initialExamType?: ExamType;
}>();

const emit = defineEmits<{
  (e: "back"): void;
  (e: "submitted", taskId: string): void;
}>();

const examTypes: Array<{ label: string; value: ExamType }> = [
  { label: "申论小题", value: "shenlun_short" },
  { label: "申论大作文", value: "shenlun_essay" },
  { label: "考研英语作文", value: "kaoyan_english" },
  { label: "396经综写作", value: "kaoyan_396" },
];

const isCustom = computed(() => Boolean(props.customMode) || !props.questionId);
const loading = ref(false);
const loadError = ref("");
const question = ref<QuestionDetail | null>(null);
const originalAnswer = ref("");
const showOriginal = ref(false);

const customExamType = ref<ExamType>(props.initialExamType || "shenlun_essay");
const customPrompt = ref("");
const customMaterial = ref("");
const promptOcrLoading = ref(false);

const answerText = ref("");
const imagePath = ref<string | null>(null);
const previewPhotos = ref<Array<{ url: string; text: string }>>([]);
const ocrLoading = ref(false);
const submitting = ref(false);
const isDragging = ref(false);
const lightboxUrl = ref("");

const activeMatIndex = ref(0);
const fontSize = ref(15.5);
const materialSearch = ref("");
const draftStatus = ref("");
const mobilePane = ref<"material" | "answer">("material");
let saveTimer: number | undefined;

const activeExamType = computed<ExamType>(() =>
  isCustom.value ? customExamType.value : question.value?.exam_type || "shenlun_short"
);

const examLabel = computed(
  () => examTypes.find((t) => t.value === activeExamType.value)?.label || "真题"
);

const countUnit = computed(() => (activeExamType.value === "kaoyan_english" ? "词" : "字"));

const customDefaultLimits: Record<ExamType, { min: number; max: number }> = {
  shenlun_short: { min: 120, max: 300 },
  shenlun_essay: { min: 1000, max: 1200 },
  kaoyan_english: { min: 160, max: 220 },
  kaoyan_396: { min: 540, max: 780 },
};

const wordRequirement = computed(() => {
  const q = question.value;
  if (q) return q.word_requirement || formatWordLimits(q.min_words, q.max_words, q.exam_type);
  const def = customDefaultLimits[customExamType.value];
  return `建议 ${formatWordLimits(def.min, def.max, customExamType.value)}`;
});

const currentWordCount = computed(() => {
  if (countUnit.value === "词") {
    return (answerText.value.match(/[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*/g) || []).length;
  }
  return Array.from(answerText.value.replace(/\s+/g, "")).length;
});

const wordWarnTag = computed(() => {
  const count = currentWordCount.value;
  if (!count) return "";
  const q = question.value;
  const minW = q ? q.min_words : customDefaultLimits[customExamType.value].min;
  const maxW = q ? q.max_words : customDefaultLimits[customExamType.value].max;
  const isApprox = Boolean(q?.word_requirement?.includes("约"));
  if (maxW && count > maxW) {
    return isApprox ? "偏长" : `超出 ${count - maxW} ${countUnit.value}`;
  }
  if (minW && count < minW) {
    return isApprox ? "偏短" : `还差 ${minW - count} ${countUnit.value}`;
  }
  return "";
});

const figureCatalog = practiceFigures as Record<string, { caption: string; extension: string }>;
const figureInfo = computed(() => {
  const qid = question.value?.question_id;
  if (!qid || !figureCatalog[qid]) return null;
  const f = figureCatalog[qid];
  return {
    caption: f.caption,
    url: `/figures/${qid}.${f.extension}`,
  };
});

const materialSections = computed(() => {
  const raw = question.value?.material_summary?.trim();
  if (!raw) return [];
  const headings = [
    ...raw.matchAll(/^(?:[ \t　]*)(?:【|\[)?(?:给定)?(?:材料|资料)[ \t　]*[0-9一二三四五六七八九十]+(?:】|\])?(?=[：:、\s]|$)/gm),
  ];
  if (!headings.length) return [{ label: "全部材料", content: raw }];
  const sections: Array<{ label: string; content: string }> = [];
  headings.forEach((h, i) => {
    const start = i === 0 ? 0 : h.index || 0;
    const end = headings[i + 1]?.index;
    const cleanLabel = h[0].trim().replace(/^[【\[]|[】\]]$/g, "");
    sections.push({
      label: cleanLabel,
      content: raw.slice(start, end).trim(),
    });
  });
  return sections;
});

const currentMaterialParagraphs = computed(() => {
  const sec = materialSections.value[activeMatIndex.value];
  if (!sec) return [];
  return sec.content.split(/\n+/).map((s) => s.trim()).filter(Boolean);
});

const sectionHitCounts = computed(() => {
  const kw = materialSearch.value.trim();
  if (!kw) return materialSections.value.map(() => 0);
  const re = new RegExp(kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi");
  return materialSections.value.map((sec) => (sec.content.match(re) || []).length);
});

const totalSearchHits = computed(() =>
  sectionHitCounts.value.reduce((sum, n) => sum + n, 0)
);

function jumpNextHitSection() {
  const counts = sectionHitCounts.value;
  if (!counts.some((n) => n > 0)) return;
  for (let offset = 1; offset <= counts.length; offset++) {
    const idx = (activeMatIndex.value + offset) % counts.length;
    if (counts[idx] > 0) {
      activeMatIndex.value = idx;
      return;
    }
  }
}

watch(materialSearch, () => {
  const counts = sectionHitCounts.value;
  if (counts[activeMatIndex.value] > 0) return;
  const firstHit = counts.findIndex((n) => n > 0);
  if (firstHit >= 0) activeMatIndex.value = firstHit;
});

function detectReferencedMaterialIndex(prompt: string, sections: Array<{ label: string }>): number {
  if (!prompt || sections.length <= 1) return 0;
  const m = prompt.match(/(?:给定)?(?:资料|材料)\s*([0-9一二三四五六七八九十]+)/);
  if (!m) return 0;
  const cnMap: Record<string, number> = {
    一: 1, 二: 2, 三: 3, 四: 4, 五: 5, 六: 6, 七: 7, 八: 8, 九: 9, 十: 10,
  };
  const raw = m[1];
  const num = /^\d+$/.test(raw) ? Number(raw) : cnMap[raw] || 0;
  if (num >= 1 && num <= sections.length) return num - 1;
  return 0;
}

function escapeHtml(text: string) {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function highlightText(para: string) {
  const safe = escapeHtml(para);
  const kw = materialSearch.value.trim();
  if (!kw) return safe;
  const escapedKw = kw.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  return safe.replace(new RegExp(`(${escapedKw})`, "gi"), '<mark class="mat-mark">$1</mark>');
}

const storageKey = computed(() =>
  draftStorageKey(props.questionId || "", customExamType.value, props.fromTaskId || "")
);

function saveDraftNow() {
  window.clearTimeout(saveTimer);
  try {
    localStorage.setItem(
      storageKey.value,
      JSON.stringify({
        answer: answerText.value,
        prompt: customPrompt.value,
        material: customMaterial.value,
        updatedAt: Date.now(),
      })
    );
    draftStatus.value = "草稿已自动保存";
  } catch {
    draftStatus.value = "草稿保存失败";
  }
}

function restoreDraft() {
  const saved = readDraft(storageKey.value);
  answerText.value = saved?.answer ?? originalAnswer.value;
  customPrompt.value = saved?.prompt || "";
  customMaterial.value = saved?.material || "";
  draftStatus.value = saved ? "已恢复上次草稿" : "";
}

watch([answerText, customPrompt, customMaterial], () => {
  if (loading.value) return;
  draftStatus.value = "正在保存草稿...";
  window.clearTimeout(saveTimer);
  saveTimer = window.setTimeout(saveDraftNow, 450);
});

function switchCustomType(type: ExamType) {
  if (customExamType.value === type) return;
  saveDraftNow();
  customExamType.value = type;
  restoreDraft();
}

async function loadData() {
  mobilePane.value = props.fromTaskId ? "answer" : "material";
  loading.value = true;
  loadError.value = "";
  question.value = null;
  originalAnswer.value = "";
  activeMatIndex.value = 0;
  try {
    if (!isCustom.value && props.questionId) {
      question.value = await apiRequest<QuestionDetail>(
        `/api/questions/${encodeURIComponent(props.questionId)}`
      );
      activeMatIndex.value = detectReferencedMaterialIndex(
        question.value.prompt || "",
        materialSections.value
      );
      if (props.fromTaskId) {
        const task = await apiRequest<TaskStatusResp>(
          `/api/grading/tasks/${encodeURIComponent(props.fromTaskId)}`
        );
        if (task.report?.student_answer) {
          originalAnswer.value = task.report.student_answer;
        }
      }
    }
    restoreDraft();
  } catch (err: any) {
    loadError.value = err?.message || "加载题目失败，请稍后重试";
  } finally {
    loading.value = false;
  }
}

async function processOcrFiles(files: File[]) {
  if (!userState.user) {
    showToast("请先登录后使用手写照片 OCR 识字", "warn");
    openAuthModal("login");
    return;
  }
  const remain = 4 - previewPhotos.value.length;
  if (remain <= 0) {
    showToast("单次最多上传 4 页手写照片", "warn");
    return;
  }
  const list = files.filter((f) => f.type.startsWith("image/")).slice(0, remain);
  if (!list.length) {
    showToast("请选择 JPG / PNG / WebP 格式图片", "warn");
    return;
  }

  ocrLoading.value = true;
  let successCount = 0;
  try {
    for (let i = 0; i < list.length; i++) {
      const file = list[i];
      showToast(`正在高清识别第 ${i + 1}/${list.length} 页（约 5~10 秒）...`, "info", 3200);
      const res = await uploadOcrImage(file, activeExamType.value);
      const recognized = (res.recognized_text || "").trim();
      if (!recognized) {
        showToast(`第 ${i + 1} 页未识别出文字，请确保画面清晰后重传`, "warn", 3600);
        continue;
      }
      answerText.value += (answerText.value ? "\n" : "") + recognized;
      imagePath.value = res.image_path;
      previewPhotos.value.push({ url: URL.createObjectURL(file), text: recognized });
      successCount += 1;
    }
    if (successCount > 0) {
      showToast("照片识别完成，请核对后提交批改", "success");
    }
  } catch (err: any) {
    showToast(err?.message || "照片识别失败，请重试", "error");
  } finally {
    ocrLoading.value = false;
  }
}

function restoreOcrText() {
  const joined = previewPhotos.value
    .map((p) => p.text.trim())
    .filter(Boolean)
    .join("\n");
  if (joined) {
    answerText.value = joined;
    showToast("已恢复照片识别文字", "success");
  }
}

function handleAnswerImageInput(e: Event) {
  const input = e.target as HTMLInputElement;
  const files = Array.from(input.files || []);
  input.value = "";
  if (files.length) processOcrFiles(files);
}

function handleDropFiles(e: DragEvent) {
  isDragging.value = false;
  const files = Array.from(e.dataTransfer?.files || []);
  if (files.length) processOcrFiles(files);
}

function handleGlobalPaste(e: ClipboardEvent) {
  const items = Array.from(e.clipboardData?.items || []);
  const imageFiles: File[] = [];
  for (const item of items) {
    if (item.type.startsWith("image/")) {
      const file = item.getAsFile();
      if (file) imageFiles.push(file);
    }
  }
  if (imageFiles.length > 0) {
    e.preventDefault();
    processOcrFiles(imageFiles);
  }
}

async function handlePromptOcrUpload(e: Event) {
  const input = e.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file) return;
  if (!userState.user) {
    showToast("请先登录后使用拍照识题", "warn");
    openAuthModal("login");
    return;
  }
  promptOcrLoading.value = true;
  try {
    const res = await uploadOcrImage(file, customExamType.value);
    customPrompt.value = res.recognized_text;
    showToast("题目要求已识别填入", "success");
  } catch (err: any) {
    showToast(err?.message || "题干识别失败", "error");
  } finally {
    promptOcrLoading.value = false;
  }
}

function removePhoto(idx: number) {
  const [removed] = previewPhotos.value.splice(idx, 1);
  if (removed?.url) URL.revokeObjectURL(removed.url);
  if (removed?.text) {
    const pos = answerText.value.indexOf(removed.text);
    if (pos >= 0) {
      const before = answerText.value.slice(0, pos).replace(/\n+$/, "");
      const after = answerText.value.slice(pos + removed.text.length).replace(/^\n+/, "");
      answerText.value = before && after ? `${before}\n${after}` : before || after;
    }
  }
}

async function handleSubmit() {
  if (!userState.user) {
    showToast("请先登录或注册（新用户送 3 次免费精批）", "warn");
    openAuthModal("register");
    return;
  }
  if (isCustom.value && customPrompt.value.trim().length < 5) {
    mobilePane.value = "material";
    showToast("请先输入或上传识别题目要求（至少 5 个字）", "warn");
    return;
  }
  if (answerText.value.trim().length < 15) {
    showToast("作答内容太短，至少需要 15 个字", "warn");
    return;
  }

  submitting.value = true;
  try {
    const endpoint = isCustom.value ? "/api/grading/submit-custom" : "/api/grading/submit";
    const body = isCustom.value
      ? {
          exam_type: customExamType.value,
          custom_prompt: customPrompt.value.trim(),
          custom_material: customMaterial.value.trim(),
          student_answer: answerText.value,
          image_path: imagePath.value,
        }
      : {
          question_id: props.questionId,
          student_answer: answerText.value,
          image_path: imagePath.value,
        };

    const res = await apiRequest<{ task_id: string }>(endpoint, {
      method: "POST",
      body,
    });
    localStorage.removeItem(storageKey.value);
    refreshUser(true);
    emit("submitted", res.task_id);
  } catch (err: any) {
    if (err?.status === 402) {
      showToast(err.message || "精批次数已用完，请先兑换额度", "warn");
      openAccountModal();
    } else {
      showToast(err?.message || "提交失败，请稍后重试", "error");
    }
  } finally {
    submitting.value = false;
  }
}

// 考场计时器、专注模式与稿纸横线
const focusMode = ref(false);
const linedPaper = ref(false);
const timerRunning = ref(false);
const timerElapsed = ref(0);
let examTimerHandle: number | undefined;

const suggestedSeconds = computed(() => {
  if (activeExamType.value === "shenlun_essay") return 60 * 60;
  if (activeExamType.value === "kaoyan_english") return 35 * 60;
  if (activeExamType.value === "kaoyan_396") return 30 * 60;
  return 25 * 60;
});

const timerRemaining = computed(() => suggestedSeconds.value - timerElapsed.value);

const formattedTimer = computed(() => {
  const rem = timerRemaining.value;
  const abs = Math.abs(rem);
  const m = String(Math.floor(abs / 60)).padStart(2, "0");
  const s = String(abs % 60).padStart(2, "0");
  return rem < 0 ? `超时 +${m}:${s}` : `${m}:${s}`;
});

const timerStateClass = computed(() => {
  if (timerRemaining.value < 0) return "overtime";
  if (timerRunning.value && timerRemaining.value <= 300) return "soon";
  if (timerRunning.value) return "running";
  return "";
});

function toggleTimer() {
  if (timerRunning.value) {
    window.clearInterval(examTimerHandle);
    examTimerHandle = undefined;
    timerRunning.value = false;
  } else {
    timerRunning.value = true;
    examTimerHandle = window.setInterval(() => {
      timerElapsed.value += 1;
    }, 1000);
  }
}

function resetTimer() {
  window.clearInterval(examTimerHandle);
  examTimerHandle = undefined;
  timerRunning.value = false;
  timerElapsed.value = 0;
}

watch(
  () => [props.questionId, props.fromTaskId, props.customMode],
  () => {
    resetTimer();
    loadData();
  }
);

onMounted(() => {
  loadData();
});

onBeforeUnmount(() => {
  window.clearInterval(examTimerHandle);
  window.clearTimeout(saveTimer);
  previewPhotos.value.forEach((p) => URL.revokeObjectURL(p.url));
});
</script>

<style scoped>
.workspace-shell {
  max-width: 1440px;
  margin: 0 auto;
  padding: 14px 20px 20px;
  height: calc(100vh - var(--nav-height));
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.ws-topbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.ws-topbar-left,
.ws-topbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.ws-divider {
  width: 1px;
  height: 16px;
  background: var(--border-strong);
}

.ws-mode-badge {
  font-size: 12px;
  font-weight: 600;
  color: var(--brand);
  background: var(--brand-soft);
  padding: 3px 10px;
  border-radius: 99px;
  flex-shrink: 0;
}



.draft-pill {
  font-size: 12px;
  color: var(--ink-muted);
}

.ws-loading {
  padding: 60px 24px;
  text-align: center;
  color: var(--ink-muted);
}

.ws-loading.error {
  color: var(--red-pen);
}

.split-pane {
  flex: 1;
  min-height: 0;
  display: grid;
  grid-template-columns: minmax(0, 47fr) minmax(0, 53fr);
  gap: 16px;
}

.left-pane,
.right-pane {
  display: flex;
  flex-direction: column;
  min-height: 0;
  overflow: hidden;
}

.left-pane {
  padding: 20px 22px;
  gap: 14px;
}

.q-meta-tags {
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 8px;
}

.meta-tag {
  font-size: 11.5px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--brand-soft);
  color: var(--brand);
}

.meta-tag.neutral {
  background: var(--bg-inset);
  color: var(--ink-secondary);
}

.q-heading {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 18px;
  line-height: 1.4;
  color: var(--ink-primary);
}

.prompt-box {
  background: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  padding: 14px 16px;
  flex-shrink: 0;
  max-height: 36%;
  overflow-y: auto;
}

.box-label {
  font-size: 12px;
  font-weight: 700;
  color: var(--ink-muted);
  margin-bottom: 6px;
  display: block;
}

.prompt-text {
  font-size: 14px;
  line-height: 1.7;
  color: var(--ink-primary);
  white-space: pre-wrap;
}

.figure-card {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px dashed var(--border-strong);
}

.figure-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 12px;
  color: var(--ink-secondary);
  margin-bottom: 6px;
}

.figure-img {
  max-width: 100%;
  max-height: 220px;
  object-fit: contain;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
  cursor: zoom-in;
  display: block;
}

.figure-caption {
  margin-top: 6px;
  font-size: 12px;
  color: var(--ink-muted);
}

.original-card {
  border: 1px solid var(--warn-amber-border);
  background: var(--warn-amber-soft);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  flex-shrink: 0;
}

.original-head {
  display: flex;
  justify-content: space-between;
  font-size: 12.5px;
  font-weight: 600;
  color: var(--warn-amber);
  cursor: pointer;
}

.original-body {
  margin-top: 8px;
  max-height: 140px;
  overflow-y: auto;
  font-size: 13px;
  color: var(--ink-primary);
  white-space: pre-wrap;
  line-height: 1.7;
}

.material-reader {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border-subtle);
  border-radius: var(--radius-md);
  overflow: hidden;
  background: #fffdf9;
}

.reader-toolbar {
  padding: 10px 12px;
  background: var(--bg-subtle);
  border-bottom: 1px solid var(--border-subtle);
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.mat-tabs {
  display: flex;
  gap: 6px;
  overflow-x: auto;
  padding-bottom: 2px;
}

.mat-tab {
  border: 1px solid var(--border-subtle);
  background: var(--bg-surface);
  color: var(--ink-secondary);
  font-size: 12px;
  padding: 4px 10px;
  border-radius: 99px;
  white-space: nowrap;
}

.mat-tab.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
  font-weight: 600;
}

.reader-controls {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
}

.mat-search {
  flex: 1;
  padding: 5px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-strong);
  background: #fff;
  font-size: 12.5px;
  outline: none;
}

.mat-search:focus {
  border-color: var(--brand);
}

.font-switch {
  display: inline-flex;
  border: 1px solid var(--border-strong);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.font-switch button {
  border: none;
  background: #fff;
  color: var(--ink-secondary);
  padding: 4px 9px;
  font-size: 12px;
}

.font-switch button.active {
  background: var(--ink-primary);
  color: #fff;
}

.reader-content {
  flex: 1;
  overflow-y: auto;
  padding: 16px 20px;
  line-height: 1.9;
  color: var(--ink-primary);
}

.mat-para {
  margin: 0 0 12px;
  text-indent: 2em;
}

:deep(.mat-mark) {
  background: #fef08a;
  color: #111827;
  padding: 0 2px;
  border-radius: 2px;
}

/* 自由批改左栏 */
.custom-left {
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: 100%;
  overflow-y: auto;
}

.custom-tip {
  margin: -6px 0 0;
  font-size: 12.5px;
  color: var(--ink-muted);
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-block.flex-grow {
  flex: 1;
  min-height: 160px;
}

.label-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.type-pills {
  display: flex;
  gap: 8px;
}

.type-pill {
  flex: 1;
  padding: 8px 10px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-strong);
  background: var(--bg-subtle);
  color: var(--ink-secondary);
  font-weight: 500;
}

.type-pill.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #fff;
  font-weight: 600;
}

.custom-textarea {
  width: 100%;
  padding: 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-strong);
  background: var(--bg-subtle);
  line-height: 1.65;
  resize: vertical;
  outline: none;
}

.custom-textarea:focus {
  border-color: var(--brand);
  background: #fff;
}

.custom-textarea.tall {
  flex: 1;
  min-height: 180px;
  resize: none;
}

/* 右栏作答区 */
.right-pane {
  position: relative;
  padding: 18px 22px;
  gap: 12px;
}

.right-pane.dragging {
  border-color: var(--brand);
  box-shadow: 0 0 0 2px var(--brand-border);
}

.editor-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-shrink: 0;
}

.editor-title-group h3 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 17px;
}

.paste-hint {
  display: block;
  font-size: 12px;
  color: var(--ink-muted);
  margin-top: 2px;
}

.upload-inline {
  cursor: pointer;
}

.thumb-bar {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  background: var(--bg-subtle);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-subtle);
  flex-wrap: wrap;
}

.thumb-item {
  position: relative;
  width: 56px;
  height: 56px;
  border-radius: 6px;
  overflow: hidden;
  border: 1px solid var(--border-strong);
}

.thumb-img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  cursor: zoom-in;
}

.thumb-index {
  position: absolute;
  bottom: 0;
  left: 0;
  right: 0;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  font-size: 10px;
  text-align: center;
}

.thumb-del {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 18px;
  height: 18px;
  border: none;
  border-radius: 50%;
  background: rgba(200, 50, 40, 0.9);
  color: #fff;
  font-size: 12px;
  line-height: 1;
  padding: 0;
}

.thumb-note {
  font-size: 12px;
  color: var(--ink-muted);
}

.textarea-wrap {
  position: relative;
  flex: 1;
  min-height: 0;
  display: flex;
}

.answer-editor {
  width: 100%;
  height: 100%;
  padding: 16px 18px;
  border-radius: var(--radius-md);
  border: 1px solid var(--border-subtle);
  background: #fffefb;
  font-size: 15px;
  line-height: 1.85;
  color: var(--ink-primary);
  resize: none;
  outline: none;
}

.answer-editor:focus {
  border-color: var(--brand);
  background: #fff;
}

.drop-overlay {
  position: absolute;
  inset: 0;
  background: rgba(30, 64, 175, 0.08);
  border: 2px dashed var(--brand);
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 600;
  color: var(--brand);
  pointer-events: none;
}

.editor-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding-top: 8px;
  border-top: 1px solid var(--bg-inset);
  flex-shrink: 0;
}

.word-meter {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.wc-num {
  font-size: 13.5px;
  color: var(--ink-secondary);
}

.wc-num.warn {
  color: var(--red-pen);
}

.wc-warn-badge {
  margin-left: 6px;
  font-size: 12px;
  font-weight: 600;
  background: var(--red-pen-soft);
  color: var(--red-pen);
  padding: 1px 7px;
  border-radius: 99px;
}

.wc-req {
  font-size: 12px;
  color: var(--ink-muted);
}

.submit-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.quota-hint {
  font-size: 12.5px;
  color: var(--ink-muted);
}

/* 灯箱 */
.lightbox {
  position: fixed;
  inset: 0;
  z-index: 150;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 28px;
}

.lightbox-img {
  max-width: 92vw;
  max-height: 90vh;
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-lg);
}

.lightbox-close {
  position: fixed;
  top: 20px;
  right: 26px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  border: none;
  background: rgba(255, 255, 255, 0.2);
  color: #fff;
  font-size: 26px;
}

/* 专注全屏模式 */
.workspace-shell.focus-mode {
  position: fixed;
  inset: 0;
  z-index: 60;
  max-width: 100%;
  height: 100vh;
  background: var(--bg-canvas);
  padding: 14px 28px 20px;
}

/* 考场限时计时器 */
.exam-timer {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 7px;
  border: 1px solid #dfd8ca;
  background: #fcfaf5;
  font-size: 12.5px;
  color: var(--ink-secondary);
}

.exam-timer.running {
  border-color: var(--brand);
  color: var(--ink-primary);
}

.exam-timer.soon {
  border-color: var(--warn-amber-border);
  background: var(--warn-amber-soft);
  color: var(--warn-amber);
}

.exam-timer.overtime {
  border-color: var(--red-pen-border);
  background: var(--red-pen-soft);
  color: var(--red-pen);
}

.timer-clock {
  font-variant-numeric: tabular-nums;
  font-weight: 700;
  font-size: 13px;
}

.timer-btn {
  border: 0;
  background: transparent;
  padding: 2px 5px;
  border-radius: 4px;
  font-size: 12px;
  color: inherit;
  opacity: 0.85;
}

.timer-btn:hover {
  background: rgba(26, 28, 27, 0.06);
  opacity: 1;
}

.editor-tools {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* 宣纸稿纸横线底纹 */
.answer-editor.lined-paper {
  line-height: 32px;
  padding-top: 14px;
  background-color: #fffdf8;
  background-image: repeating-linear-gradient(
    to bottom,
    transparent 0,
    transparent 31px,
    rgba(26, 28, 27, 0.085) 31px,
    rgba(26, 28, 27, 0.085) 32px
  );
  background-attachment: local;
  background-position-y: 13px;
}

.tab-hit {
  display: inline-block;
  margin-left: 4px;
  padding: 0 5px;
  border-radius: 99px;
  background: var(--red-pen);
  color: #fff;
  font-size: 10.5px;
  font-weight: 700;
}

.mat-limit-tip {
  font-size: 11.5px;
  color: var(--ink-muted);
  font-variant-numeric: tabular-nums;
}

.pane-switch { display: none; }
@media (max-width: 960px) {
  .workspace-shell { height: auto; padding: 10px 14px 32px; }
  .ws-topbar, .ws-topbar-right { flex-wrap: wrap; }
  .pane-switch { display: flex; gap: 6px; position: sticky; top: var(--nav-height); z-index: 5; padding: 6px 0; background: var(--bg-canvas); }
  .pane-switch button { flex: 1; padding: 10px; border: 1px solid var(--border-strong); border-radius: 6px; background: var(--bg-surface); color: var(--ink-secondary); }
  .pane-switch button[aria-pressed="true"] { border-color: var(--brand); color: var(--brand); background: var(--brand-soft); font-weight: 600; }
  .split-pane { display: block; min-width: 0; }
  .split-pane[data-pane="material"] .right-pane,
  .split-pane[data-pane="answer"] .left-pane { display: none; }
  .left-pane, .right-pane { padding: 16px; }
  .reader-controls, .editor-head, .editor-footer, .submit-actions { flex-wrap: wrap; }
  .material-reader { flex: auto; }
  .answer-editor { min-height: 38vh; font-size: 16px; }
  .editor-footer { align-items: flex-start; }
}
</style>
