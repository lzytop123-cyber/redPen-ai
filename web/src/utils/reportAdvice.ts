import type { GradingReport } from "../types";

export interface ReportAdvice {
  title: string;
  cue?: string;
  text: string;
  target?: string;
  link?: string;
}

export function selectReportAdvice(report: Partial<GradingReport>): ReportAdvice {
  const points = report.shenlun_detail?.point_matches || [];
  const point = points.find((p) => p.status === "miss") || points.find((p) => p.status === "partial");
  if (point) {
    return {
      title: `${point.status === "miss" ? "补上" : "补全"}采分点 · ${point.keyword || point.point_id}`,
      cue: point.material_quote
        ? `${point.material_section || "材料原文"}：“${point.material_quote}”`
        : undefined,
      text: point.comment || "在答案中单列这一点，写明材料里的主体和做法。",
      target: `point-${points.indexOf(point)}`,
      link: "定位采分点",
    };
  }

  const sentences = report.sentences || [];
  const annotations = report.annotations || [];
  for (const severity of ["high", "medium", "low"]) {
    const annotation = annotations.find(
      (a) =>
        a.severity === severity &&
        a.suggestion?.trim() &&
        sentences.some((s) => s.sentence_id === a.sentence_id && s.text?.trim())
    );
    if (annotation) {
      const sentence = sentences.find((s) => s.sentence_id === annotation.sentence_id)!;
      return {
        title: `改写原句 · ${sentence.sentence_id}`,
        cue: `你的原句：${sentence.text}`,
        text: `建议改写：${annotation.suggestion}`,
        target: `sentence-${sentence.sentence_id}`,
        link: "定位逐句批注",
      };
    }
  }

  const dimensions = (report.shenlun_essay_detail || report.kaoyan_detail)?.dimensions || [];
  const weakest = dimensions.reduce<(typeof dimensions)[number] | undefined>(
    (lowest, d) => (!lowest || d.level < lowest.level ? d : lowest),
    undefined
  );
  if (weakest) {
    return {
      title: `重点突破评分维度 · ${weakest.dimension}`,
      text: weakest.comment || "对照这一维度的要求，挑出原稿中最需要修改的一句进行精修。",
      target: `dimension-${dimensions.indexOf(weakest)}`,
      link: "定位维度点评",
    };
  }

  const improvement = report.key_improvements?.find((item) => item.trim());
  if (improvement || report.upgraded_answer) {
    return {
      title: "对照参考改写，修改一处",
      text: improvement || "找出参考改写中写得更具体的一句，试着用自己的话重写一遍。",
      target: "upgrade",
      link: "查看参考改写",
    };
  }

  return {
    title: "复查原稿表达",
    text: "逐句通读原稿，删去口语化和重复修饰，让核心踩分点更突出。",
  };
}

export function formatReportWarning(
  warning: string | null | undefined,
  english: boolean
): string {
  if (!warning) return "";
  return english ? warning.replace(/字数/g, "词数").replace(/(\d\s*)字/g, "$1词") : warning;
}

export function formatWordLimits(minimum: number, maximum: number, examType?: string): string {
  const unit = examType === "kaoyan_english" ? "词" : "字";
  if (minimum && maximum) return `${minimum}～${maximum} ${unit}`;
  if (maximum) return `不超过 ${maximum} ${unit}`;
  if (minimum) return `不少于 ${minimum} ${unit}`;
  return "";
}

export function draftStorageKey(qid: string, customType: string, fromTask = ""): string {
  if (fromTask) return `zxd_draft:rewrite:${qid}:${fromTask}`;
  return qid ? `zxd_draft:q:${qid}` : `zxd_draft:custom:${customType}`;
}

export interface SavedDraft {
  answer: string;
  prompt: string;
  material: string;
  updatedAt?: number;
}

export function readDraft(key: string): SavedDraft | null {
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && (parsed.answer || parsed.prompt || parsed.material)) {
      return parsed as SavedDraft;
    }
    return null;
  } catch {
    return null;
  }
}

export function hasDraftForQuestion(qid: string): boolean {
  const d = readDraft(draftStorageKey(qid, ""));
  return Boolean(d && d.answer.trim().length > 0);
}
