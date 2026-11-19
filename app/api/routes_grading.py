import asyncio
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_utils import get_current_user
from app.config import settings
from app.db.database import AsyncSessionLocal, get_db
from app.db.models import GradingTask, QuestionModel, User
from app.llm_client import LLMRouter
from app.pipeline import GradingPipeline
from app.point_builder import build_grounded_scoring_points
from app.schemas import ExamType, Question, ScoringPoint
from app.utils import count_words

router = APIRouter(prefix="/api/grading", tags=["AI 精批引擎"])
UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# 按 question_id 维度的内存互斥锁，防止并发首次提交同一道新题时重复生成采分点
_POINT_GEN_LOCKS: dict[str, asyncio.Lock] = {}


def _get_point_lock(question_id: str) -> asyncio.Lock:
    lock = _POINT_GEN_LOCKS.get(question_id)
    if lock is None:
        lock = asyncio.Lock()
        _POINT_GEN_LOCKS[question_id] = lock
    return lock


async def ensure_cached_scoring_points(
    question: Question,
    router_client: LLMRouter,
    on_progress=None,
) -> Question:
    """
    懒加载 + 永久缓存机制：
    当某道申论小题首次被提交且尚无标准采分点时，自动基于完整材料构建 v2 采分点并永久写入数据库；
    后续所有用户提交该题直接复用数据库缓存，0 额外延迟、0 重复费用。
    """
    if (
        question.exam_type != ExamType.SHENLUN_SHORT
        or question.scoring_points
        or question.question_id.startswith("CUSTOM_")
        or not (question.material_summary or "").strip()
    ):
        return question

    async with _get_point_lock(question.question_id):
        # 双重检查：若刚才已有并发请求生成并落库，直接复用
        async with AsyncSessionLocal() as session:
            row = await session.get(QuestionModel, question.question_id)
            if row and row.scoring_points:
                question.scoring_points = [ScoringPoint.model_validate(p) for p in row.scoring_points]
                if row.reference_answer:
                    question.reference_answer = row.reference_answer
                return question

        if on_progress:
            await on_progress("Step 0/3: 首次评阅本题，正在基于完整材料自动构建 v2 标准采分点并缓存...")

        points, ref_ans, sub_type = await build_grounded_scoring_points(router_client, question)
        if points:
            question.scoring_points = points
            question.reference_answer = ref_ans
            if sub_type:
                question.sub_type = sub_type

            async with AsyncSessionLocal() as session:
                row = await session.get(QuestionModel, question.question_id)
                if row:
                    row.scoring_points = [p.model_dump() for p in points]
                    row.reference_answer = ref_ans
                    if sub_type:
                        row.sub_type = sub_type
                    await session.commit()

    return question


class SubmitGradingReq(BaseModel):
    question_id: str
    student_answer: str = Field(..., min_length=10, description="考生作答文本（可直接输入或由 OCR 识别微调后提交）")
    image_path: Optional[str] = None


class SubmitCustomGradingReq(BaseModel):
    exam_type: ExamType = Field(default=ExamType.SHENLUN_ESSAY, description="题型：shenlun_short / shenlun_essay / kaoyan_english")
    custom_title: Optional[str] = Field(default=None, description="自定义标题，可不填")
    custom_prompt: str = Field(..., min_length=5, description="题目要求（可手打或拍照 OCR 识别）")
    custom_material: str = Field(default="", description="给定材料或参考答案（可选）")
    full_score: float = Field(default=0, description="满分（0 表示按题型自动给默认满分）")
    student_answer: str = Field(..., min_length=10, description="考生作答文本")
    image_path: Optional[str] = None


def _to_question_schema(q: QuestionModel) -> Question:
    return Question(
        question_id=q.question_id,
        exam_type=ExamType(q.exam_type),
        title=q.title,
        year=q.year,
        paper=q.paper,
        sub_type=q.sub_type,
        prompt=q.prompt,
        material_summary=q.material_summary,
        full_score=q.full_score,
        min_words=q.min_words,
        max_words=q.max_words,
        scoring_points=[ScoringPoint.model_validate(p) for p in (q.scoring_points or [])],
        reference_answer=q.reference_answer,
    )


async def _execute_grading_task(task_id: str, question: Question, student_answer: str) -> None:
    """后台异步执行 3 步精批管线（后续高并发时可直接迁移至 Redis + ARQ Worker）"""
    use_mock = (not settings.llm_api_key or settings.llm_api_key.startswith("sk-your-")) and settings.enable_mock_fallback

    async def update_progress(msg: str) -> None:
        async with AsyncSessionLocal() as session:
            t = await session.get(GradingTask, task_id)
            if t:
                t.status = "running"
                t.progress_message = msg
                await session.commit()

    try:
        router_client = LLMRouter()
        if not use_mock:
            question = await ensure_cached_scoring_points(question, router_client, on_progress=update_progress)

        await update_progress("Step 1/3: 正在对照官方评分细则与采分点核对...")
        pipeline = GradingPipeline(router=router_client)
        report = await pipeline.run(
            question=question,
            student_answer=student_answer,
            mock=use_mock,
        )

        async with AsyncSessionLocal() as session:
            t = await session.get(GradingTask, task_id)
            if t:
                t.status = "completed"
                t.progress_message = "精批完成！"
                t.final_score = report.final_score
                t.full_score = report.full_score
                t.band_label = report.band_label
                t.weakness_tags = report.weakness_tags
                t.report_json = report.model_dump()
                t.finished_at = datetime.utcnow()
                await session.commit()
    except Exception as e:
        async with AsyncSessionLocal() as session:
            t = await session.get(GradingTask, task_id)
            if t:
                t.status = "failed"
                t.progress_message = "批改失败，请稍后重试"
                t.error_message = str(e)
                t.finished_at = datetime.utcnow()
                await session.commit()


@router.post("/ocr")
async def ocr_handwriting_image(
    file: UploadFile = File(...),
    exam_type: str = "shenlun_short",
    user: User = Depends(get_current_user),
):
    """
    Step 0 接口：小程序拍照上传手写答卷照片 -> 视觉模型识别文字与字数
    前端拿到文本后给用户 10 秒微调错别字，再调用 /submit 提交精批。
    """
    ext = Path(file.filename or "answer.jpg").suffix or ".jpg"
    fname = f"{user.id}_{uuid.uuid4().hex[:12]}{ext}"
    save_path = UPLOAD_DIR / fname
    content = await file.read()
    save_path.write_bytes(content)

    use_mock = (
        not settings.effective_vlm_api_key
        or settings.effective_vlm_api_key.startswith("sk-your-")
    ) and settings.enable_mock_fallback

    if use_mock:
        text = (
            "1. 提升设计研发能力，注重原创设计，结合高校与科研机构提升产品技术含量。\n"
            "2. 拓展多元销售渠道，线上直播触达年轻群体，线下门店做好体验服务。\n"
            "3. 深耕细分市场，满足不同消费场景的个性化照明需求。"
        )
    else:
        router_client = LLMRouter()
        text = await router_client.ocr_handwriting(save_path)

    wc = count_words(text, ExamType(exam_type))
    return {
        "image_path": str(save_path),
        "recognized_text": text,
        "word_count": wc,
        "mock_mode": use_mock,
    }


@router.post("/submit")
async def submit_grading(
    req: SubmitGradingReq,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """提交精批任务（扣减额度 -> 立即返回 task_id -> 后台异步执行 3 步管线）"""
    q_row = await db.get(QuestionModel, req.question_id)
    if not q_row:
        raise HTTPException(status_code=404, detail="所选真题不存在")

    is_vip = bool(user.vip_expire_at and user.vip_expire_at > datetime.utcnow())
    if not is_vip:
        if user.free_quota > 0:
            user.free_quota -= 1
        elif user.paid_quota > 0:
            user.paid_quota -= 1
        else:
            raise HTTPException(status_code=402, detail="精批次数已用完，请先充值体验包或开通月卡")

    task_id = f"task_{uuid.uuid4().hex[:16]}"
    task = GradingTask(
        task_id=task_id,
        user_id=user.id,
        question_id=q_row.question_id,
        exam_type=q_row.exam_type,
        question_title=q_row.title,
        status="pending",
        progress_message="已接收答卷，正在启动 AI 阅卷引擎...",
        student_answer=req.student_answer,
        image_path=req.image_path,
    )
    db.add(task)
    await db.commit()

    q_schema = _to_question_schema(q_row)
    background_tasks.add_task(_execute_grading_task, task_id, q_schema, req.student_answer)

    return {
        "task_id": task_id,
        "status": "pending",
        "progress_message": task.progress_message,
        "remaining_quota": user.free_quota + user.paid_quota,
    }


@router.post("/submit-custom")
async def submit_custom_grading(
    req: SubmitCustomGradingReq,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """自定义题目自由批改接口（适用于模拟卷、机构押题、随手练笔等不在真题库里的题目）"""
    is_vip = bool(user.vip_expire_at and user.vip_expire_at > datetime.utcnow())
    if not is_vip:
        if user.free_quota > 0:
            user.free_quota -= 1
        elif user.paid_quota > 0:
            user.paid_quota -= 1
        else:
            raise HTTPException(status_code=402, detail="精批次数已用完，请先充值体验包或开通月卡")

    default_scores = {
        ExamType.SHENLUN_SHORT: (15.0, 120, 300),
        ExamType.SHENLUN_ESSAY: (40.0, 1000, 1200),
        ExamType.KAOYAN_ENGLISH: (20.0, 160, 220),
    }
    def_score, min_w, max_w = default_scores[req.exam_type]
    full_score = req.full_score if req.full_score > 0 else def_score

    qid = f"CUSTOM_{uuid.uuid4().hex[:10].upper()}"
    title = (req.custom_title or "").strip() or f"【自由批改】{req.custom_prompt[:22]}"

    q_row = QuestionModel(
        question_id=qid,
        exam_type=req.exam_type.value,
        title=title,
        year=datetime.utcnow().year,
        paper="自定义题目",
        sub_type="自由批改",
        prompt=req.custom_prompt,
        material_summary=req.custom_material,
        full_score=full_score,
        min_words=min_w,
        max_words=max_w,
        scoring_points=[],
        reference_answer="",
    )
    db.add(q_row)

    task_id = f"task_{uuid.uuid4().hex[:16]}"
    task = GradingTask(
        task_id=task_id,
        user_id=user.id,
        question_id=qid,
        exam_type=req.exam_type.value,
        question_title=title,
        status="pending",
        progress_message="已接收自定义答卷，正在启动 AI 阅卷引擎...",
        student_answer=req.student_answer,
        image_path=req.image_path,
    )
    db.add(task)
    await db.commit()

    q_schema = _to_question_schema(q_row)
    background_tasks.add_task(_execute_grading_task, task_id, q_schema, req.student_answer)

    return {
        "task_id": task_id,
        "status": "pending",
        "progress_message": task.progress_message,
        "remaining_quota": user.free_quota + user.paid_quota,
    }


@router.get("/tasks/{task_id}")
async def get_task_status(
    task_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """小程序端每 2 秒轮询此接口，获取批改进度与最终结构化红笔报告"""
    task = await db.get(GradingTask, task_id)
    if not task or task.user_id != user.id:
        raise HTTPException(status_code=404, detail="批改任务不存在")
    return {
        "task_id": task.task_id,
        "status": task.status,
        "progress_message": task.progress_message,
        "error_message": task.error_message,
        "report": task.report_json,
        "created_at": task.created_at,
        "finished_at": task.finished_at,
    }


@router.get("/history")
async def get_grading_history(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """获取当前用户历史精批记录 + 个人高频薄弱项画像"""
    stmt = (
        select(GradingTask)
        .where(GradingTask.user_id == user.id)
        .order_by(desc(GradingTask.created_at))
        .limit(50)
    )
    rows = (await db.execute(stmt)).scalars().all()

    tag_counter: Counter[str] = Counter()
    items = []
    for r in rows:
        for t in (r.weakness_tags or []):
            tag_counter[t] += 1
        items.append(
            {
                "task_id": r.task_id,
                "question_id": r.question_id,
                "exam_type": r.exam_type,
                "question_title": r.question_title,
                "status": r.status,
                "final_score": r.final_score,
                "full_score": r.full_score,
                "band_label": r.band_label,
                "weakness_tags": r.weakness_tags or [],
                "created_at": r.created_at,
            }
        )

    return {
        "total": len(items),
        "top_weaknesses": [{"tag": k, "count": v} for k, v in tag_counter.most_common(6)],
        "items": items,
    }
