import test from "node:test";
import assert from "node:assert/strict";
import { selectReportAdvice, formatReportWarning } from "../src/utils/reportAdvice.ts";

test("申论先补漏点，材料引用与作答原文区分", () => {
  const advice = selectReportAdvice({ shenlun_detail: { point_matches: [
    { point_id: "P1", status: "partial", evidence_quote: "我的原文", comment: "补充主体" },
    { point_id: "P2", status: "miss", keyword: "资金共筹", material_quote: "居民和社区共同出资", comment: "写明出资主体" },
  ] } });
  assert.equal(advice.target, "point-1");
  assert.match(advice.title, /资金共筹/);
  assert.equal(advice.text, "写明出资主体");
  assert.match(advice.cue, /材料.*居民和社区共同出资/);
});

test("旧报告没有材料线索时保留部分命中评语", () => {
  const advice = selectReportAdvice({ shenlun_detail: { point_matches: [
    { point_id: "P3", status: "partial", evidence_quote: "原稿里的话", comment: "补上谁来出资" },
  ] } });
  assert.match(advice.title, /P3/);
  assert.equal(advice.text, "补上谁来出资");
  assert.doesNotMatch(advice.cue || "", /材料/);
});

test("只选能定位且有改写建议的扣分句，并引用真实原句", () => {
  const advice = selectReportAdvice({
    exam_type: "kaoyan_english",
    sentences: [{ sentence_id: "S1", text: "I likes tea." }],
    annotations: [
      { sentence_id: "S1", severity: "positive", suggestion: "Great!" },
      { sentence_id: "S3", severity: "high", suggestion: "Cannot locate" },
      { sentence_id: "S1", severity: "high", suggestion: " " },
      { sentence_id: "S1", severity: "medium", original_excerpt: "invalid excerpt", suggestion: "I like tea." },
    ],
  });
  assert.equal(advice.target, "sentence-S1");
  assert.match(advice.cue, /I likes tea\./);
  assert.match(advice.text, /I like tea\./);
});

test("无可用批注时选择较低评分维度，再回退到升格范文或原句", () => {
  const dimensions = [{ dimension: "内容", level: 4, comment: "补充背景" }, { dimension: "衔接", level: 2, comment: "说明转折的原因" }];
  assert.equal(selectReportAdvice({ shenlun_essay_detail: { dimensions } }).target, "dimension-1");
  assert.equal(selectReportAdvice({ upgraded_answer: "A better answer" }).target, "upgrade");
  assert.equal(selectReportAdvice({ sentences: [{ sentence_id: "S1", text: "My answer." }] }).target, "sentence-S1");
  assert.ok(selectReportAdvice({}).text);
});

test("历史英语报告的字数警告按词显示，申论保留字数", () => {
  const warning = "未达最少字数要求，差 3 字（当前 97 / 最低 100），会触发字数扣分！";
  assert.equal(formatReportWarning(warning, true), "未达最少词数要求，差 3 词（当前 97 / 最低 100），会触发词数扣分！");
  assert.equal(formatReportWarning(warning, false), warning);
});
