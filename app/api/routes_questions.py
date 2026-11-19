from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import QuestionModel

router = APIRouter(prefix="/api/questions", tags=["真题库"])


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
                "min_words": q.min_words,
                "max_words": q.max_words,
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
        "min_words": q.min_words,
        "max_words": q.max_words,
        "scoring_point_count": len(q.scoring_points or []),
    }
