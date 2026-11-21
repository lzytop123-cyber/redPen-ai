import json
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import QuestionModel


async def seed_questions_if_empty(db: AsyncSession) -> int:
    """服务启动时自动将清洗好的真题库幂等导入数据库（支持增量补齐新增科目如 396 经综）"""
    existing_count = await db.scalar(select(func.count(QuestionModel.question_id)))
    if existing_count and existing_count > 0:
        count_396 = await db.scalar(
            select(func.count(QuestionModel.question_id)).where(
                QuestionModel.exam_type == "kaoyan_396"
            )
        )
        if count_396 and count_396 > 0:
            return 0
        seed_paths = [Path("data/kaoyan_396_questions.json")]
    else:
        seed_paths = [
            Path("data/shenlun_questions.json"),
            Path("data/kaoyan_questions.json"),
            Path("data/kaoyan_396_questions.json"),
            Path("data/sample_questions.json"),
        ]

    existing_ids = set(
        (await db.execute(select(QuestionModel.question_id))).scalars().all()
    )
    inserted = 0
    seen_ids: set[str] = set(existing_ids)
    for path in seed_paths:
        if not path.exists():
            continue
        items = json.loads(path.read_text(encoding="utf-8"))
        for item in items:
            qid = item["question_id"]
            if qid in seen_ids:
                continue
            seen_ids.add(qid)
            db.add(
                QuestionModel(
                    question_id=qid,
                    exam_type=item["exam_type"],
                    title=item["title"],
                    year=item.get("year", 0),
                    paper=item.get("paper", ""),
                    sub_type=item.get("sub_type", ""),
                    prompt=item["prompt"],
                    material_summary=item.get("material_summary", ""),
                    full_score=item.get("full_score", 15.0),
                    min_words=item.get("min_words", 0),
                    max_words=item.get("max_words", 0),
                    scoring_points=item.get("scoring_points", []),
                    reference_answer=item.get("reference_answer", ""),
                )
            )
            inserted += 1

    await db.commit()
    return inserted
