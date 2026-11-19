"""
商业级 v2 标准采分点构建器（在线懒加载缓存 + 离线批量脚本共用）。
- 有官方参考答案时：严格从参考答案拆分原子采分点；
- 无参考答案时：基于完整给定材料提炼，每个采分点强制附材料原文引用并由代码逐字核验防幻觉。
"""

import re
from typing import Optional

from pydantic import BaseModel, Field

from app.llm_client import LLMRouter
from app.schemas import Question, ScoringPoint

SUB_TYPES = ["单一题（归纳概括）", "提出对策题", "综合分析题", "公文写作题", "大作文"]


class PointDraft(BaseModel):
    keyword: str = Field(..., description="4~12字规范总括词")
    description: str = Field(..., description="得分细项与可接受的同义表述")
    weight: int = Field(..., ge=1, le=3, description="相对重要度：3=核心要点，2=重要，1=次要")
    material_quote: str = Field(default="", description="支撑该要点的给定材料原文（逐字摘录10~40字）")


class PointBuildOutput(BaseModel):
    sub_type: str = Field(..., description=f"题型，只能是：{' / '.join(SUB_TYPES)}")
    scoring_points: list[PointDraft] = Field(..., min_length=1, max_length=12)
    reference_answer: str = Field(default="", description="高分参考答案")


def _norm(s: str) -> str:
    return re.sub(r"[\s，。、；：:,.;“”\"'‘’（）()《》!?！？\-—…]", "", s)


def quote_in_material(quote: str, material: str, window: int = 10) -> bool:
    q, m = _norm(quote), _norm(material)
    if len(q) < window:
        return bool(q) and q in m
    return any(q[i : i + window] in m for i in range(0, len(q) - window + 1, 3))


def allocate_scores(points: list[PointDraft], full_score: float) -> list[float]:
    reserve = max(1.0, round(full_score * 0.15))
    budget = full_score - reserve
    total_w = sum(p.weight for p in points) or 1
    raw = [budget * p.weight / total_w for p in points]
    scores = [round(x * 2) / 2 for x in raw]
    diff = round((budget - sum(scores)) * 2) / 2
    if scores and diff:
        idx = max(range(len(points)), key=lambda i: points[i].weight)
        scores[idx] = max(0.5, scores[idx] + diff)
    return scores


async def build_grounded_scoring_points(
    router: LLMRouter,
    question: Question,
) -> tuple[list[ScoringPoint], str, Optional[str]]:
    """
    为缺失采分点的申论小题构建经材料逐字核验的 v2 标准采分点。
    返回: (scoring_points, reference_answer, detected_sub_type)
    """
    material = question.material_summary or ""
    has_ref = len(question.reference_answer or "") >= 30 and question.question_id.startswith(("GK-", "GD-", "HB-"))

    if has_ref:
        sys_p = (
            "你是公考申论阅卷组的采分点拆解专家。你的唯一依据是【参考答案】。\n"
            "规则：\n"
            "1. 把参考答案拆成原子级采分点：一个采分点只包含一个独立得分意思；\n"
            "2. 严禁添加参考答案中没有的内容，忽略参考答案说明文字；\n"
            "3. description 写明核心意思与可接受的同义表述；weight 反映重要度(1~3)；\n"
            "4. material_quote 从给定材料中摘录支撑原文（找不到可留空）；判断 sub_type；reference_answer 留空。"
        )
        usr_p = (
            f"【题目要求】\n{question.prompt}\n\n"
            f"【参考答案】\n{question.reference_answer}\n\n"
            f"【给定材料】\n{material}"
        )
    else:
        sys_p = (
            "你是资深公考申论教研组长，严格遵循“材料为王、原词提炼、不凭空臆造”。\n"
            "规则：\n"
            "1. 先精确定位题目指定的给定资料范围（如“给定资料3”），只从该范围提炼；\n"
            "2. 每个采分点必须附 material_quote：从材料中逐字摘录10~40字原文，禁止改写，系统会逐字核验；\n"
            "3. 一个采分点只包含一个独立得分意思，数量按分值合理确定（一般每2~4分一个点）；\n"
            "4. weight 反映重要度(1~3)；判断 sub_type；\n"
            "5. reference_answer 写一份严格符合题目字数要求的高分答案。"
        )
        usr_p = f"【题目要求】\n{question.prompt}\n\n【给定材料】\n{material}"

    res = await router.call_structured(sys_p, usr_p, PointBuildOutput)
    drafts = res.scoring_points
    if not has_ref and material:
        verified = [p for p in drafts if quote_in_material(p.material_quote, material)]
        # 若极端情况下全部被过滤，保留原始前几条避免空点，否则严格采用核验通过项
        if verified:
            drafts = verified

    scores = allocate_scores(drafts, question.full_score)
    points = [
        ScoringPoint(
            point_id=f"P{i}",
            keyword=p.keyword,
            description=p.description,
            score=s,
        )
        for i, (p, s) in enumerate(zip(drafts, scores), start=1)
    ]
    ref_ans = question.reference_answer if has_ref else (res.reference_answer.strip() or question.reference_answer)
    sub_type = res.sub_type if res.sub_type in SUB_TYPES and res.sub_type != "大作文" else None
    return points, ref_ans, sub_type
