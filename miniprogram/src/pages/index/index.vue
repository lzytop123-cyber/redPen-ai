<template>
  <view class="page">
    <!-- 顶部品牌栏 -->
    <view class="header">
      <view class="title">AI 阅卷级主观题精批</view>
      <view class="subtitle">覆盖全国 31 省市历年国考/省考申论与考研英语真题</view>
      <view class="search-box">
        <input
          v-model="keyword"
          class="search-input"
          placeholder="搜索年份/省份/题目关键词（如 2025 山西）"
          confirm-type="search"
          @confirm="fetchQuestions"
        />
        <text class="search-btn" @click="fetchQuestions">搜索</text>
      </view>
    </view>

    <!-- 醒目的任意题目自由批改大入口 -->
    <view class="quick-entry" @click="goCustomSubmit">
      <view class="quick-left">
        <view class="quick-title">📷 任意题目拍照直批</view>
        <view class="quick-desc">模拟卷 / 机构押题 / 随手练笔，无需找题直接批改</view>
      </view>
      <view class="quick-btn">去批改 →</view>
    </view>

    <!-- 大类切换 Tabs -->
    <view class="tabs">
      <view
        v-for="tab in tabs"
        :key="tab.value"
        :class="['tab-item', activeType === tab.value ? 'active' : '']"
        @click="selectTab(tab.value)"
      >
        {{ tab.label }}
      </view>
    </view>

    <!-- 地区 & 细分题型筛选器 -->
    <view class="filter-panel">
      <view v-if="activeType !== 'kaoyan_english'" class="filter-row">
        <text class="filter-label">地区</text>
        <scroll-view scroll-x class="chip-scroll">
          <view class="chip-list">
            <view
              v-for="r in regions"
              :key="r.value"
              :class="['chip', activeRegion === r.value ? 'chip-active' : '']"
              @click="selectRegion(r.value)"
            >
              {{ r.label }}
            </view>
          </view>
        </scroll-view>
      </view>

      <view v-if="activeType === 'shenlun_short'" class="filter-row" style="margin-top: 12rpx;">
        <text class="filter-label">题型</text>
        <scroll-view scroll-x class="chip-scroll">
          <view class="chip-list">
            <view
              v-for="s in subTypes"
              :key="s.value"
              :class="['chip', activeSubType === s.value ? 'chip-active' : '']"
              @click="selectSubType(s.value)"
            >
              {{ s.label }}
            </view>
          </view>
        </scroll-view>
      </view>

      <view v-if="activeType === 'kaoyan_english'" class="filter-row">
        <text class="filter-label">分类</text>
        <scroll-view scroll-x class="chip-scroll">
          <view class="chip-list">
            <view
              v-for="k in kaoyanSubTypes"
              :key="k.value"
              :class="['chip', activeSubType === k.value ? 'chip-active' : '']"
              @click="selectSubType(k.value)"
            >
              {{ k.label }}
            </view>
          </view>
        </scroll-view>
      </view>
    </view>

    <!-- 真题列表 -->
    <view class="list">
      <view class="result-count">共匹配 {{ totalCount }} 道真题</view>
      <view v-if="loading" class="empty">加载真题库中...</view>
      <view v-else-if="questions.length === 0" class="empty">暂无匹配真题，可点击上方「任意题目拍照直批」</view>
      <view
        v-for="q in questions"
        :key="q.question_id"
        class="card"
        @click="goSubmit(q.question_id)"
      >
        <view class="card-top">
          <text class="tag">{{ q.sub_type || q.exam_type }}</text>
          <text class="score">满分 {{ q.full_score }} 分</text>
        </view>
        <view class="card-title">{{ q.title }}</view>
        <view class="card-meta">
          <text v-if="q.min_words || q.max_words">字数要求：{{ formatWordLimits(q.min_words, q.max_words) }}</text>
          <text v-if="q.scoring_point_count > 0"> ｜ 含 {{ q.scoring_point_count }} 个标准采分点</text>
          <text v-else> ｜ 结合给定材料评阅</text>
        </view>
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { onMounted, ref } from "vue";
import { formatWordLimits } from "@/utils/wordLimits";
import { request } from "@/utils/request";

interface QuestionItem {
  question_id: string;
  exam_type: string;
  title: string;
  sub_type: string;
  full_score: number;
  min_words: number;
  max_words: number;
  scoring_point_count: number;
}

const tabs = [
  { label: "申论小题", value: "shenlun_short" },
  { label: "申论大作文", value: "shenlun_essay" },
  { label: "考研英语", value: "kaoyan_english" },
];

const regions = ref<Array<{ label: string; value: string }>>([
  { label: "全部", value: "" },
  { label: "国考", value: "国考" },
  { label: "山西", value: "山西" },
  { label: "贵州", value: "贵州" },
  { label: "广东", value: "广东" },
  { label: "湖北", value: "湖北" },
]);

async function fetchRegions() {
  try {
    const res = await request<{ items: Array<{ label: string; value: string; count: number }> }>({
      url: "/api/questions/regions",
    });
    if (res.items && res.items.length > 0) {
      regions.value = [
        { label: "全部", value: "" },
        ...res.items.map((r) => ({ label: r.label, value: r.value })),
      ];
    }
  } catch {
    // 兜底保留默认列表
  }
}

const subTypes = [
  { label: "全部", value: "" },
  { label: "归纳概括", value: "归纳概括" },
  { label: "提出对策", value: "提出对策" },
  { label: "综合分析", value: "综合分析" },
  { label: "公文写作", value: "公文写作" },
];

const kaoyanSubTypes = [
  { label: "全部", value: "" },
  { label: "英语一·大作文", value: "英语一·大作文" },
  { label: "英语一·小作文", value: "英语一·小作文" },
  { label: "英语二·大作文", value: "英语二·大作文" },
  { label: "英语二·小作文", value: "英语二·小作文" },
];

const activeType = ref("shenlun_short");
const activeRegion = ref("");
const activeSubType = ref("");
const keyword = ref("");
const loading = ref(false);
const totalCount = ref(0);
const questions = ref<QuestionItem[]>([]);

async function fetchQuestions() {
  loading.value = true;
  try {
    const params = [
      `exam_type=${encodeURIComponent(activeType.value)}`,
      `page_size=40`,
    ];
    if (activeType.value !== "kaoyan_english" && activeRegion.value) {
      params.push(`region=${encodeURIComponent(activeRegion.value)}`);
    }
    if ((activeType.value === "shenlun_short" || activeType.value === "kaoyan_english") && activeSubType.value) {
      params.push(`sub_type=${encodeURIComponent(activeSubType.value)}`);
    }
    if (keyword.value.trim()) {
      params.push(`keyword=${encodeURIComponent(keyword.value.trim())}`);
    }
    const res = await request<{ total: number; items: QuestionItem[] }>({
      url: `/api/questions?${params.join("&")}`,
    });
    totalCount.value = res.total || 0;
    questions.value = res.items || [];
  } finally {
    loading.value = false;
  }
}

function selectTab(val: string) {
  activeType.value = val;
  activeSubType.value = "";
  fetchQuestions();
}

function selectRegion(val: string) {
  activeRegion.value = val;
  fetchQuestions();
}

function selectSubType(val: string) {
  activeSubType.value = val;
  fetchQuestions();
}

function goSubmit(qid: string) {
  uni.navigateTo({ url: `/pages/submit/submit?qid=${encodeURIComponent(qid)}` });
}

function goCustomSubmit() {
  uni.navigateTo({ url: `/pages/submit/submit?mode=custom` });
}

onMounted(() => {
  fetchRegions();
  fetchQuestions();
});
</script>

<style scoped>
.header {
  background: linear-gradient(135deg, #1e3a8a, #2563eb);
  color: #fff;
  padding: 32rpx 28rpx 36rpx;
}
.title {
  font-size: 38rpx;
  font-weight: 700;
}
.subtitle {
  font-size: 24rpx;
  opacity: 0.85;
  margin-top: 8rpx;
}
.search-box {
  margin-top: 24rpx;
  display: flex;
  background: #fff;
  border-radius: 999rpx;
  padding: 12rpx 24rpx;
  align-items: center;
}
.search-input {
  flex: 1;
  color: #1f2937;
  font-size: 26rpx;
}
.search-btn {
  color: #2563eb;
  font-weight: 600;
  padding-left: 16rpx;
}
.quick-entry {
  margin: 20rpx 24rpx 12rpx;
  padding: 24rpx 26rpx;
  background: linear-gradient(135deg, #fff7ed, #ffedd5);
  border: 2rpx solid #fdba74;
  border-radius: 18rpx;
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.quick-left {
  flex: 1;
  padding-right: 16rpx;
}
.quick-title {
  font-size: 32rpx;
  font-weight: 700;
  color: #9a3412;
}
.quick-desc {
  font-size: 23rpx;
  color: #c2410c;
  margin-top: 6rpx;
}
.quick-btn {
  background: #ea580c;
  color: #fff;
  font-size: 24rpx;
  font-weight: 600;
  padding: 12rpx 22rpx;
  border-radius: 999rpx;
  white-space: nowrap;
}
.tabs {
  display: flex;
  background: #fff;
  padding: 16rpx 24rpx;
  gap: 16rpx;
  border-bottom: 1rpx solid #f3f4f6;
}
.tab-item {
  flex: 1;
  text-align: center;
  padding: 14rpx 0;
  border-radius: 12rpx;
  font-size: 26rpx;
  color: #4b5563;
  background: #f3f4f6;
}
.tab-item.active {
  background: #2563eb;
  color: #fff;
  font-weight: 600;
}
.filter-panel {
  background: #fff;
  padding: 14rpx 24rpx 18rpx;
  border-bottom: 1rpx solid #e5e7eb;
}
.filter-row {
  display: flex;
  align-items: center;
}
.filter-label {
  font-size: 23rpx;
  color: #6b7280;
  font-weight: 600;
  margin-right: 14rpx;
  white-space: nowrap;
}
.chip-scroll {
  flex: 1;
  white-space: nowrap;
  overflow: hidden;
}
.chip-list {
  display: inline-flex;
  gap: 12rpx;
}
.chip {
  display: inline-block;
  padding: 8rpx 20rpx;
  border-radius: 999rpx;
  font-size: 23rpx;
  background: #f3f4f6;
  color: #4b5563;
}
.chip-active {
  background: #dbeafe;
  color: #1d4ed8;
  font-weight: 600;
}
.list {
  padding: 16rpx 24rpx 24rpx;
}
.result-count {
  font-size: 22rpx;
  color: #6b7280;
  margin-bottom: 14rpx;
}
.card {
  background: #fff;
  border-radius: 16rpx;
  padding: 24rpx;
  margin-bottom: 20rpx;
  box-shadow: 0 4rpx 14rpx rgba(0, 0, 0, 0.04);
}
.card-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12rpx;
}
.tag {
  background: #eff6ff;
  color: #1d4ed8;
  font-size: 22rpx;
  padding: 4rpx 14rpx;
  border-radius: 8rpx;
}
.score {
  font-size: 24rpx;
  color: #dc2626;
  font-weight: 600;
}
.card-title {
  font-size: 30rpx;
  font-weight: 600;
  line-height: 1.45;
  margin-bottom: 12rpx;
}
.card-meta {
  font-size: 24rpx;
  color: #6b7280;
}
.empty {
  text-align: center;
  color: #9ca3af;
  padding: 80rpx 0;
}
</style>
