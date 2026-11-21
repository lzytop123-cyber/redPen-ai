export type ExamType = "shenlun_short" | "shenlun_essay" | "kaoyan_english";

export interface UserInfo {
  user_id: number;
  username?: string | null;
  nickname: string;
  free_quota: number;
  paid_quota: number;
  is_vip: boolean;
  vip_expire_at?: string | null;
}

export interface RegionItem {
  label: string;
  value: string;
  count: number;
}

export interface QuestionSummary {
  question_id: string;
  exam_type: ExamType;
  title: string;
  year: number;
  paper: string;
  sub_type: string;
  full_score: number;
  min_words: number;
  max_words: number;
  word_requirement: string;
  scoring_point_count: number;
}

export interface QuestionDetail extends QuestionSummary {
  prompt: string;
  material_summary: string;
}

export interface PointMatch {
  point_id: string;
  keyword?: string;
  status: "hit" | "partial" | "miss" | string;
  evidence_quote?: string;
  material_quote?: string;
  material_section?: string;
  comment: string;
}

export interface DimensionScore {
  dimension: string;
  level: number;
  comment: string;
}

export interface SentenceItem {
  sentence_id: string;
  text: string;
}

export interface AnnotationItem {
  sentence_id: string;
  issue_type: string;
  severity: "high" | "medium" | "low" | "positive" | string;
  comment: string;
  suggestion: string;
}

export interface GradingReport {
  question_id: string;
  question_title: string;
  exam_type: ExamType;
  final_score: number;
  full_score: number;
  band_label: string;
  word_count: number;
  word_count_warning?: string | null;
  student_answer: string;
  weakness_tags?: string[];
  shenlun_detail?: {
    point_matches: PointMatch[];
  };
  shenlun_essay_detail?: {
    dimensions: DimensionScore[];
  };
  kaoyan_detail?: {
    dimensions: DimensionScore[];
  };
  sentences?: SentenceItem[];
  annotations?: AnnotationItem[];
  upgraded_answer?: string;
  key_improvements?: string[];
}

export interface TaskStatusResp {
  task_id: string;
  status: "pending" | "running" | "completed" | "failed" | string;
  progress_message: string;
  error_message?: string | null;
  report?: GradingReport | null;
  created_at?: string;
  finished_at?: string | null;
}

export interface HistoryItem {
  task_id: string;
  question_id: string;
  exam_type: ExamType;
  question_title: string;
  status: string;
  final_score: number | null;
  full_score: number | null;
  band_label: string | null;
  weakness_tags: string[];
  created_at: string;
}

export interface HistoryResp {
  total: number;
  top_weaknesses: Array<{ tag: string; count: number }>;
  items: HistoryItem[];
}
