from enum import Enum
import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, ValidationInfo, model_validator

from app.word_limits import english_word_limits, kaoyan_396_word_limits, short_answer_limits


def _normalize_quote_text(text: str) -> str:
    """去除空白/换行并统一常见全半角标点，避免 OCR 换行或标点差异误杀真实原文引用"""
    s = re.sub(r"\s+", "", text)
    return s.translate(str.maketrans({",": "，", ";": "；", ":": "：", "!": "！", "?": "？"}))


class ExamType(str, Enum):
    SHENLUN_SHORT = "shenlun_short"      # 考公申论小题（采分点驱动：概括/对策/分析/公文）
    SHENLUN_ESSAY = "shenlun_essay"      # 考公申论大作文（五档维度量表驱动）
    KAOYAN_ENGLISH = "kaoyan_english"    # 考研英语作文（五档量表驱动）
    KAOYAN_396 = "kaoyan_396"            # 396经济类综合能力写作（论证有效性分析 + 论说文）


# =========================
# 1. 结构化真题与采分点模型
# =========================

class ScoringPoint(BaseModel):
    """申论小题原子级采分点"""
    point_id: str = Field(..., description="采分点编号，如 P1, P2")
    keyword: str = Field(..., description="核心关键词/规范表述")
    description: str = Field(..., description="采分点完整说明及同义表达")
    score: float = Field(..., description="该采分点分值")
    material_quote: str = Field(default="", description="已核对的给定材料原文")


class Question(BaseModel):
    """结构化真题模型（可直接存 PostgreSQL + JSONB）"""
    question_id: str
    exam_type: ExamType
    title: str
    year: int = Field(default=0, description="真题年份")
    paper: str = Field(default="", description="所属试卷，如 国考-2024-副省级")
    sub_type: str = Field(default="", description="细分题型，如 单一题（归纳概括）/大作文/公文写作题")
    prompt: str = Field(..., description="题目具体要求")
    material_summary: str = Field(default="", description="给定材料核心摘要（申论用）")
    full_score: float = Field(..., description="本题满分")
    min_words: int = Field(default=0, description="最少字数要求")
    max_words: int = Field(default=0, description="最多字数限制（0表示不限）")
    scoring_points: list[ScoringPoint] = Field(default_factory=list, description="申论标准采分点列表")
    reference_answer: str = Field(default="", description="参考高分答案")


    @model_validator(mode="after")
    def apply_written_limits(self):
        if self.exam_type == ExamType.KAOYAN_ENGLISH:
            self.min_words, self.max_words, _ = english_word_limits(
                self.prompt, self.min_words, self.max_words
            )
        if self.exam_type == ExamType.SHENLUN_SHORT:
            self.min_words, self.max_words = short_answer_limits(
                self.prompt, self.min_words, self.max_words
            )
        if self.exam_type == ExamType.KAOYAN_396:
            self.min_words, self.max_words, _ = kaoyan_396_word_limits(
                self.prompt, self.min_words, self.max_words
            )
        return self


# =========================
# 2. 预处理句子模型
# =========================

class NumberedSentence(BaseModel):
    sentence_id: str = Field(..., description="如 S1, S2, S3")
    text: str


# =========================
# 3. Step 1: 采分点 / 维度核对结果（由 LLM 输出，总分由代码算）
# =========================

class PointMatchResult(BaseModel):
    point_id: str
    status: Literal["hit", "partial", "miss"] = Field(
        ..., description="hit=完全命中, partial=部分命中, miss=未命中"
    )
    evidence_quote: str = Field(
        default="", description="考生原文中命中该采分点的原句摘录；未命中则留空"
    )
    comment: str = Field(..., description="简短判定理由及如何补全")


class ShenlunStep1Output(BaseModel):
    """申论小题 Step 1 结构化核对输出"""
    point_matches: list[PointMatchResult]
    structure_score_ratio: float = Field(
        ..., ge=0.0, le=1.0, description="条理/格式/语言规范得分率（0~1）"
    )
    structure_comment: str = Field(..., description="对分条作答、总分结构、语言精炼度的评价")
    weakness_tags: list[str] = Field(
        default_factory=list, description="本次作答暴露的薄弱项标签，如['漏提对策','表达口语化']"
    )


    @model_validator(mode="after")
    def check_matches(self, info: ValidationInfo):
        ids = [match.point_id for match in self.point_matches]
        if info.context:
            if len(ids) != len(set(ids)):
                raise ValueError("每个采分点编号只能出现一次")
            if set(ids) != info.context["point_ids"]:
                raise ValueError("请严格使用题目提供的所有采分点编号，每点返回一次")
            norm_answer = _normalize_quote_text(info.context["student_answer"])
            for match in self.point_matches:
                if match.status in ("hit", "partial"):
                    quote = match.evidence_quote.strip()
                    if not quote or _normalize_quote_text(quote) not in norm_answer:
                        raise ValueError(f"{match.point_id} 的证据必须逐字摘自考生原文")
        return self


class DimensionRating(BaseModel):
    dimension: str = Field(..., description="维度名称，如 内容切题/语法准确/词汇与句式/逻辑衔接")
    level: int = Field(..., ge=1, le=5, description="1~5 档（5 为最高）")
    weight: float = Field(..., gt=0.0, le=1.0, description="该维度权重")
    comment: str = Field(..., description="该维度具体扣分点与点评")


class ShenlunEssayStep1Output(BaseModel):
    """申论大作文 Step 1 结构化维度定档输出"""
    dimensions: list[DimensionRating]
    thesis_accuracy: Literal["accurate", "partial", "off_topic"] = Field(
        ..., description="中心论点立意判定：accurate=精准切题, partial=略有偏差, off_topic=跑题偏题"
    )
    material_usage: Literal["strong", "moderate", "weak"] = Field(
        ..., description="结合给定材料的程度"
    )
    overall_comment: str = Field(..., description="考官总评（严苛客观，不客套）")
    weakness_tags: list[str] = Field(
        default_factory=list, description="薄弱项标签，如['脱离材料','分论点不平行','结尾空泛']"
    )


class KaoyanEnglishStep1Output(BaseModel):
    """考研英语作文 Step 1 结构化维度定档输出"""
    dimensions: list[DimensionRating]
    template_risk: Literal["low", "medium", "high"] = Field(
        ..., description="模板痕迹风险等级"
    )
    overall_comment: str = Field(..., description="考官总评（严苛客观，不客套）")
    weakness_tags: list[str] = Field(
        default_factory=list, description="薄弱项标签，如['时态错误','中式英语','词汇重复']"
    )


# =========================
# 4. Step 2: 逐句红笔批注模型（严格绑定 sentence_id）
# =========================

class SentenceAnnotation(BaseModel):
    sentence_id: str = Field(..., description="必须严格对应输入的 S1/S2/... 编号")
    issue_type: Literal[
        "grammar",          # 语法/拼写错误
        "expression",       # 表达口语化/中式英语/不够规范
        "missing_point",    # 采分点遗漏或表述不精准
        "logic",            # 逻辑断层/跑题
        "redundancy",       # 啰嗦超字数
        "highlight",        # 亮点句（表扬）
    ]
    severity: Literal["high", "medium", "low", "positive"]
    original_excerpt: str = Field(..., description="该句中有问题的局部片段")
    comment: str = Field(..., description="红笔批注说明")
    suggestion: str = Field(..., description="具体修改后的句子或表达")


class Step2AnnotationOutput(BaseModel):
    annotations: list[SentenceAnnotation]


# =========================
# 5. Step 3: 同思路升格范文
# =========================

class Step3UpgradeOutput(BaseModel):
    upgraded_answer: str = Field(..., description="保留考生原有立意框架，仅做表达升格与漏点补全后的高分版")
    key_improvements: list[str] = Field(..., description="列出 3~5 条本次升格最核心的改动亮点")


# =========================
# 6. 最终汇总报告（存入数据库 & 返回前端）
# =========================

class GradingReport(BaseModel):
    question_id: str
    exam_type: ExamType
    question_title: str
    student_answer: str
    word_count: int
    word_count_warning: Optional[str] = None

    # 由后端代码严格计算出的分数与档位
    final_score: float
    full_score: float
    band_label: str

    # 细分核对详情
    shenlun_detail: Optional[ShenlunStep1Output] = None
    shenlun_essay_detail: Optional[ShenlunEssayStep1Output] = None
    kaoyan_detail: Optional[KaoyanEnglishStep1Output] = None

    # 带 ID 原文 + 红笔批注
    sentences: list[NumberedSentence]
    annotations: list[SentenceAnnotation]

    # 同思路升格范文
    upgraded_answer: str
    key_improvements: list[str]
    weakness_tags: list[str] = Field(default_factory=list)
