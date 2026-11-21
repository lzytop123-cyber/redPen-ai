import type { QuestionSummary } from "../types";

/**
 * 统一格式化真题显示标题（列表页与作答页共用）：
 * 去掉末尾重复的【题型】、重复的卷号前缀和重复年份。
 */
export function formatQuestionTitle(q: Pick<QuestionSummary, "title" | "sub_type" | "paper" | "year">): string {
  const suffix = `【${q.sub_type}】`;
  let title = q.sub_type && q.title.endsWith(suffix) ? q.title.slice(0, -suffix.length) : q.title;
  const prefix = `${q.paper} (`;
  if (q.paper && title.startsWith(prefix) && title.includes(") 第")) {
    title = title.slice(prefix.length).replace(") 第", " · 第");
  }
  if (q.year && title.startsWith(`${q.year}年`)) {
    title = title.slice(String(q.year).length + 1);
  }
  return title.trim() || q.title;
}
