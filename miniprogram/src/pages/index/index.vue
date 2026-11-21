<template>
  <view class="page">
    <view class="header">
      <view class="masthead">
        <view class="title">历年真题</view>
        <button class="quick-entry" @click="goCustomSubmit">拍自己的题 <text aria-hidden="true">↗</text></button>
      </view>
      <view class="search-box">
        <input
          v-model="keyword"
          class="search-input"
          placeholder="搜索年份、试卷或题目关键词"
          confirm-type="search"
          @confirm="search"
        />
        <text class="search-btn" @click="search">搜索</text>
      </view>
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
    <view class="filter-bar">
      <text class="result-count">{{ loading ? "正在查题…" : loadError ? "题目列表" : totalCount + " 道题" }}</text>
      <button class="filter-toggle" :aria-expanded="filtersOpen" @click="filtersOpen = !filtersOpen">
        {{ filterSummary }} {{ filtersOpen ? "−" : "＋" }}
      </button>
    </view>
    <view v-if="filtersOpen" class="filter-panel">
      <view v-if="activeType !== 'kaoyan_english' && activeType !== 'kaoyan_396'" class="filter-row">
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

      <view v-if="activeType === 'kaoyan_396'" class="filter-row">
        <text class="filter-label">题型</text>
        <scroll-view scroll-x class="chip-scroll">
          <view class="chip-list">
            <view
              v-for="k in kaoyan396SubTypes"
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
      <view v-if="loading" class="empty">加载真题库中...</view>
      <view v-else-if="loadError && questions.length === 0" class="empty" @click="fetchQuestions()">真题加载失败，点此重试</view>
      <view v-else-if="questions.length === 0" class="empty">没有找到题目，可以换个关键词或调整筛选。</view>
      <view
        v-for="q in questions"
        :key="q.question_id"
        class="card"
        @click="goSubmit(q.question_id)"
      >
        <view class="card-top">
          <view class="card-tags">
            <text class="tag">{{ q.sub_type || examLabel }}</text>
            <text v-if="q.hasDraft" class="draft-tag">继续草稿</text>
          </view>
          <text class="score">满分 {{ q.full_score }} 分</text>
        </view>
        <view class="card-title">{{ listTitle(q) }}</view>
        <view class="card-meta">
          <text v-if="q.word_requirement">{{ q.word_requirement }}</text>
          <text v-if="(q.exam_type === 'shenlun_short' || q.exam_type === 'kaoyan_396') && q.scoring_point_count > 0">{{ q.scoring_point_count }} 个{{ q.exam_type === 'kaoyan_396' ? '逻辑漏洞点' : '采分点' }}</text>
        </view>
      </view>
      <view v-if="loadingMore" class="load-more">加载更多真题中...</view>
      <view v-else-if="loadError && questions.length > 0" class="load-more" @click="fetchQuestions(false)">加载失败，点此重试</view>
      <view v-else-if="questions.length > 0 && questions.length >= totalCount" class="load-more">
        已显示全部 {{ totalCount }} 道题
      </view>
    </view>
  </view>
</template>

<script setup lang="ts">
import { computed, ref } from "vue";
import { onLoad, onReachBottom, onShow } from "@dcloudio/uni-app";
import { hasDraft } from "@/utils/drafts";
import { formatWordLimits } from "@/utils/wordLimits";
import { request } from "@/utils/request";

interface QuestionItem {
  question_id: string;
  exam_type: string;
  title: string;
  sub_type: string;
  full_score: number;
  word_requirement: string;
  min_words: number;
  max_words: number;
  scoring_point_count: number;
}

function listTitle(question: QuestionItem): string {
  const title = question.title.trim();
  const suffix = question.sub_type && `【${question.sub_type}】`;
  if (suffix && title.endsWith(suffix)) return title.slice(0, -suffix.length).trim() || title;
  return title;
}

const tabs = [
  { label: "申论小题", value: "shenlun_short" },
  { label: "申论大作文", value: "shenlun_essay" },
  { label: "考研英语", value: "kaoyan_english" },
  { label: "396经综", value: "kaoyan_396" },
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
    if (Array.isArray(res.items)) {
      regions.value = [
        { label: "全部", value: "" },
        ...res.items.map((r) => ({ label: r.label, value: r.value })),
      ];
      if (activeRegion.value && !regions.value.some((r) => r.value === activeRegion.value)) {
        activeRegion.value = "";
        saveFilters();
        if (activeType.value !== "kaoyan_english") fetchQuestions();
      }
    }
  } catch {
    // 离线时仍显示上次从地区列表中选中的省份。
    if (activeRegion.value && !regions.value.some((r) => r.value === activeRegion.value)) {
      regions.value.push({ label: activeRegion.value, value: activeRegion.value });
    }
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

const kaoyan396SubTypes = [
  { label: "全部", value: "" },
  { label: "论证有效性分析", value: "论证有效性分析" },
  { label: "论说文", value: "论说文" },
];

const activeType = ref("shenlun_short");
const examLabel = computed(() => tabs.find((tab) => tab.value === activeType.value)!.label);
const activeRegion = ref("");
const shortSubType = ref("");
const englishSubType = ref("");
const kaoyan396SubType = ref("");
const activeSubType = computed(() => {
  if (activeType.value === "kaoyan_english") return englishSubType.value;
  if (activeType.value === "kaoyan_396") return kaoyan396SubType.value;
  if (activeType.value === "shenlun_short") return shortSubType.value;
  return "";
});
const filtersOpen = ref(false);
const filterSummary = computed(() => {
  const region = activeType.value === "kaoyan_english" || activeType.value === "kaoyan_396" ? "" : activeRegion.value;
  return [region, activeSubType.value].filter(Boolean).join(" · ") || "筛选";
});
const keyword = ref("");
const appliedKeyword = ref("");
const filterStorageKey = "ai_grading_question_filters";

function restoreFilters() {
  try {
    const saved = uni.getStorageSync(filterStorageKey);
    if (!saved || typeof saved !== "object") return;
    if (tabs.some((tab) => tab.value === saved.examType)) activeType.value = saved.examType;
    if (typeof saved.region === "string") activeRegion.value = saved.region;
    if (subTypes.some((s) => s.value === saved.shortSubType)) shortSubType.value = saved.shortSubType;
    if (kaoyanSubTypes.some((s) => s.value === saved.englishSubType)) englishSubType.value = saved.englishSubType;
    if (typeof saved.keyword === "string") keyword.value = appliedKeyword.value = saved.keyword;
  } catch {
    // 存储不可用时使用默认筛选。
  }
}

function saveFilters() {
  try {
    uni.setStorageSync(filterStorageKey, {
      examType: activeType.value,
      region: activeRegion.value,
      shortSubType: shortSubType.value,
      englishSubType: englishSubType.value,
      keyword: appliedKeyword.value,
    });
  } catch {
    // 存储不可用时，本次筛选仍然生效。
  }
}

const loading = ref(false);
const loadingMore = ref(false);
const loadError = ref(false);
const page = ref(1);
const pageSize = 20;
const totalCount = ref(0);
const questions = ref<Array<QuestionItem & { hasDraft: boolean }>>([]);
let requestVersion = 0;

async function fetchQuestions(reset = true) {
  if (reset) {
    requestVersion += 1;
    questions.value = [];
    totalCount.value = 0;
    loading.value = true;
    loadingMore.value = false;
  } else {
    if (loading.value || loadingMore.value || questions.value.length >= totalCount.value) return;
    loadingMore.value = true;
  }
  const version = requestVersion;
  const nextPage = reset ? 1 : page.value + 1;
  loadError.value = false;
  try {
    const params = [
      `exam_type=${encodeURIComponent(activeType.value)}`,
      `page=${nextPage}`,
      `page_size=${pageSize}`,
    ];
    if (activeType.value !== "kaoyan_english" && activeType.value !== "kaoyan_396" && activeRegion.value) {
      params.push(`region=${encodeURIComponent(activeRegion.value)}`);
    }
    if (activeSubType.value) {
      params.push(`sub_type=${encodeURIComponent(activeSubType.value)}`);
    }
    if (appliedKeyword.value) {
      params.push(`keyword=${encodeURIComponent(appliedKeyword.value)}`);
    }
    const res = await request<{ total: number; items: QuestionItem[] }>({
      url: `/api/questions?${params.join("&")}`,
    });
    if (version !== requestVersion) return;
    totalCount.value = res.total;
    page.value = nextPage;
    const incoming = res.items.map((q) => ({
      ...q,
      word_requirement: q.word_requirement ?? formatWordLimits(q.min_words, q.max_words, q.exam_type),
      hasDraft: hasDraft(q.question_id),
    }));
    questions.value = reset ? incoming : [...questions.value, ...incoming];
  } catch {
    if (version === requestVersion) loadError.value = true;
  } finally {
    if (version === requestVersion) {
      loading.value = false;
      loadingMore.value = false;
    }
  }
}

onReachBottom(() => {
  fetchQuestions(false);
});

function selectTab(val: string) {
  if (val === activeType.value) return;
  activeType.value = val;
  search();
}

function selectRegion(val: string) {
  activeRegion.value = val;
  search();
}

function selectSubType(val: string) {
  if (activeType.value === "kaoyan_english") englishSubType.value = val;
  else if (activeType.value === "kaoyan_396") kaoyan396SubType.value = val;
  else shortSubType.value = val;
  search();
}

function search() {
  appliedKeyword.value = keyword.value.trim();
  saveFilters();
  fetchQuestions();
}

function goSubmit(qid: string) {
  uni.navigateTo({ url: `/pages/submit/submit?qid=${encodeURIComponent(qid)}` });
}

function goCustomSubmit() {
  uni.navigateTo({ url: `/pages/submit/submit?mode=custom&examType=${encodeURIComponent(activeType.value)}` });
}

onLoad(() => {
  restoreFilters();
  fetchRegions();
  fetchQuestions();
});

onShow(() => {
  for (const q of questions.value) q.hasDraft = hasDraft(q.question_id);
});
</script>

<style scoped>
.page { padding: 0 36rpx 36rpx; }
.header { padding-top: 42rpx; }
.masthead, .search-box, .filter-bar, .card-top, .filter-row { display: flex; align-items: center; }
.masthead, .filter-bar, .card-top { justify-content: space-between; gap: 16rpx; }
.title { font-family: var(--display); font-size: 54rpx; font-weight: 700; letter-spacing: 2rpx; }
.quick-entry, .filter-toggle { margin: 0; border-radius: 4rpx; font-size: 25rpx; font-weight: 500; }
.quick-entry { background: var(--action); color: #fff; padding: 0 22rpx; line-height: 72rpx; }
.quick-entry text { margin-left: 8rpx; }
.quick-entry::after, .filter-toggle::after { border: 0; }
.search-box { margin: 24rpx 0 22rpx; padding: 0 18rpx; background: var(--wash); border-radius: 5rpx; }
.search-input { min-width: 0; flex: 1; font-size: 27rpx; height: 78rpx; color: var(--ink); }
.search-btn { padding: 14rpx 0 14rpx 24rpx; font-size: 25rpx; color: var(--action); font-weight: 600; }
.tabs { display: flex; gap: 34rpx; border-bottom: 2rpx solid var(--ink); }
.tab-item { padding: 20rpx 0 15rpx; color: var(--muted); font-size: 27rpx; border-bottom: 5rpx solid transparent; }
.tab-item.active { color: var(--ink); border-color: var(--ink); font-weight: 700; }
.filter-bar { min-height: 76rpx; border-bottom: 1rpx solid var(--rule); }
.result-count, .card-meta, .score, .empty, .load-more { font-size: 24rpx; color: var(--muted); }
.filter-toggle { max-width: 75%; padding: 8rpx 0 8rpx 18rpx; line-height: 1.8; color: var(--action); background: transparent; }
.filter-panel { padding: 18rpx 0; border-bottom: 1rpx solid var(--rule); }
.filter-label { color: var(--muted); margin-right: 14rpx; font-size: 24rpx; white-space: nowrap; }
.chip-scroll { flex: 1; min-width: 0; white-space: nowrap; overflow: hidden; }
.chip-list { display: inline-flex; gap: 8rpx; }
.chip { padding: 9rpx 16rpx; font-size: 24rpx; color: var(--muted); }
.chip-active { background: var(--wash); color: var(--ink); font-weight: 700; }
.card { padding: 27rpx 0 28rpx; border-bottom: 1rpx solid var(--rule); }
.card-title { font-family: var(--display); font-size: 35rpx; font-weight: 700; line-height: 1.5; margin: 7rpx 0; }
.card-tags, .card-meta { display: flex; flex-wrap: wrap; align-items: center; gap: 18rpx; }
.tag { font-size: 23rpx; color: var(--mark); font-weight: 600; }
.draft-tag { color: var(--action); font-size: 23rpx; text-decoration: underline; }
.score { white-space: nowrap; font-variant-numeric: tabular-nums; }
.empty, .load-more { padding: 48rpx 0; text-align: center; }
</style>
