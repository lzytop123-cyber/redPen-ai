export function formatWordLimits(minimum: number, maximum: number): string {
  if (minimum && maximum) return `${minimum}～${maximum} 字`;
  if (maximum) return `不超过 ${maximum} 字`;
  if (minimum) return `不少于 ${minimum} 字`;
  return "";
}
