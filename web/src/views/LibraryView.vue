<template>
  <div class="library-page">
    <header class="catalog-hero">
      <div class="hero-content">
        <div class="hero-title-row">
          <h1>真题精批</h1>
          <span class="vermilion-seal" aria-hidden="true">AI 阅卷</span>
        </div>
        <p class="hero-subtitle">申论、考研英语与 396 经综 · 对照采分点逐句红笔批注与同思路升格</p>
        <form class="search-wrap" role="search" @submit.prevent="handleSearch">
          <span class="magnifier" aria-hidden="true"></span>
          <input v-model="keyword" type="text" inputmode="search" aria-label="搜索题库" placeholder="搜试卷、地区或题目关键词" />
          <button v-if="keyword" type="button" class="search-clear" aria-label="清空搜索" @click="keyword = ''; handleSearch()">×</button>
          <button class="search-btn" type="submit">搜索</button>
        </form>
      </div>
      <div class="hero-art" aria-hidden="true"><IslandLandscape /></div>
    </header>

    <div class="catalog-layout">
      <div class="sidebar-col">
        <aside class="library-sidebar" aria-label="题库分类与筛选">
          <h2 class="group-title">考试科目</h2>
          <div class="exam-tabs">
            <button v-for="tab in tabs" :key="tab.value" class="exam-tab"
              :aria-pressed="activeType === tab.value" @click="selectTab(tab.value)">
              <span class="book-mark" :data-exam="tab.value" aria-hidden="true"></span>
              {{ tab.label }}
            </button>
          </div>
          <button class="filter-trigger" :aria-expanded="filtersOpen" aria-controls="question-filters" @click="filtersOpen = !filtersOpen">
            {{ filterSummary || "筛选条件" }} <span aria-hidden="true">{{ filtersOpen ? "−" : "＋" }}</span>
          </button>
          <div id="question-filters" class="filter-panel" :class="{ open: filtersOpen }">
            <h2 class="group-title">筛选条件</h2>
            <label v-if="activeType !== 'kaoyan_english' && activeType !== 'kaoyan_396'">地区
              <select aria-label="地区" :value="activeRegion" @change="selectRegion(($event.target as HTMLSelectElement).value)">
                <option v-for="r in regions" :key="r.value" :value="r.value">{{ r.count ? `${r.label} (${r.count})` : r.label }}</option>
              </select>
            </label>
            <label v-if="activeType !== 'shenlun_essay'">题型
              <select aria-label="题型" :value="activeSubType" @change="selectSubType(($event.target as HTMLSelectElement).value)">
                <option v-for="t in currentSubTypeOptions" :key="t.value" :value="t.value">{{ t.value ? t.label : "全部题型" }}</option>
              </select>
            </label>
            <label>年份
              <select aria-label="年份" :value="activeYear" @change="selectYear(($event.target as HTMLSelectElement).value)">
                <option value="">全部年份</option>
                <option v-for="y in yearOptions" :key="y" :value="String(y)">{{ y }} 年</option>
              </select>
            </label>
            <button v-if="filterSummary || appliedKeyword || keyword" class="reset-link" @click="resetFilters">清除筛选和搜索</button>
          </div>
        </aside>
        <DailyQuoteCard />
      </div>
      <section class="results-section" aria-label="真题列表">
        <div class="results-top">
          <div class="results-heading"><h2>{{ examLabel }}</h2>
            <span role="status">{{ loading ? "正在查询…" : loadError ? "查询失败" : totalCount + " 道题" }}</span>
          </div>
          <button class="own-question" @click="$emit('openCustom', activeType)"><span aria-hidden="true">＋</span> 拍自己的题</button>
        </div>
      <div v-if="loading && questions.length === 0" class="state-box paper-card">
        正在加载真题库...
      </div>

      <div v-else-if="loadError && questions.length === 0" class="state-box paper-card error">
        <p>{{ loadError }}</p>
        <button class="btn btn-outline btn-sm" @click="fetchQuestions(true)">重新加载</button>
      </div>

      <div v-else-if="questions.length === 0" class="state-box paper-card">
        <p>没有找到题目，可以换个关键词或调整筛选。</p>
      </div>

      <div v-else class="question-list">
        <div class="columns" aria-hidden="true">
          <span>试题名称</span><span>年份</span><span>满分</span><span>作答要求</span><span></span>
        </div>
        <button v-for="q in questions" :key="q.question_id" class="q-card"
          @click="$emit('openQuestion', q.question_id)">
          <span class="q-main">
            <span class="q-title">{{ catalogTitle(q) }}</span>
            <span class="q-type">{{ q.sub_type || examLabel }}<span v-if="hasDraft(q.question_id)" class="draft">继续草稿</span></span>
          </span>
          <span class="q-year">{{ q.year || "—" }}</span>
          <span class="q-score">{{ q.full_score }} <small>分</small></span>
          <span class="q-limit">{{ q.word_requirement || "见题干" }}<small v-if="(q.exam_type === 'shenlun_short' || q.exam_type === 'kaoyan_396') && q.scoring_point_count">{{ q.scoring_point_count }} 个{{ q.exam_type === 'kaoyan_396' ? '逻辑漏洞点' : '采分点' }}</small></span>
          <span class="q-arrow" aria-hidden="true">↗</span>
        </button>
      </div>

      <div v-if="questions.length > 0" class="pagination-bar">
        <p v-if="loadError" role="alert">{{ loadError }}</p>
        <button
          v-if="questions.length < totalCount"
          class="btn btn-outline"
          :disabled="loadingMore || loading"
          @click="fetchQuestions(false)"
        >
          {{ loadingMore ? "加载中..." : `加载更多真题（已展示 ${questions.length} / ${totalCount}）` }}
        </button>
        <span v-else class="all-loaded">已显示全部 {{ totalCount }} 道题</span>
      </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import DailyQuoteCard from "../components/DailyQuoteCard.vue";
import IslandLandscape from "../components/IslandLandscape.vue";
import { apiRequest } from "../api/client";
import type { ExamType, QuestionSummary, RegionItem } from "../types";
import { hasDraftForQuestion } from "../utils/reportAdvice";
import { formatQuestionTitle } from "../utils/questionFormat";

defineEmits<{
  (e: "openQuestion", questionId: string): void;
  (e: "openCustom", examType: ExamType): void;
}>();

const tabs: Array<{ label: string; value: ExamType }> = [
  { label: "申论小题", value: "shenlun_short" },
  { label: "申论大作文", value: "shenlun_essay" },
  { label: "考研英语作文", value: "kaoyan_english" },
  { label: "396经综写作", value: "kaoyan_396" },
];

const shortSubTypes = [
  { label: "全部题型", value: "" },
  { label: "归纳概括", value: "归纳概括" },
  { label: "提出对策", value: "提出对策" },
  { label: "综合分析", value: "综合分析" },
  { label: "公文写作", value: "公文写作" },
];

const kaoyanSubTypes = [
  { label: "全部", value: "" },
  { label: "英语一", value: "英语一" },
  { label: "英语二", value: "英语二" },
  { label: "小作文", value: "小作文" },
  { label: "大作文", value: "大作文" },
];

const kaoyan396SubTypes = [
  { label: "全部题型", value: "" },
  { label: "论证有效性分析", value: "论证有效性分析" },
  { label: "论说文", value: "论说文" },
];

const activeType = ref<ExamType>("shenlun_short");
const currentSubTypeOptions = computed(() => {
  if (activeType.value === "kaoyan_english") return kaoyanSubTypes;
  if (activeType.value === "kaoyan_396") return kaoyan396SubTypes;
  return shortSubTypes;
});
const activeRegion = ref("");
const activeSubType = ref("");
const activeYear = ref("");
const yearOptions = ref<number[]>([]);
const keyword = ref("");
const appliedKeyword = ref("");
let latestRequest = 0;
const filtersOpen = ref(false);
const filterSummary = computed(() => [
  activeType.value === "kaoyan_english" || activeType.value === "kaoyan_396" ? "" : activeRegion.value,
  activeSubType.value,
  activeYear.value ? `${activeYear.value}年` : "",
].filter(Boolean).join(" · "));

function catalogTitle(q: QuestionSummary) {
  return formatQuestionTitle(q);
}

const regions = ref<RegionItem[]>([{ label: "全部地区", value: "", count: 0 }]);
const questions = ref<QuestionSummary[]>([]);
const totalCount = ref(0);
const page = ref(1);
const pageSize = 24;
const loading = ref(false);
const loadingMore = ref(false);
const loadError = ref("");

const examLabel = computed(
  () => tabs.find((t) => t.value === activeType.value)?.label || "真题"
);

function hasDraft(qid: string) {
  return hasDraftForQuestion(qid);
}

async function fetchRegions() {
  try {
    const res = await apiRequest<{ items: RegionItem[] }>("/api/questions/regions");
    regions.value = [{ label: "全部地区", value: "", count: 0 }, ...(res.items || [])];
  } catch {
    // 保留默认地区项
  }
}

async function fetchYears() {
  try {
    const res = await apiRequest<{ items: number[] }>(
      `/api/questions/years?exam_type=${encodeURIComponent(activeType.value)}`
    );
    yearOptions.value = res.items || [];
  } catch {
    yearOptions.value = [];
  }
}

async function fetchQuestions(reset = true) {
  if (!reset && (loading.value || loadingMore.value)) return;
  const requestId = ++latestRequest;
  const nextPage = reset ? 1 : page.value + 1;
  loadError.value = "";
  if (reset) {
    loading.value = true;
    loadingMore.value = false;
  } else {
    loadingMore.value = true;
  }

  try {
    const params = new URLSearchParams();
    params.set("exam_type", activeType.value);
    params.set("page", String(nextPage));
    params.set("page_size", String(pageSize));
    if (activeType.value !== "kaoyan_english" && activeType.value !== "kaoyan_396" && activeRegion.value) {
      params.set("region", activeRegion.value);
    }
    if (activeSubType.value) {
      params.set("sub_type", activeSubType.value);
    }
    if (activeYear.value) {
      params.set("year", activeYear.value);
    }
    if (appliedKeyword.value) {
      params.set("keyword", appliedKeyword.value);
    }

    const res = await apiRequest<{ total: number; items: QuestionSummary[] }>(
      `/api/questions?${params.toString()}`
    );
    if (requestId !== latestRequest) return;
    page.value = nextPage;
    totalCount.value = res.total;
    if (reset) {
      questions.value = res.items || [];
    } else {
      questions.value = [...questions.value, ...(res.items || [])];
    }
  } catch (err: any) {
    if (requestId !== latestRequest) return;
    if (reset) questions.value = [];
    loadError.value = err?.message || "真题库加载失败，请稍后重试";
  } finally {
    if (requestId === latestRequest) {
      loading.value = false;
      loadingMore.value = false;
    }
  }
}

function selectTab(type: ExamType) {
  if (activeType.value === type) return;
  activeType.value = type;
  activeSubType.value = "";
  activeYear.value = "";
  fetchYears();
  fetchQuestions(true);
}

function selectRegion(region: string) {
  activeRegion.value = region;
  fetchQuestions(true);
}

function selectSubType(sub: string) {
  activeSubType.value = sub;
  fetchQuestions(true);
}

function selectYear(year: string) {
  activeYear.value = year;
  fetchQuestions(true);
}

function handleSearch() {
  appliedKeyword.value = keyword.value.trim();
  fetchQuestions(true);
}

function resetFilters() {
  activeRegion.value = "";
  activeSubType.value = "";
  activeYear.value = "";
  keyword.value = "";
  handleSearch();
}

onMounted(() => {
  fetchRegions();
  fetchYears();
  fetchQuestions(true);
});
</script>

<style scoped>
.library-page { max-width: var(--catalog-max); padding: 26px var(--catalog-gutter) 64px; margin-inline: auto; }
.catalog-hero { position: relative; isolation: isolate; overflow: hidden; display: flex; align-items: center; min-height: 205px; padding: 34px 44px; background: linear-gradient(125deg, #fbf9f4 0%, #f1ece1 100%); color: var(--ink-primary); border: 1px solid #e1dacb; border-radius: 14px; box-shadow: 0 2px 10px rgba(26, 28, 27, 0.03); }
.hero-content { position: relative; z-index: 1; width: min(44%, 465px); }
.hero-title-row { display: inline-flex; align-items: flex-start; gap: 10px; margin-bottom: 10px; }
.catalog-hero h1 { margin: 0; font: 650 clamp(36px, 3.2vw, 52px)/1.13 var(--font-serif); letter-spacing: .04em; color: #191d1b; }
.hero-subtitle { margin: 0 0 18px; font-size: 13.5px; color: #6b6860; letter-spacing: 0.02em; }
.vermilion-seal { display: inline-flex; align-items: center; justify-content: center; margin-top: 6px; padding: 3px 7px; border: 1.5px solid #c63829; border-radius: 4px; color: #c63829; background: rgba(198, 56, 41, 0.05); font-family: var(--font-serif); font-size: 12px; font-weight: 700; line-height: 1.1; letter-spacing: 0.08em; white-space: nowrap; user-select: none; }
.hero-art { position: absolute; right: 1%; top: -7%; height: 114%; width: 55%; pointer-events: none; }
.search-wrap { display: flex; gap: 10px; align-items: center; min-height: 46px; padding: 4px 5px 4px 16px; border-radius: 8px; background: #ffffff; border: 1px solid rgba(25, 29, 27, 0.12); box-shadow: 0 2px 8px rgba(25, 29, 27, 0.04); }
.magnifier { position: relative; flex: 0 0 14px; width: 14px; height: 14px; border: 1.6px solid #6b726e; border-radius: 50%; margin-right: 2px; }
.magnifier::after { content: ""; position: absolute; width: 6px; height: 1.6px; background: #6b726e; right: -4px; bottom: -2px; transform: rotate(48deg); }
.search-wrap:focus-within { border-color: var(--brand); box-shadow: 0 0 0 3px rgba(27, 77, 62, 0.1); }
.search-wrap input { border: 0; outline: 0; background: transparent; color: var(--ink-primary); font-size: 15px; flex: 1; min-width: 0; }
.search-btn, .search-clear { border: 0; border-radius: 6px; padding: 8px 15px; background: #1e2421; color: #faf9f6; font-weight: 500; transition: background 0.15s ease; }
.search-btn:hover { background: #111513; }
.search-clear { background: transparent; color: #6b726e; padding-inline: 4px; }
.catalog-layout { display: grid; grid-template-columns: clamp(185px, 15vw, 244px) minmax(0, 1fr); gap: clamp(22px, 2.4vw, 42px); align-items: start; margin-top: 28px; }
.library-sidebar { padding: 18px 18px 24px; border: 1px solid #e4dfd3; border-radius: 10px; background: #f5f2ea; }
.group-title { margin: 0 0 12px; font-size: 12.5px; font-weight: 600; color: #78746c; letter-spacing: 0.02em; }
.exam-tabs { display: grid; gap: 4px; }
.exam-tab { display: flex; align-items: center; gap: 12px; padding: 11px 12px; text-align: left; font-weight: 500; font-size: 14.5px; border: 1px solid transparent; border-radius: 7px; color: #4f4e49; background: transparent; transition: all 0.15s ease; }
.exam-tab[aria-pressed="true"] { border-color: #ded8ca; background: #ffffff; color: #191b1a; font-weight: 650; box-shadow: 0 1px 3px rgba(26, 28, 27, 0.05); }
.exam-tab:hover:not([aria-pressed="true"]) { background: #ece8de; color: #191b1a; }
.book-mark { width: 14px; height: 17px; flex: none; border: 1.5px solid currentColor; border-left-width: 3px; border-radius: 2px; position: relative; }
.book-mark::after { content: ""; position: absolute; top: 4px; left: 2px; right: 2px; height: 1px; background: currentColor; }
.book-mark[data-exam="shenlun_essay"]::after { box-shadow: 0 3px currentColor; }
.book-mark[data-exam="kaoyan_english"]::after { content: "A"; top: -1px; left: 1px; background: transparent; font: 600 11px/16px Georgia, serif; }
.book-mark[data-exam="kaoyan_396"]::after { content: "经"; top: -1px; left: 0px; background: transparent; font: 700 9px/16px var(--font-serif); }
.filter-panel { display: grid; gap: 12px; border-top: 1px solid #e3ddd1; margin-top: 20px; padding-top: 20px; }
.filter-panel .group-title { margin: 0; }
.filter-panel label { display: grid; gap: 5px; font-size: 12px; color: #6e6b63; }
.filter-panel select { width: 100%; min-height: 39px; padding: 5px 8px; color: #1f2220; background: #fff; border: 1px solid #dad4c7; border-radius: 6px; font-size: 14px; }
.reset-link, .filter-trigger { border: 0; padding: 5px 0; color: var(--brand); background: transparent; text-align: left; }
.filter-trigger { display: none; }
.results-section { min-width: 0; border: 1px solid #e4dfd3; border-radius: 10px; overflow: hidden; background: white; }
.results-top, .results-heading { display: flex; align-items: center; gap: 12px; }
.results-top { min-height: 68px; padding: 10px 22px; justify-content: space-between; }
.results-heading h2 { margin: 0; font-size: 21px; line-height: 1.3; font-weight: 650; }
.results-heading > span { border-left: 1px solid #e0dad0; padding-left: 12px; color: #78746c; font-size: 13px; }
.own-question { border: 0; border-radius: 7px; padding: 9px 15px; background: var(--brand); color: #faf8f4; font-size: 13.5px; font-weight: 550; white-space: nowrap; transition: background 0.15s ease; }
.own-question:hover { background: var(--brand-hover); }
.columns, .q-card { display: grid; grid-template-columns: minmax(0,1fr) minmax(50px,.19fr) minmax(55px,.19fr) minmax(104px,.37fr) 24px; align-items: center; gap: 14px; }
.columns { padding: 9px 22px; font-size: 12px; color: #78746c; background: #f8f6f0; border-block: 1px solid #eae5da; }
.q-card { width: 100%; min-height: 78px; padding: 13px 22px; background: #fff; border: 0; border-bottom: 1px solid #eeeae0; text-align: left; color: var(--ink-primary); transition: background 0.14s ease; }
.q-card:hover, .q-card:focus-visible { background: #f9f7f2; }
.q-card:focus-visible { outline: 2px solid var(--brand); outline-offset: -3px; }
.q-main, .q-limit { display: grid; gap: 4px; }
.q-title { font-weight: 600; font-size: 16.5px; line-height: 1.5; overflow-wrap: anywhere; }
.q-type, .q-limit, .q-year, .q-score small { color: #75726a; font-size: 13px; }
.q-limit small { font-size: 12px; }
.q-year, .q-score { font-variant-numeric: tabular-nums; }
.q-score { font-size: 16px; }
.draft { color: var(--red-pen); margin-left: 10px; font-weight: 600; }
.q-arrow { justify-self: end; font-size: 16px; color: #8c887f; }
.pagination-bar, .state-box { padding: 24px 16px; text-align: center; color: #75726a; }
@media (max-width: 900px) {
  .library-page { padding-top: 16px; }
  .catalog-hero { min-height: 163px; padding: 23px 25px; }
  .hero-content { width: 52%; }
  .hero-art { right: -5%; }
  .catalog-layout { display: block; margin-top: 16px; }
  .library-sidebar { border: 0; background: transparent; padding: 0; display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 4px; margin-bottom: 10px; }
  .library-sidebar > .group-title, .book-mark, .filter-panel, .filter-panel .group-title { display: none; }
  .exam-tabs { display: flex; flex-wrap: wrap; gap: 2px; }
  .exam-tab { padding: 8px 11px; font-size: 14px; }
  .filter-trigger { display: inline-block; min-height: 42px; font-size: 13px; }
  .filter-panel.open { display: flex; width: 100%; flex-wrap: wrap; align-items: end; margin: 0 0 8px; padding: 12px; background: #f3f5ef; }
  .filter-panel label { flex: 1; }
}
@media (max-width: 640px) {
  .catalog-hero { padding: 20px; min-height: 143px; border-radius: 9px; }
  .catalog-hero h1 { font-size: 33px; margin-bottom: 20px; }
  .hero-content { width: 100%; }
  .hero-art { right: -1%; top: 1px; width: 46%; height: 78px; }
  .search-wrap { min-height: 42px; }
  .search-wrap input { font-size: 16px; }
  .exam-tab { padding: 8px 7px; font-size: 13px; }
  .filter-trigger { font-size: 12px; }
  .results-top { padding: 12px; gap: 6px; min-height: 58px; }
  .results-heading { gap: 6px; }
  .results-heading h2 { font-size: 17px; }
  .results-heading > span { font-size: 12px; padding-left: 6px; }
  .own-question { padding: 9px; font-size: 13px; }
  .columns { display: none; }
  .q-card { grid-template-columns: auto auto minmax(0,1fr) 16px; gap: 3px 10px; min-height: 80px; padding: 12px 14px; border-top: 1px solid #e5e8e3; border-bottom: 0; }
  .q-main { grid-column: 1 / 4; gap: 2px; }
  .q-title { font-size: 16px; }
  .q-arrow { grid-column: 4; grid-row: 1; }
  .q-year, .q-score, .q-limit { font-size: 12px; color: #59695e; }
  .q-limit { display: flex; flex-wrap: wrap; gap: 3px 8px; }
}
</style>
