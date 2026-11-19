<template>
  <view class="page">
    <!-- 模式 A：内置真题模式 -->
    <view v-if="!isCustomMode && question" class="card">
      <view class="q-title">{{ question.title }}</view>
      <view class="q-prompt">{{ question.prompt }}</view>
      <view v-if="question.material_summary" class="material-toggle" @click="showMaterial = !showMaterial">
        {{ showMaterial ? "收起给定材料摘要 ▲" : "展开给定材料摘要 ▼" }}
      </view>
      <view v-if="showMaterial && question.material_summary" class="material-box">
        {{ question.material_summary }}
      </view>
    </view>

    <!-- 模式 B：任意题目自由批改模式 -->
    <view v-if="isCustomMode" class="card">
      <view class="section-title">1. 选择批改题型</view>
      <view class="type-row">
        <view
          v-for="t in examTypes"
          :key="t.value"
          :class="['type-pill', customExamType === t.value ? 'active' : '']"
          @click="customExamType = t.value"
        >
          {{ t.label }}
        </view>
      </view>

      <view class="section-header" style="margin-top: 20rpx;">
        <text class="section-title">2. 题目要求</text>
        <button class="ocr-btn" size="mini" :loading="promptOcrLoading" @click="ocrToPrompt">
          📷 拍照识题
        </button>
      </view>
      <textarea
        v-model="customPrompt"
        class="prompt-input"
        maxlength="1000"
        placeholder="输入或拍照识别题目要求（如：请以“青年与创新”为主题写一篇 1000 字议论文）"
      />

      <view class="material-toggle" @click="showCustomMaterial = !showCustomMaterial">
        {{ showCustomMaterial ? "收起参考材料/答案（选填） ▲" : "+ 补充给定材料或参考答案（选填，填了更准） ▼" }}
      </view>
      <textarea
        v-if="showCustomMaterial"
        v-model="customMaterial"
        class="prompt-input"
        maxlength="3000"
        placeholder="可粘贴给定材料片段或机构参考答案，辅助 AI 精准踩点..."
      />
    </view>

    <!-- 公共区域：提交我的作答（拍照 OCR + 10 秒微调） -->
    <view class="card">
      <view class="section-header">
        <text class="section-title">{{ isCustomMode ? "3. 我的作答" : "提交我的作答" }}</text>
        <button class="ocr-btn" size="mini" :loading="ocrLoading" @click="chooseAndOcr">
          📷 拍照识别手写稿
        </button>
      </view>
      <view class="tip">拍完手写答卷可花 10 秒核对错别字；或直接粘贴/输入作答文本</view>
      <textarea
        v-model="answerText"
        class="answer-input"
        maxlength="4000"
        placeholder="点击上方「拍照识别手写稿」，或直接在此粘贴/输入你的作答..."
      />
      <view class="word-bar">
        <text>当前字数：{{ currentWordCount }}</text>
        <text v-if="!isCustomMode && question?.max_words">
          要求：{{ question.min_words }}~{{ question.max_words }}
        </text>
      </view>
    </view>

    <view class="footer-bar">
      <button class="submit-btn" type="primary" :loading="submitting" @click="handleSubmit">
        立即开启 AI 红笔精批
      </button>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad } from "@dcloudio/uni-app";
import { request, uploadHandwriting } from "@/utils/request";

const examTypes = [
  { label: "申论小题", value: "shenlun_short" },
  { label: "申论大作文", value: "shenlun_essay" },
  { label: "考研英语", value: "kaoyan_english" },
];

const isCustomMode = ref(false);
const qid = ref("");
const question = ref<any>(null);
const showMaterial = ref(false);

const customExamType = ref("shenlun_essay");
const customPrompt = ref("");
const customMaterial = ref("");
const showCustomMaterial = ref(false);
const promptOcrLoading = ref(false);

const answerText = ref("");
const imagePath = ref<string | null>(null);
const ocrLoading = ref(false);
const submitting = ref(false);

const activeExamType = computed(() =>
  isCustomMode.value ? customExamType.value : question.value?.exam_type || "shenlun_short"
);

const currentWordCount = computed(() => {
  const txt = answerText.value.trim();
  if (!txt) return 0;
  if (activeExamType.value === "kaoyan_english") {
    return txt.split(/\s+/).filter(Boolean).length;
  }
  return txt.replace(/\s+/g, "").length;
});

onLoad(async (opts: any) => {
  if (opts?.mode === "custom" || !opts?.qid) {
    isCustomMode.value = true;
    uni.setNavigationBarTitle({ title: "任意题目自由精批" });
    return;
  }
  qid.value = decodeURIComponent(opts.qid);
  question.value = await request({ url: `/api/questions/${encodeURIComponent(qid.value)}` });
});

function ocrToPrompt() {
  uni.chooseImage({
    count: 1,
    sizeType: ["compressed"],
    sourceType: ["camera", "album"],
    success: async (res) => {
      promptOcrLoading.value = true;
      try {
        const ocrRes = await uploadHandwriting(res.tempFilePaths[0], customExamType.value);
        customPrompt.value = ocrRes.recognized_text;
        uni.showToast({ title: "题目识别完成", icon: "none" });
      } finally {
        promptOcrLoading.value = false;
      }
    },
  });
}

function chooseAndOcr() {
  uni.chooseImage({
    count: 1,
    sizeType: ["compressed"],
    sourceType: ["camera", "album"],
    success: async (res) => {
      ocrLoading.value = true;
      try {
        const ocrRes = await uploadHandwriting(res.tempFilePaths[0], activeExamType.value);
        answerText.value = ocrRes.recognized_text;
        imagePath.value = ocrRes.image_path;
        uni.showToast({
          title: ocrRes.mock_mode ? "Mock 识别完成，可微调" : "手写识别完成，请核对错字",
          icon: "none",
        });
      } finally {
        ocrLoading.value = false;
      }
    },
  });
}

async function handleSubmit() {
  if (isCustomMode.value && customPrompt.value.trim().length < 5) {
    uni.showToast({ title: "请先输入或拍照识别题目要求", icon: "none" });
    return;
  }
  if (answerText.value.trim().length < 15) {
    uni.showToast({ title: "作答内容太短，请先输入或拍照识别", icon: "none" });
    return;
  }

  submitting.value = true;
  try {
    let res: { task_id: string };
    if (isCustomMode.value) {
      res = await request<{ task_id: string }>({
        url: "/api/grading/submit-custom",
        method: "POST",
        data: {
          exam_type: customExamType.value,
          custom_prompt: customPrompt.value,
          custom_material: customMaterial.value,
          student_answer: answerText.value,
          image_path: imagePath.value,
        },
      });
    } else {
      res = await request<{ task_id: string }>({
        url: "/api/grading/submit",
        method: "POST",
        data: {
          question_id: qid.value,
          student_answer: answerText.value,
          image_path: imagePath.value,
        },
      });
    }
    uni.redirectTo({
      url: `/pages/report/report?taskId=${encodeURIComponent(res.task_id)}`,
    });
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
.material-toggle {
  margin-top: 16rpx;
  color: #2563eb;
  font-size: 25rpx;
  font-weight: 600;
}
.material-box {
  margin-top: 12rpx;
  padding: 16rpx;
  background: #f9fafb;
  border-radius: 10rpx;
  font-size: 24rpx;
  color: #4b5563;
  line-height: 1.65;
  max-height: 420rpx;
  overflow-y: auto;
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
  margin: 10rpx 0 16rpx;
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
</style>
