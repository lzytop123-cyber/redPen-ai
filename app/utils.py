import re
from typing import Optional

from app.schemas import (
    ExamType,
    KaoyanEnglishStep1Output,
    NumberedSentence,
    Question,
    ShenlunEssayStep1Output,
    ShenlunStep1Output,
)


def count_words(text: str, exam_type: ExamType) -> int:
    """精确统计字数：英文按单词数，中文申论按非空白字符数（含标点，贴合方格纸计字规则）"""
    cleaned = text.strip()
    if not cleaned:
        return 0
    if exam_type == ExamType.KAOYAN_ENGLISH:
        return len(re.findall(r"[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*", cleaned))
    # 申论格子纸通常按非空白字符计字
    return len(re.sub(r"\s+", "", cleaned))


def check_word_count_warning(word_count: int, question: Question) -> Optional[str]:
    if question.max_words and word_count > question.max_words:
        over = word_count - question.max_words
        return f"超出字数上限 {over} 字（当前 {word_count} / 上限 {question.max_words}），考场可能触发扣分！"
    if question.min_words and word_count < question.min_words:
        short = question.min_words - word_count
        return f"未达最少字数要求，差 {short} 字（当前 {word_count} / 最低 {question.min_words}），会触发字数扣分！"
    return None


def split_numbered_sentences(text: str, exam_type: ExamType) -> list[NumberedSentence]:
    """将考生原文切分为带 S1, S2... 编号的句子数组，用于强制绑定红笔批注，杜绝幻觉错位"""
    normalized = text.strip()
    if not normalized:
        return []

    if exam_type == ExamType.KAOYAN_ENGLISH:
        # 英文按 . ! ? 或换行切分
        raw_parts = re.split(r"(?<=[.!?])\s+|\n+", normalized)
    else:
        # 中文按 。！？；或换行切分
        raw_parts = re.split(r"(?<=[。！？；])\s*|\n+", normalized)

    sentences: list[NumberedSentence] = []
    idx = 1
    for part in raw_parts:
        s = part.strip()
        if s:
            sentences.append(NumberedSentence(sentence_id=f"S{idx}", text=s))
            idx += 1
    return sentences


def calculate_shenlun_score(
    question: Question,
    step1: ShenlunStep1Output,
    word_count: int,
) -> tuple[float, str]:
    """
    后端确定性代码算分引擎（申论小题）：
    绝不让大模型直接拍脑袋给总分，而是按采分点命中状态 + 条理分 + 字数扣分严格计算。
    """
    point_map = {p.point_id: p.score for p in question.scoring_points}
    points_total_possible = sum(point_map.values())
    structure_full = max(0.0, question.full_score - points_total_possible)

    earned_points = 0.0
    seen_ids = set()
    for m in step1.point_matches:
        if m.point_id in seen_ids:
            raise ValueError(f"采分点 {m.point_id} 重复，无法计分")
        seen_ids.add(m.point_id)
        base = point_map.get(m.point_id, 0.0)
        if m.status == "hit":
            earned_points += base
        elif m.status == "partial":
            earned_points += base * 0.5

    earned_structure = structure_full * step1.structure_score_ratio
    raw_score = earned_points + earned_structure

    # 字数硬性扣分规则
    penalty = 0.0
    if question.max_words and word_count > question.max_words + 20:
        penalty = min(2.0, ((word_count - question.max_words) // 25) * 0.5 + 0.5)
    elif question.min_words and word_count < question.min_words - 30:
        penalty = 1.5

    final_score = round(max(0.0, min(question.full_score, raw_score - penalty)) * 2) / 2
    ratio = final_score / question.full_score if question.full_score > 0 else 0
    if ratio >= 0.8:
        band = "一类答卷（优秀）"
    elif ratio >= 0.65:
        band = "二类答卷（良好）"
    elif ratio >= 0.5:
        band = "三类答卷（中等）"
    else:
        band = "四类答卷（待大幅提升）"
    return final_score, band


def calculate_kaoyan_english_score(
    question: Question,
    step1: KaoyanEnglishStep1Output,
    word_count: int,
) -> tuple[float, str]:
    """
    后端确定性代码算分引擎（考研英语作文）：
    按各维度 1~5 档定级加权计算，并叠加工整字数扣分与模板风险微调。
    """
    level_to_ratio = {5: 0.92, 4: 0.78, 3: 0.62, 2: 0.44, 1: 0.25}
    total_weight = sum(d.weight for d in step1.dimensions) or 1.0
    weighted_ratio = sum(
        level_to_ratio.get(d.level, 0.5) * (d.weight / total_weight)
        for d in step1.dimensions
    )

    raw_score = question.full_score * weighted_ratio

    # 模板痕迹惩罚
    if step1.template_risk == "high":
        raw_score -= 1.5
    elif step1.template_risk == "medium":
        raw_score -= 0.5

    # 字数不足扣分（考研大纲：每少 10 词扣 1 分左右）
    if question.min_words and word_count < question.min_words:
        shortfall = question.min_words - word_count
        raw_score -= min(4.0, (shortfall / 15.0) * 1.0)

    final_score = round(max(0.0, min(question.full_score, raw_score)) * 2) / 2
    ratio = final_score / question.full_score if question.full_score > 0 else 0
    if ratio >= 0.85:
        band = "第五档（高分优秀）"
    elif ratio >= 0.7:
        band = "第四档（良好）"
    elif ratio >= 0.55:
        band = "第三档（及格中等）"
    elif ratio >= 0.35:
        band = "第二档（偏弱）"
    else:
        band = "第一档（亟需重练）"
    return final_score, band


def calculate_shenlun_essay_score(
    question: Question,
    step1: ShenlunEssayStep1Output,
    word_count: int,
) -> tuple[float, str]:
    """
    后端确定性代码算分引擎（申论大作文）：
    严格执行国考/省考大作文硬性红线：跑题封顶、缺字硬扣分、脱离材料降档。
    """
    level_to_ratio = {5: 0.88, 4: 0.75, 3: 0.60, 2: 0.45, 1: 0.28}
    total_weight = sum(d.weight for d in step1.dimensions) or 1.0
    weighted_ratio = sum(
        level_to_ratio.get(d.level, 0.5) * (d.weight / total_weight)
        for d in step1.dimensions
    )
    raw_score = question.full_score * weighted_ratio

    # 脱离材料微调
    if step1.material_usage == "weak":
        raw_score -= question.full_score * 0.08

    # 字数硬性扣分（申论大作文常见规则：每少 50 字扣 1 分，严重不足直接降档）
    if question.min_words and word_count < question.min_words:
        shortfall = question.min_words - word_count
        raw_score -= min(question.full_score * 0.35, (shortfall / 50.0) * 1.0)

    # 跑题红线封顶（四类文上限约 45%）
    if step1.thesis_accuracy == "off_topic":
        raw_score = min(raw_score, question.full_score * 0.45)
    elif step1.thesis_accuracy == "partial":
        raw_score = min(raw_score, question.full_score * 0.68)

    final_score = round(max(0.0, min(question.full_score, raw_score)) * 2) / 2
    ratio = final_score / question.full_score if question.full_score > 0 else 0
    if ratio >= 0.80:
        band = "一类文（高分范文）"
    elif ratio >= 0.65:
        band = "二类文（良好稳健）"
    elif ratio >= 0.50:
        band = "三类文（及格平庸）"
    else:
        band = "四类文（偏题/残卷风险）"
    return final_score, band

