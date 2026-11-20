export interface WritingDraft {
  answer: string;
  prompt: string;
  material: string;
}

export function draftKey(qid: string, examType = "", sourceTask = ""): string {
  if (sourceTask) return `writing:revision:${sourceTask}`;
  if (qid) return `writing:question:${qid}`;
  return `writing:custom:${examType}`;
}

export function readDraft(key: string): WritingDraft | null {
  const saved = uni.getStorageSync(key);
  if (!saved || typeof saved.answer !== "string") return null;
  return {
    answer: saved.answer,
    prompt: typeof saved.prompt === "string" ? saved.prompt : "",
    material: typeof saved.material === "string" ? saved.material : "",
  };
}

export function hasDraft(qid: string): boolean {
  return Boolean(readDraft(draftKey(qid))?.answer.trim());
}
