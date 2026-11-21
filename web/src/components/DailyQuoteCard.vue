<template>
  <section class="cal-card" aria-label="每日写作日签">
    <div class="cal-top">
      <div class="cal-date">
        <span class="cal-day">{{ dayNum }}</span>
        <div class="cal-ym">
          <span class="cal-month">{{ monthLabel }}</span>
          <span class="cal-week">{{ weekLabel }}</span>
        </div>
      </div>
      <button
        type="button"
        class="cal-refresh"
        :disabled="fetching"
        title="换一签"
        aria-label="换一签"
        @click="nextQuote"
      >
        ↻
      </button>
    </div>

    <!-- 目标考试倒计时（点击可自定义目标与日期） -->
    <div class="countdown-bar" @click="editingCountdown = !editingCountdown" title="点击修改目标考试与日期">
      <span class="cd-label">距 {{ countdown.name }}</span>
      <span class="cd-days">
        <template v-if="daysLeft > 0"><strong>{{ daysLeft }}</strong> 天</template>
        <template v-else-if="daysLeft === 0"><strong>就在今天</strong></template>
        <template v-else>已过 {{ Math.abs(daysLeft) }} 天</template>
      </span>
    </div>

    <div v-if="editingCountdown" class="cd-editor">
      <div class="cd-presets">
        <button
          v-for="p in PRESETS"
          :key="p.name"
          type="button"
          class="cd-preset-btn"
          @click="applyPreset(p)"
        >
          {{ p.name }}
        </button>
      </div>
      <input
        v-model="draftName"
        type="text"
        class="cd-input"
        maxlength="16"
        placeholder="考试名称，如 省考"
      />
      <input v-model="draftDate" type="date" class="cd-input" />
      <div class="cd-editor-actions">
        <button type="button" class="cd-cancel" @click="editingCountdown = false">取消</button>
        <button type="button" class="cd-save" @click="saveCountdown">保存</button>
      </div>
    </div>

    <div class="cal-rule"></div>

    <blockquote
      class="cal-quote"
      :class="{ 'is-en': isEnglish }"
      title="点击复制这句金句"
      @click="copyQuote"
    >
      {{ currentQuote.text }}
    </blockquote>

    <div class="cal-foot">
      <span class="cal-from">{{ currentQuote.from }}</span>
      <span v-if="currentQuote.topic" class="cal-topic">{{ currentQuote.topic }}</span>
    </div>

    <div class="cal-hint">
      <span class="cal-copy-tip" @click="copyQuote">点击金句复制</span>
      <button type="button" class="cal-src-toggle" @click="toggleSource">
        {{ sourceMode === "exam" ? "切换诗词" : "回到金句" }}
      </button>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { showToast } from "../stores/auth";

interface QuoteItem {
  text: string;
  from: string;
  topic?: string;
}

interface CountdownConfig {
  name: string;
  date: string; // YYYY-MM-DD
}

const COUNTDOWN_KEY = "zxd_exam_countdown";

// 固定按北京时间（Asia/Shanghai）解析当日日期，避免海外/UTC 浏览器显示昨天
function getBeijingDateParts() {
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "numeric",
    day: "numeric",
    weekday: "short",
  }).formatToParts(new Date());
  const get = (type: string) => parts.find((p) => p.type === type)?.value || "";
  return {
    year: Number(get("year")) || new Date().getFullYear(),
    month: Number(get("month")) || new Date().getMonth() + 1,
    day: Number(get("day")) || new Date().getDate(),
    weekday: get("weekday") || "今日",
  };
}

const bjNow = getBeijingDateParts();
const curYear = bjNow.year;

function nextDate(month: number, day: number): string {
  const todayStamp = Date.UTC(bjNow.year, bjNow.month - 1, bjNow.day);
  const candidateStamp = Date.UTC(curYear, month - 1, day);
  const year = candidateStamp < todayStamp ? curYear + 1 : curYear;
  return `${year}-${String(month).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
}

const PRESETS: CountdownConfig[] = [
  { name: "国考", date: nextDate(11, 29) },
  { name: "考研", date: nextDate(12, 19) },
  { name: "省考联考", date: nextDate(3, 15) },
];

const countdown = ref<CountdownConfig>(PRESETS[1]);
const editingCountdown = ref(false);
const draftName = ref("");
const draftDate = ref("");

function loadCountdown() {
  try {
    const raw = localStorage.getItem(COUNTDOWN_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (parsed?.name && parsed?.date) {
        countdown.value = parsed;
      }
    }
  } catch {
    // ignore
  }
  draftName.value = countdown.value.name;
  draftDate.value = countdown.value.date;
}

function applyPreset(p: CountdownConfig) {
  draftName.value = p.name;
  draftDate.value = p.date;
}

function saveCountdown() {
  const name = draftName.value.trim() || "目标考试";
  const date = draftDate.value || PRESETS[0].date;
  countdown.value = { name, date };
  try {
    localStorage.setItem(COUNTDOWN_KEY, JSON.stringify(countdown.value));
  } catch {
    // ignore
  }
  editingCountdown.value = false;
  showToast(`已更新倒计时：距 ${name}`, "success");
}

const daysLeft = computed(() => {
  const [y, m, d] = countdown.value.date.split("-").map(Number);
  if (!y || !m || !d) return 0;
  const target = Date.UTC(y, m - 1, d);
  const today = Date.UTC(bjNow.year, bjNow.month - 1, bjNow.day);
  return Math.round((target - today) / 86400000);
});

const EXAM_QUOTES: QuoteItem[] = [
  { text: "知屋漏者在宇下，知政失者在草野。", from: "王充《论衡》", topic: "基层治理" },
  { text: "治政之要在于安民，安民之道在于察其疾苦。", from: "张居正", topic: "民生保障" },
  { text: "不谋万世者，不足谋一时；不谋全局者，不足谋一域。", from: "陈澹然《寤言》", topic: "系统思维" },
  { text: "道虽迩，不行不至；事虽小，不为不成。", from: "《荀子·修身》", topic: "实干笃行" },
  { text: "善治病者，必医其受病之处；善救弊者，必塞其起弊之源。", from: "欧阳修", topic: "标本兼治" },
  { text: "明者因时而变，知者随事而制。", from: "桓宽《盐铁论》", topic: "改革创新" },
  { text: "致天下之治者在人才，成天下之才者在教化。", from: "胡瑗", topic: "人才教育" },
  { text: "取之有度，用之有节，则常足。", from: "《资治通鉴》", topic: "生态文明" },
  { text: "法立，有犯而必施；令出，唯行而不返。", from: "王勃", topic: "依法行政" },
  { text: "涉浅水者得鱼虾，涉深水者得蛟龙。", from: "人民日报", topic: "调查研究" },
  { text: "志不求易者成，事不避难者进。", from: "《后汉书》", topic: "青年担当" },
  { text: "一枝一叶总关情，民生无小事。", from: "郑板桥", topic: "为民情怀" },
  { text: "求木之长者，必固其根本；欲流之远者，必浚其泉源。", from: "魏征", topic: "文化根脉" },
  { text: "苟日新，日日新，又日新。", from: "《礼记·大学》", topic: "守正创新" },
  { text: "功崇惟志，业广惟勤。", from: "《尚书·周官》", topic: "奋斗实干" },
  { text: "合抱之木，生于毫末；九层之台，起于累土。", from: "《老子》", topic: "久久为功" },
  { text: "Excellence is not an act, but a habit.", from: "Will Durant", topic: "英语 · 坚持" },
  { text: "In the middle of difficulty lies opportunity.", from: "Albert Einstein", topic: "英语 · 逆境" },
  { text: "Technology is a useful servant but a dangerous master.", from: "C. L. Lange", topic: "英语 · 科技" },
];

const dayNum = String(bjNow.day).padStart(2, "0");
const MONTHS = ["一月", "二月", "三月", "四月", "五月", "六月", "七月", "八月", "九月", "十月", "十一月", "十二月"];
const monthLabel = MONTHS[bjNow.month - 1] || `${bjNow.month}月`;
const weekLabel = bjNow.weekday;

const sourceMode = ref<"exam" | "hitokoto">("exam");
const examIndex = ref(0);
const fetching = ref(false);
const currentQuote = ref<QuoteItem>(EXAM_QUOTES[0]);

const isEnglish = computed(() => /^[A-Za-z]/.test(currentQuote.value.text));

function pickDailyExamQuote() {
  const cnCount = 16;
  const daySeed = Math.floor(Date.now() / 86400000);
  examIndex.value = daySeed % cnCount;
  currentQuote.value = EXAM_QUOTES[examIndex.value];
}

async function fetchHitokoto() {
  fetching.value = true;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 3500);
  try {
    const resp = await fetch("https://v1.hitokoto.cn/?c=d&c=i&c=k&encode=json", {
      signal: controller.signal,
    });
    if (!resp.ok) throw new Error("network");
    const data = await resp.json();
    if (data?.hitokoto) {
      currentQuote.value = {
        text: String(data.hitokoto).trim(),
        from: data.from_who ? `${data.from_who}《${data.from || "一言"}》` : (data.from || "一言"),
        topic: "诗词一言",
      };
      return;
    }
    throw new Error("empty");
  } catch {
    examIndex.value = (examIndex.value + 1) % EXAM_QUOTES.length;
    currentQuote.value = EXAM_QUOTES[examIndex.value];
  } finally {
    window.clearTimeout(timer);
    fetching.value = false;
  }
}

function toggleSource() {
  if (sourceMode.value === "exam") {
    sourceMode.value = "hitokoto";
    fetchHitokoto();
  } else {
    sourceMode.value = "exam";
    currentQuote.value = EXAM_QUOTES[examIndex.value];
  }
}

function nextQuote() {
  if (sourceMode.value === "hitokoto") {
    fetchHitokoto();
    return;
  }
  examIndex.value = (examIndex.value + 1) % EXAM_QUOTES.length;
  currentQuote.value = EXAM_QUOTES[examIndex.value];
}

async function copyQuote() {
  const text = `${currentQuote.value.text} —— ${currentQuote.value.from}`;
  try {
    await navigator.clipboard.writeText(text);
    showToast("金句已复制，可直接用于作文积累", "success");
  } catch {
    showToast("复制失败，请手动选中复制", "warn");
  }
}

onMounted(() => {
  loadCountdown();
  pickDailyExamQuote();
});
</script>

<style scoped>
.cal-card {
  margin-top: 14px;
  padding: 18px 18px 15px;
  border: 1px solid #e2dcd0;
  border-radius: 10px;
  background: #fcfaf5;
  box-shadow: 0 1px 4px rgba(26, 28, 27, 0.03);
}

.cal-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
}

.cal-date {
  display: flex;
  align-items: baseline;
  gap: 8px;
}

.cal-day {
  font-family: var(--font-serif);
  font-size: 32px;
  font-weight: 700;
  line-height: 1;
  color: var(--ink-primary);
  letter-spacing: -0.02em;
}

.cal-ym {
  display: flex;
  flex-direction: column;
  gap: 1px;
  line-height: 1.25;
}

.cal-month {
  font-size: 11.5px;
  font-weight: 600;
  color: var(--ink-secondary);
}

.cal-week {
  font-size: 11px;
  color: var(--ink-muted);
}

.cal-refresh {
  width: 26px;
  height: 26px;
  border: 1px solid transparent;
  border-radius: 6px;
  background: transparent;
  color: var(--ink-muted);
  font-size: 14px;
  line-height: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.cal-refresh:hover:not(:disabled) {
  background: #f0ece2;
  color: var(--ink-primary);
}

/* 考试倒计时条 */
.countdown-bar {
  margin-top: 10px;
  padding: 6px 9px;
  border-radius: 6px;
  background: #f3efe6;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11.5px;
  color: var(--ink-secondary);
  cursor: pointer;
  transition: background 0.14s ease;
}

.countdown-bar:hover {
  background: #ebe5d8;
}

.cd-label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cd-days {
  flex-shrink: 0;
  color: var(--ink-muted);
}

.cd-days strong {
  font-family: var(--font-serif);
  font-size: 14px;
  font-weight: 700;
  color: var(--red-pen);
  margin: 0 1px;
}

.cd-editor {
  margin-top: 8px;
  padding: 10px;
  border-radius: 7px;
  background: #ffffff;
  border: 1px solid #e2dcd0;
  display: grid;
  gap: 7px;
}

.cd-presets {
  display: flex;
  gap: 5px;
  flex-wrap: wrap;
}

.cd-preset-btn {
  border: 1px solid #e2dcd0;
  background: #faf8f3;
  color: var(--ink-secondary);
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 99px;
}

.cd-preset-btn:hover {
  border-color: var(--brand);
  color: var(--ink-primary);
}

.cd-input {
  width: 100%;
  padding: 5px 8px;
  border: 1px solid #dcd5c7;
  border-radius: 5px;
  font-size: 12px;
  background: #fcfaf5;
  color: var(--ink-primary);
  outline: none;
}

.cd-input:focus {
  border-color: var(--brand);
  background: #fff;
}

.cd-editor-actions {
  display: flex;
  justify-content: flex-end;
  gap: 6px;
}

.cd-cancel,
.cd-save {
  border: 0;
  border-radius: 5px;
  font-size: 11.5px;
  padding: 4px 10px;
}

.cd-cancel {
  background: transparent;
  color: var(--ink-muted);
}

.cd-save {
  background: var(--brand);
  color: #faf8f4;
}

.cal-rule {
  position: relative;
  height: 1px;
  background: #e8e2d5;
  margin: 12px 0 13px;
}

.cal-rule::before {
  content: "";
  position: absolute;
  left: 0;
  top: -0.5px;
  width: 22px;
  height: 2px;
  background: var(--red-pen);
  border-radius: 2px;
}

.cal-quote {
  margin: 0;
  font-family: var(--font-serif);
  font-size: 14px;
  line-height: 1.75;
  color: var(--ink-primary);
  cursor: pointer;
  transition: color 0.15s ease;
}

.cal-quote:hover {
  color: #000;
}

.cal-quote.is-en {
  font-family: Georgia, "Times New Roman", serif;
  font-style: italic;
  font-size: 13.5px;
  line-height: 1.65;
}

.cal-foot {
  margin-top: 10px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  font-size: 11.5px;
  color: var(--ink-muted);
}

.cal-from {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cal-topic {
  flex-shrink: 0;
  font-size: 10.5px;
  color: var(--ink-secondary);
  background: #f0ece2;
  padding: 1px 6px;
  border-radius: 4px;
}

.cal-hint {
  margin-top: 12px;
  padding-top: 9px;
  border-top: 1px dashed #e6e0d3;
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: var(--ink-faint);
}

.cal-copy-tip {
  cursor: pointer;
}

.cal-copy-tip:hover {
  color: var(--ink-secondary);
}

.cal-src-toggle {
  border: 0;
  background: transparent;
  padding: 0;
  font-size: 11px;
  color: var(--ink-muted);
}

.cal-src-toggle:hover {
  color: var(--ink-primary);
  text-decoration: underline;
}

@media (max-width: 900px) {
  .cal-card {
    display: none;
  }
}
</style>
