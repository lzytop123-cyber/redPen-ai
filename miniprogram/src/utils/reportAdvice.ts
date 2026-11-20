interface PointMatch {
  point_id: string;
  status: string;
  comment: string;
  keyword?: string;
  material_quote?: string;
  material_section?: string;
}

interface Dimension {
  dimension: string;
  level: number;
  comment: string;
}

interface AdviceReport {
  exam_type?: string;
  shenlun_detail?: { point_matches?: PointMatch[] };
  shenlun_essay_detail?: { dimensions?: Dimension[] };
  kaoyan_detail?: { dimensions?: Dimension[] };
  annotations?: { sentence_id: string; severity: string; suggestion: string }[];
  sentences?: { sentence_id: string; text: string }[];
  key_improvements?: string[];
  upgraded_answer?: string;
}

interface ReportAdvice {
  title: string;
  cue?: string;
  text: string;
  target?: string;
  link?: string;
}

export function selectReportAdvice(report: AdviceReport): ReportAdvice {
  const points = report.shenlun_detail?.point_matches || [];
  const point = points.find(p => p.status === "miss") || points.find(p => p.status === "partial");
  if (point) {
    return {
      title: `${point.status === "miss" ? "补上" : "补全"}采分点 · ${point.keyword || point.point_id}`,
      cue: point.material_quote ? `${point.material_section || "材料原文"}：“${point.material_quote}”` : undefined,
      text: point.comment || "在答案中单列这一点，写明材料里的主体和做法。",
      target: `point-${points.indexOf(point)}`,
      link: "查看采分点",
    };
  }

  const sentences = report.sentences || [];
  const annotations = report.annotations || [];
  for (const severity of ["high", "medium", "low"]) {
    const annotation = annotations.find(a => a.severity === severity && a.suggestion?.trim()
      && sentences.some(s => s.sentence_id === a.sentence_id && s.text?.trim()));
    if (annotation) {
      const sentence = sentences.find(s => s.sentence_id === annotation.sentence_id)!;
      return {
        title: `改写原句 · ${sentence.sentence_id}`,
        cue: `你的原句：${sentence.text}`,
        text: `建议改写：${annotation.suggestion}`,
        target: `sentence-${sentence.sentence_id}`,
        link: "查看逐句批注",
      };
    }
  }

  const dimensions = (report.shenlun_essay_detail || report.kaoyan_detail)?.dimensions || [];
  const weakest = dimensions.reduce<Dimension | undefined>((lowest, d) =>
    !lowest || d.level < lowest.level ? d : lowest, undefined);
  if (weakest) {
    return {
      title: `复核评分维度 · ${weakest.dimension}`,
      text: weakest.comment || "对照这一维度的要求，挑出原稿中最需要修改的一句。",
      target: `dimension-${dimensions.indexOf(weakest)}`,
      link: "查看维度点评",
    };
  }

  const improvement = report.key_improvements?.find(item => item.trim());
  if (improvement || report.upgraded_answer) {
    return {
      title: "对照升格版改一处",
      text: improvement || "找出升格版中写得更具体的一句，试着用自己的话重写。",
      target: "upgrade",
      link: "查看升格版",
    };
  }
  const sentence = sentences.find(s => s.text?.trim());
  return {
    title: "复查原稿",
    text: "选出一句，圈出最想表达的意思，再删去重复的词。",
    cue: sentence ? `你的原句：${sentence.text}` : undefined,
    target: sentence ? `sentence-${sentence.sentence_id}` : undefined,
    link: sentence ? "查看原句" : undefined,
  };
}

export function formatReportWarning(warning: string | null | undefined, english: boolean): string {
  if (!warning) return "";
  return english ? warning.replace(/字数/g, "词数").replace(/(\d\s*)字/g, "$1词") : warning;
}
