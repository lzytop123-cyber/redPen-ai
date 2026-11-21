<template>
  <div class="feedback-root no-print">
    <button
      class="fb-fab"
      type="button"
      title="内测意见反馈"
      @click="open = true"
    >
      <span class="fb-dot" aria-hidden="true"></span>
      <span>内测反馈</span>
    </button>

    <div v-if="open" class="fb-mask" @click.self="open = false">
      <div class="fb-modal paper-card">
        <button class="fb-close" type="button" aria-label="关闭" @click="open = false">×</button>

        <div class="fb-head">
          <div class="fb-eyebrow">知行岛·自习室 内测共创</div>
          <h3>遇到批改不准或使用问题？</h3>
          <p>一键复制下方诊断信息发给自习室前台或内测群，我们会第一时间核对原卷并优化。</p>
        </div>

        <div class="fb-tags">
          <button
            v-for="t in categories"
            :key="t"
            type="button"
            :class="['fb-tag', selectedCategory === t ? 'active' : '']"
            @click="selectedCategory = t"
          >
            {{ t }}
          </button>
        </div>

        <label class="fb-field">
          <span>补充说明（选填）</span>
          <textarea
            v-model="note"
            rows="3"
            maxlength="400"
            placeholder="例如：第 2 个采分点其实我写了，或者觉得某句升格不够贴合材料..."
          ></textarea>
        </label>

        <div class="fb-context">
          <div><strong>当前页面：</strong>{{ pageLabel }}</div>
          <div v-if="contextRef"><strong>关联编号：</strong><code>{{ contextRef }}</code></div>
        </div>

        <div class="fb-actions">
          <button class="btn btn-outline btn-sm" type="button" @click="open = false">暂不反馈</button>
          <button class="btn btn-primary btn-sm" type="button" @click="copyFeedback">
            📋 一键复制反馈内容发给群主
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { showToast, userState } from "../stores/auth";

const props = defineProps<{
  page: string;
  questionId?: string;
  taskId?: string;
}>();

const open = ref(false);
const categories = [
  "采分点/打分有异议",
  "升格范文建议",
  "手写识字不准",
  "界面或功能建议",
];
const selectedCategory = ref(categories[0]);
const note = ref("");

const pageLabel = computed(() => {
  if (props.page === "report") return "红笔精批报告页";
  if (props.page === "workspace") return "沉浸式作答台";
  if (props.page === "history") return "批改记录与薄弱项";
  return "真题精批库";
});

const contextRef = computed(() => {
  if (props.page === "report" && props.taskId) return `任务号 ${props.taskId}`;
  if (props.page === "workspace" && props.questionId) return `题号 ${props.questionId}`;
  return "";
});

async function copyFeedback() {
  const userLabel = userState.user
    ? `${userState.user.nickname} (${userState.user.username || `ID#${userState.user.user_id}`})`
    : "未登录访客";
  const lines = [
    "【知行岛自习室 · 内测反馈】",
    `类型：${selectedCategory.value}`,
    `页面：${pageLabel.value}`,
    ...(contextRef.value ? [`编号：${contextRef.value}`] : []),
    `用户：${userLabel}`,
    `说明：${note.value.trim() || "（无补充说明）"}`,
  ];
  try {
    await navigator.clipboard.writeText(lines.join("\n"));
    showToast("反馈信息已复制，直接粘贴发到自习室群或微信即可！", "success", 3600);
    note.value = "";
    open.value = false;
  } catch {
    showToast("复制失败，请手动截图当前页面发给自习室群主", "warn");
  }
}
</script>

<style scoped>
.fb-fab {
  position: fixed;
  right: 22px;
  bottom: 22px;
  z-index: 45;
  display: inline-flex;
  align-items: center;
  gap: 7px;
  padding: 8px 14px;
  border-radius: 99px;
  border: 1px solid #dfd8ca;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(8px);
  color: var(--ink-secondary);
  font-size: 12.5px;
  font-weight: 500;
  box-shadow: var(--shadow-md);
  transition: all 0.16s ease;
}

.fb-fab:hover {
  color: var(--ink-primary);
  border-color: var(--brand-border);
  transform: translateY(-1px);
}

.fb-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: var(--red-pen);
}

.fb-mask {
  position: fixed;
  inset: 0;
  z-index: 120;
  background: rgba(20, 24, 22, 0.42);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.fb-modal {
  position: relative;
  width: 100%;
  max-width: 460px;
  padding: 24px 26px 22px;
  box-shadow: var(--shadow-lg);
}

.fb-close {
  position: absolute;
  top: 12px;
  right: 14px;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: var(--ink-muted);
  font-size: 20px;
  line-height: 1;
}

.fb-close:hover {
  background: var(--bg-hover);
  color: var(--ink-primary);
}

.fb-eyebrow {
  font-size: 11.5px;
  font-weight: 700;
  color: var(--red-pen);
  letter-spacing: 0.04em;
  margin-bottom: 4px;
}

.fb-head h3 {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 18px;
  color: var(--ink-primary);
}

.fb-head p {
  margin: 6px 0 16px;
  font-size: 12.5px;
  color: var(--ink-muted);
  line-height: 1.6;
}

.fb-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.fb-tag {
  padding: 5px 11px;
  border-radius: 99px;
  border: 1px solid var(--border-strong);
  background: var(--bg-subtle);
  color: var(--ink-secondary);
  font-size: 12.5px;
  transition: all 0.14s ease;
}

.fb-tag.active {
  background: var(--brand);
  border-color: var(--brand);
  color: #faf8f4;
  font-weight: 500;
}

.fb-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}

.fb-field span {
  font-size: 12px;
  font-weight: 600;
  color: var(--ink-secondary);
}

.fb-field textarea {
  width: 100%;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-strong);
  background: var(--bg-subtle);
  color: var(--ink-primary);
  resize: vertical;
  outline: none;
  line-height: 1.6;
}

.fb-field textarea:focus {
  border-color: var(--brand);
  background: #fff;
}

.fb-context {
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--bg-subtle);
  border: 1px solid var(--border-subtle);
  font-size: 12px;
  color: var(--ink-secondary);
  display: flex;
  flex-direction: column;
  gap: 4px;
  margin-bottom: 16px;
}

.fb-context code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  color: var(--ink-primary);
}

.fb-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}
</style>
