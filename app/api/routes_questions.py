from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import QuestionModel
from app.pdf_exporter import build_question_pdf

from app.word_limits import english_word_limits, short_answer_limits


def _word_limits(q: QuestionModel) -> dict[str, int | str]:
    minimum, maximum = q.min_words, q.max_words
    if q.exam_type == "kaoyan_english":
        minimum, maximum, label = english_word_limits(q.prompt, minimum, maximum)
        return {"min_words": minimum, "max_words": maximum, "word_requirement": label}
    if q.exam_type == "shenlun_short":
        minimum, maximum = short_answer_limits(q.prompt, minimum, maximum)
    label = ""
    if minimum and maximum:
        label = f"{minimum}～{maximum} 字"
    elif maximum:
        label = f"不超过 {maximum} 字"
    elif minimum:
        label = f"不少于 {minimum} 字"
    return {"min_words": minimum, "max_words": maximum, "word_requirement": label}


router = APIRouter(prefix="/api/questions", tags=["真题库"])


@router.get("/regions")
async def list_regions(db: AsyncSession = Depends(get_db)):
    """动态返回当前申论题库覆盖的所有地区与题目数量（国考排首位，其余按题量降序）"""
    stmt = select(QuestionModel.paper).where(
        ~QuestionModel.question_id.startswith("CUSTOM_"),
        QuestionModel.exam_type.in_(["shenlun_short", "shenlun_essay"]),
    )
    papers = (await db.execute(stmt)).scalars().all()
    counts: dict[str, int] = {}
    for p in papers:
        if not p:
            continue
        reg = p.split("-")[0].strip()
        if reg:
            counts[reg] = counts.get(reg, 0) + 1

    ordered = sorted(
        counts.items(),
        key=lambda kv: (0 if kv[0] == "国考" else 1, -kv[1], kv[0]),
    )
    return {
        "total_regions": len(ordered),
        "items": [{"label": k, "value": k, "count": v} for k, v in ordered],
    }


@router.get("")
async def list_questions(
    exam_type: Optional[str] = Query(default=None, description="shenlun_short / shenlun_essay / kaoyan_english"),
    region: Optional[str] = Query(default=None, description="按地区筛选，如 国考/山西/贵州/广东/湖北"),
    sub_type: Optional[str] = Query(default=None, description="按细分题型筛选，如 归纳概括/提出对策/综合分析/公文写作"),
    year: Optional[int] = Query(default=None, description="按年份筛选，如 2026"),
    keyword: Optional[str] = Query(default=None, description="按标题或题干关键词搜索"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """分页查询结构化真题库"""
    stmt = select(QuestionModel).where(~QuestionModel.question_id.startswith("CUSTOM_"))
    count_stmt = select(func.count(QuestionModel.question_id)).where(
        ~QuestionModel.question_id.startswith("CUSTOM_")
    )

    if exam_type:
        stmt = stmt.where(QuestionModel.exam_type == exam_type)
        count_stmt = count_stmt.where(QuestionModel.exam_type == exam_type)
    if region:
        r_like = f"%{region.strip()}%"
        r_cond = or_(QuestionModel.paper.ilike(r_like), QuestionModel.title.ilike(r_like))
        stmt = stmt.where(r_cond)
        count_stmt = count_stmt.where(r_cond)
    if sub_type:
        s_like = f"%{sub_type.strip()}%"
        stmt = stmt.where(QuestionModel.sub_type.ilike(s_like))
        count_stmt = count_stmt.where(QuestionModel.sub_type.ilike(s_like))
    if year:
        stmt = stmt.where(QuestionModel.year == year)
        count_stmt = count_stmt.where(QuestionModel.year == year)
    if keyword:
        like = f"%{keyword.strip()}%"
        cond = or_(
            QuestionModel.title.ilike(like),
            QuestionModel.prompt.ilike(like),
            QuestionModel.paper.ilike(like),
        )
        stmt = stmt.where(cond)
        count_stmt = count_stmt.where(cond)

    total = await db.scalar(count_stmt) or 0
    stmt = (
        stmt.order_by(QuestionModel.year.desc(), QuestionModel.question_id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    rows = (await db.execute(stmt)).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "question_id": q.question_id,
                "exam_type": q.exam_type,
                "title": q.title,
                "year": q.year,
                "paper": q.paper,
                "sub_type": q.sub_type,
                "full_score": q.full_score,
                **_word_limits(q),
                "scoring_point_count": len(q.scoring_points or []),
            }
            for q in rows
        ],
    }


@router.get("/{question_id}")
async def get_question_detail(question_id: str, db: AsyncSession = Depends(get_db)):
    """获取单道真题详情（题干、给定材料摘要、字数要求）"""
    q = await db.get(QuestionModel, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="真题不存在")
    return {
        "question_id": q.question_id,
        "exam_type": q.exam_type,
        "title": q.title,
        "year": q.year,
        "paper": q.paper,
        "sub_type": q.sub_type,
        "prompt": q.prompt,
        "material_summary": q.material_summary,
        "full_score": q.full_score,
        **_word_limits(q),
        "scoring_point_count": len(q.scoring_points or []),
    }


@router.get("/{question_id}/pdf")
async def export_question_pdf(question_id: str, db: AsyncSession = Depends(get_db)):
    """导出单道真题的 A4 宽行距 PDF（支持直接打印或转发至 iPad GoodNotes 勾画）"""
    q = await db.get(QuestionModel, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="真题不存在")

    limits = _word_limits(q)
    min_w, max_w = limits["min_words"], limits["max_words"]
    unit = "词" if q.exam_type == "kaoyan_english" else "字"
    if min_w and max_w:
        limit_str = f"字数要求：{min_w}～{max_w} {unit}"
    elif max_w:
        limit_str = f"字数要求：不超过 {max_w} {unit}"
    elif min_w:
        limit_str = f"字数要求：不少于 {min_w} {unit}"
    else:
        limit_str = ""

    pdf_bytes = build_question_pdf(
        title=q.title,
        prompt=q.prompt,
        material=q.material_summary or "",
        word_limit_text=limit_str,
    )
    safe_name = quote(f"{q.question_id}.pdf")
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename*=UTF-8''{safe_name}"},
    )
