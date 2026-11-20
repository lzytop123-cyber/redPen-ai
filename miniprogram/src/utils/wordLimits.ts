export function formatWordLimits(minimum: number, maximum: number, examType?: string): string {
  const unit = examType === "kaoyan_english" ? "词" : "字";
  if (minimum && maximum) return `${minimum}～${maximum} ${unit}`;
  if (maximum) return `不超过 ${maximum} ${unit}`;
  if (minimum) return `不少于 ${minimum} ${unit}`;
  return "";
}
