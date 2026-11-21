"""
知行岛申论精批 — 商业级运营管理后台 API (/api/admin/*)
涵盖 6 大模块：运营看板、批改质检与退次、真题与可视化采分点 CRUD、用户管理、卡密生成/作废/CSV 导出、系统连通性检测。
"""

import csv
import hmac
import io
import secrets
import string
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.routes_auth import hash_password
from app.config import settings
from app.db.database import get_db
from app.db.models import GradingTask, QuestionModel, RedeemCode, User
from app.llm_client import LLMRouter
from app.point_builder import build_grounded_scoring_points
from app.schemas import ExamType, Question, ScoringPoint

router = APIRouter(prefix="/api/admin", tags=["运营后台 API"])
UPLOAD_DIR = Path("data/uploads").resolve()

_ADMIN_FAIL_WINDOW_SEC = 300.0
_ADMIN_MAX_FAILS = 10
_ADMIN_FAIL_LOG: dict[str, list[float]] = defaultdict(list)


def verify_admin(
    request: Request,
    x_admin_password: Optional[str] = Header(default=None),
) -> None:
    """仅接受 Header 鉴权（禁止 URL 明文传密码），并带防爆破限流"""
    ip = request.client.host if request.client else "unknown"
    now = time.monotonic()
    fails = [t for t in _ADMIN_FAIL_LOG[ip] if now - t < _ADMIN_FAIL_WINDOW_SEC]
    if len(fails) >= _ADMIN_MAX_FAILS:
        raise HTTPException(status_code=429, detail="管理员密码错误次数过多，请 5 分钟后再试")

    if not x_admin_password or not hmac.compare_digest(x_admin_password, settings.admin_password):
        fails.append(now)
        _ADMIN_FAIL_LOG[ip] = fails
        raise HTTPException(status_code=401, detail="管理员密码错误或未登录")

    if ip in _ADMIN_FAIL_LOG:
        _ADMIN_FAIL_LOG.pop(ip, None)


# =========================
# 1. 运营总览看板与趋势
# =========================

@router.get("/stats", dependencies=[Depends(verify_admin)])
async def admin_stats(db: AsyncSession = Depends(get_db)):
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_users = await db.scalar(select(func.count(User.id))) or 0
    today_users = await db.scalar(select(func.count(User.id)).where(User.created_at >= today_start)) or 0
    active_vips = await db.scalar(select(func.count(User.id)).where(User.vip_expire_at > now)) or 0

    total_tasks = await db.scalar(select(func.count(GradingTask.task_id))) or 0
    today_tasks = (
        await db.scalar(select(func.count(GradingTask.task_id)).where(GradingTask.created_at >= today_start)) or 0
    )
    completed_tasks = (
        await db.scalar(select(func.count(GradingTask.task_id)).where(GradingTask.status == "completed")) or 0
    )
    failed_tasks = (
        await db.scalar(select(func.count(GradingTask.task_id)).where(GradingTask.status == "failed")) or 0
    )

    q_rows = (
        await db.execute(
            select(QuestionModel.exam_type, QuestionModel.scoring_points).where(
                ~QuestionModel.question_id.startswith("CUSTOM_")
            )
        )
    ).all()
    total_questions = len(q_rows)
    short_total = sum(1 for et, _ in q_rows if et == "shenlun_short")
    short_with_points = sum(1 for et, pts in q_rows if et == "shenlun_short" and pts and len(pts) > 0)

    unused_codes = await db.scalar(select(func.count(RedeemCode.code)).where(RedeemCode.is_used == 0)) or 0
    used_codes = await db.scalar(select(func.count(RedeemCode.code)).where(RedeemCode.is_used == 1)) or 0

    # 近 7 天批改趋势
    seven_days_ago = today_start - timedelta(days=6)
    recent_dates = (
        await db.execute(select(GradingTask.created_at).where(GradingTask.created_at >= seven_days_ago))
    ).scalars().all()
    day_counts: dict[str, int] = {}
    for i in range(7):
        d_str = (seven_days_ago + timedelta(days=i)).strftime("%m-%d")
        day_counts[d_str] = 0
    for dt in recent_dates:
        if dt:
            k = dt.strftime("%m-%d")
            if k in day_counts:
                day_counts[k] += 1
    trend_7d = [{"date": k, "count": v} for k, v in day_counts.items()]

    # 热门被练真题 Top 10
    top_q_rows = (
        await db.execute(
            select(GradingTask.question_id, GradingTask.question_title, func.count(GradingTask.task_id).label("cnt"))
            .group_by(GradingTask.question_id, GradingTask.question_title)
            .order_by(desc("cnt"))
            .limit(10)
        )
    ).all()

    finished_total = completed_tasks + failed_tasks
    success_rate = round((completed_tasks / finished_total) * 100, 1) if finished_total > 0 else 100.0

    return {
        "total_users": total_users,
        "today_users": today_users,
        "active_vips": active_vips,
        "total_tasks": total_tasks,
        "today_tasks": today_tasks,
        "completed_tasks": completed_tasks,
        "failed_tasks": failed_tasks,
        "success_rate": success_rate,
        "total_questions": total_questions,
        "short_total": short_total,
        "short_with_points": short_with_points,
        "unused_codes": unused_codes,
        "used_codes": used_codes,
        "trend_7d": trend_7d,
        "top_questions": [{"question_id": r[0], "title": r[1], "count": r[2]} for r in top_q_rows],
    }


# =========================
# 2. 批改记录、质检详情与退次
# =========================

@router.get("/tasks", dependencies=[Depends(verify_admin)])
async def admin_list_tasks(
    status: Optional[str] = Query(default=None),
    exam_type: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(GradingTask)
    cnt_stmt = select(func.count(GradingTask.task_id))

    if status:
        stmt = stmt.where(GradingTask.status == status)
        cnt_stmt = cnt_stmt.where(GradingTask.status == status)
    if exam_type:
        stmt = stmt.where(GradingTask.exam_type == exam_type)
        cnt_stmt = cnt_stmt.where(GradingTask.exam_type == exam_type)
    if keyword:
        like = f"%{keyword.strip()}%"
        cond = or_(
            GradingTask.question_title.ilike(like),
            GradingTask.task_id.ilike(like),
            GradingTask.question_id.ilike(like),
        )
        stmt = stmt.where(cond)
        cnt_stmt = cnt_stmt.where(cond)

    total = await db.scalar(cnt_stmt) or 0
    rows = (
        await db.execute(
            stmt.order_by(desc(GradingTask.created_at)).offset((page - 1) * page_size).limit(page_size)
        )
    ).scalars().all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "task_id": t.task_id,
                "user_id": t.user_id,
                "question_id": t.question_id,
                "exam_type": t.exam_type,
                "question_title": t.question_title,
                "status": t.status,
                "final_score": t.final_score,
                "full_score": t.full_score,
                "band_label": t.band_label,
                "has_image": bool(t.image_path),
                "error_message": t.error_message,
                "created_at": t.created_at,
                "finished_at": t.finished_at,
            }
            for t in rows
        ],
    }


@router.get("/tasks/{task_id}", dependencies=[Depends(verify_admin)])
async def admin_task_detail(task_id: str, db: AsyncSession = Depends(get_db)):
    t = await db.get(GradingTask, task_id)
    if not t:
        raise HTTPException(status_code=404, detail="批改任务不存在")
    user = await db.get(User, t.user_id)
    img_name = Path(t.image_path).name if t.image_path else None
    return {
        "task_id": t.task_id,
        "user_id": t.user_id,
        "user_nickname": user.nickname if user else "未知用户",
        "question_id": t.question_id,
        "exam_type": t.exam_type,
        "question_title": t.question_title,
        "status": t.status,
        "progress_message": t.progress_message,
        "error_message": t.error_message,
        "student_answer": t.student_answer,
        "image_filename": img_name,
        "final_score": t.final_score,
        "full_score": t.full_score,
        "band_label": t.band_label,
        "weakness_tags": t.weakness_tags or [],
        "report": t.report_json,
        "created_at": t.created_at,
        "finished_at": t.finished_at,
    }


@router.post("/tasks/{task_id}/refund", dependencies=[Depends(verify_admin)])
async def admin_refund_task(task_id: str, db: AsyncSession = Depends(get_db)):
    """售后一键退还该任务对应用户的 1 次精批额度"""
    t = await db.get(GradingTask, task_id)
    if not t:
        raise HTTPException(status_code=404, detail="任务不存在")
    user = await db.get(User, t.user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.paid_quota += 1
    await db.commit()
    return {"ok": True, "user_id": user.id, "paid_quota": user.paid_quota}


@router.get("/uploads/{filename}", dependencies=[Depends(verify_admin)])
async def admin_get_upload_image(filename: str):
    """安全返回用户上传的手写答卷原图供后台质检放大查看"""
    safe_path = (UPLOAD_DIR / Path(filename).name).resolve()
    if not str(safe_path).startswith(str(UPLOAD_DIR)) or not safe_path.exists():
        raise HTTPException(status_code=404, detail="原图不存在或已清理")
    return FileResponse(safe_path)


# =========================
# 3. 真题库与可视化采分点 CRUD
# =========================

@router.get("/questions", dependencies=[Depends(verify_admin)])
async def admin_list_questions(
    exam_type: Optional[str] = Query(default=None),
    region: Optional[str] = Query(default=None),
    has_points: Optional[str] = Query(default=None, description="yes / no"),
    keyword: Optional[str] = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(QuestionModel).where(~QuestionModel.question_id.startswith("CUSTOM_"))
    if exam_type:
        stmt = stmt.where(QuestionModel.exam_type == exam_type)
    if region:
        r_like = f"%{region.strip()}%"
        stmt = stmt.where(or_(QuestionModel.paper.ilike(r_like), QuestionModel.title.ilike(r_like)))
    if keyword:
        k_like = f"%{keyword.strip()}%"
        stmt = stmt.where(
            or_(
                QuestionModel.question_id.ilike(k_like),
                QuestionModel.title.ilike(k_like),
                QuestionModel.prompt.ilike(k_like),
            )
        )

    rows = (await db.execute(stmt.order_by(desc(QuestionModel.year), desc(QuestionModel.question_id)))).scalars().all()
    if has_points == "yes":
        rows = [q for q in rows if q.scoring_points and len(q.scoring_points) > 0]
    elif has_points == "no":
        rows = [q for q in rows if not q.scoring_points or len(q.scoring_points) == 0]

    total = len(rows)
    sliced = rows[(page - 1) * page_size : page * page_size]

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
                "material_len": len(q.material_summary or ""),
                "scoring_point_count": len(q.scoring_points or []),
                "has_reference": bool((q.reference_answer or "").strip()),
            }
            for q in sliced
        ],
    }


@router.get("/questions/{question_id}", dependencies=[Depends(verify_admin)])
async def admin_get_question(question_id: str, db: AsyncSession = Depends(get_db)):
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
        "material_summary": q.material_summary or "",
        "full_score": q.full_score,
        "min_words": q.min_words,
        "max_words": q.max_words,
        "scoring_points": q.scoring_points or [],
        "reference_answer": q.reference_answer or "",
    }


class QuestionUpsertReq(BaseModel):
    question_id: Optional[str] = None
    exam_type: str = "shenlun_short"
    title: str = Field(..., min_length=2)
    year: int = 2026
    paper: str = ""
    sub_type: str = "单一题（归纳概括）"
    prompt: str = Field(..., min_length=5)
    material_summary: str = ""
    full_score: float = 15.0
    min_words: int = 0
    max_words: int = 300
    scoring_points: list[dict[str, Any]] = Field(default_factory=list)
    reference_answer: str = ""


@router.post("/questions", dependencies=[Depends(verify_admin)])
async def admin_create_question(req: QuestionUpsertReq, db: AsyncSession = Depends(get_db)):
    qid = (req.question_id or "").strip() or f"MAN-{req.year}-{secrets.token_hex(3).upper()}"
    if await db.get(QuestionModel, qid):
        raise HTTPException(status_code=400, detail=f"真题 ID {qid} 已存在")
    q = QuestionModel(
        question_id=qid,
        exam_type=req.exam_type,
        title=req.title,
        year=req.year,
        paper=req.paper,
        sub_type=req.sub_type,
        prompt=req.prompt,
        material_summary=req.material_summary,
        full_score=req.full_score,
        min_words=req.min_words,
        max_words=req.max_words,
        scoring_points=req.scoring_points,
        reference_answer=req.reference_answer,
    )
    db.add(q)
    await db.commit()
    return {"ok": True, "question_id": qid}


@router.put("/questions/{question_id}", dependencies=[Depends(verify_admin)])
async def admin_update_question(question_id: str, req: QuestionUpsertReq, db: AsyncSession = Depends(get_db)):
    q = await db.get(QuestionModel, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="真题不存在")
    q.exam_type = req.exam_type
    q.title = req.title
    q.year = req.year
    q.paper = req.paper
    q.sub_type = req.sub_type
    q.prompt = req.prompt
    q.material_summary = req.material_summary
    q.full_score = req.full_score
    q.min_words = req.min_words
    q.max_words = req.max_words
    q.scoring_points = req.scoring_points
    q.reference_answer = req.reference_answer
    await db.commit()
    return {"ok": True}


@router.delete("/questions/{question_id}", dependencies=[Depends(verify_admin)])
async def admin_delete_question(question_id: str, db: AsyncSession = Depends(get_db)):
    q = await db.get(QuestionModel, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="真题不存在")
    await db.delete(q)
    await db.commit()
    return {"ok": True}


@router.post("/questions/{question_id}/generate-points", dependencies=[Depends(verify_admin)])
async def admin_generate_points(question_id: str, db: AsyncSession = Depends(get_db)):
    """后台一键触发大模型基于完整材料为该题生成 v2 标准采分点"""
    q = await db.get(QuestionModel, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="真题不存在")
    schema_q = Question(
        question_id=q.question_id,
        exam_type=ExamType(q.exam_type),
        title=q.title,
        year=q.year,
        paper=q.paper,
        sub_type=q.sub_type,
        prompt=q.prompt,
        material_summary=q.material_summary or "",
        full_score=q.full_score,
        min_words=q.min_words,
        max_words=q.max_words,
        scoring_points=[ScoringPoint.model_validate(p) for p in (q.scoring_points or [])],
        reference_answer=q.reference_answer or "",
    )
    router_client = LLMRouter()
    pts, ref_ans, sub_type = await build_grounded_scoring_points(router_client, schema_q)
    q.scoring_points = [p.model_dump() for p in pts]
    if ref_ans:
        q.reference_answer = ref_ans
    if sub_type:
        q.sub_type = sub_type
    await db.commit()
    return {"ok": True, "scoring_points": q.scoring_points, "reference_answer": q.reference_answer}


# =========================
# 4. 用户管理
# =========================

@router.get("/users", dependencies=[Depends(verify_admin)])
async def admin_list_users(
    keyword: Optional[str] = Query(default=None),
    vip_only: bool = Query(default=False),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    now = datetime.utcnow()
    stmt = select(User)
    cnt_stmt = select(func.count(User.id))

    if keyword:
        like = f"%{keyword.strip()}%"
        cond = or_(
            User.username.ilike(like),
            User.nickname.ilike(like),
            User.openid.ilike(like),
        )
        stmt = stmt.where(cond)
        cnt_stmt = cnt_stmt.where(cond)
    if vip_only:
        stmt = stmt.where(User.vip_expire_at > now)
        cnt_stmt = cnt_stmt.where(User.vip_expire_at > now)

    total = await db.scalar(cnt_stmt) or 0
    rows = (
        await db.execute(stmt.order_by(desc(User.created_at)).offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    user_ids = [u.id for u in rows]
    task_counts: dict[int, int] = {}
    if user_ids:
        tc_rows = (
            await db.execute(
                select(GradingTask.user_id, func.count(GradingTask.task_id))
                .where(GradingTask.user_id.in_(user_ids))
                .group_by(GradingTask.user_id)
            )
        ).all()
        task_counts = {uid: cnt for uid, cnt in tc_rows}

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [
            {
                "user_id": u.id,
                "username": u.username,
                "openid": u.openid,
                "nickname": u.nickname,
                "free_quota": u.free_quota,
                "paid_quota": u.paid_quota,
                "is_vip": bool(u.vip_expire_at and u.vip_expire_at > now),
                "vip_expire_at": u.vip_expire_at,
                "task_count": task_counts.get(u.id, 0),
                "created_at": u.created_at,
            }
            for u in rows
        ],
    }


class AdjustUserReq(BaseModel):
    add_quota: int = Field(default=0, ge=-100, le=500)
    add_vip_days: int = Field(default=0, ge=0, le=365)


@router.post("/users/{user_id}/adjust", dependencies=[Depends(verify_admin)])
async def admin_adjust_user(user_id: int, req: AdjustUserReq, db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if req.add_quota:
        user.paid_quota = max(0, user.paid_quota + req.add_quota)
    if req.add_vip_days > 0:
        now = datetime.utcnow()
        base = user.vip_expire_at if (user.vip_expire_at and user.vip_expire_at > now) else now
        user.vip_expire_at = base + timedelta(days=req.add_vip_days)
    await db.commit()
    return {"ok": True, "paid_quota": user.paid_quota, "vip_expire_at": user.vip_expire_at}


class ResetPasswordReq(BaseModel):
    new_password: str = Field(..., min_length=6, max_length=64, description="新登录密码（6-64位）")


@router.post("/users/{user_id}/reset-password", dependencies=[Depends(verify_admin)])
async def admin_reset_user_password(
    user_id: int,
    req: ResetPasswordReq,
    db: AsyncSession = Depends(get_db),
):
    """售后一键重置 PC 端用户登录密码"""
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if not user.username:
        raise HTTPException(status_code=400, detail="该用户为纯微信登录账号，未绑定 PC 密码登录")
    user.password_hash = hash_password(req.new_password)
    await db.commit()
    return {"ok": True, "user_id": user.id, "username": user.username}


# =========================
# 5. 兑换码生成、作废与 CSV 导出
# =========================

class GenCodeReq(BaseModel):
    count: int = Field(default=5, ge=1, le=200)
    add_quota: int = Field(default=5, ge=0, le=500)
    add_vip_days: int = Field(default=0, ge=0, le=365)
    plan_name: str = Field(default="冲刺体验包(5次)", min_length=1, max_length=64)


@router.post("/codes", dependencies=[Depends(verify_admin)])
async def admin_generate_codes(req: GenCodeReq, db: AsyncSession = Depends(get_db)):
    alphabet = string.ascii_uppercase + string.digits
    prefix = "VIP" if req.add_vip_days > 0 else "RP"
    created: list[str] = []
    for _ in range(req.count):
        body = "".join(secrets.choice(alphabet) for _ in range(8))
        code = f"{prefix}-{body[:4]}-{body[4:]}"
        db.add(
            RedeemCode(
                code=code,
                plan_name=req.plan_name,
                add_quota=req.add_quota,
                add_vip_days=req.add_vip_days,
            )
        )
        created.append(code)
    await db.commit()
    return {"created": created}


@router.get("/codes", dependencies=[Depends(verify_admin)])
async def admin_list_codes(
    status: str = Query(default="all", description="all / unused / used"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(RedeemCode)
    cnt_stmt = select(func.count(RedeemCode.code))
    if status == "unused":
        stmt = stmt.where(RedeemCode.is_used == 0)
        cnt_stmt = cnt_stmt.where(RedeemCode.is_used == 0)
    elif status == "used":
        stmt = stmt.where(RedeemCode.is_used == 1)
        cnt_stmt = cnt_stmt.where(RedeemCode.is_used == 1)

    total = await db.scalar(cnt_stmt) or 0
    rows = (
        await db.execute(stmt.order_by(desc(RedeemCode.created_at)).offset((page - 1) * page_size).limit(page_size))
    ).scalars().all()

    return {
        "total": total,
        "items": [
            {
                "code": r.code,
                "plan_name": r.plan_name,
                "add_quota": r.add_quota,
                "add_vip_days": r.add_vip_days,
                "is_used": bool(r.is_used),
                "used_by_user_id": r.used_by_user_id,
                "used_at": r.used_at,
                "created_at": r.created_at,
            }
            for r in rows
        ],
    }


@router.delete("/codes/{code}", dependencies=[Depends(verify_admin)])
async def admin_delete_code(code: str, db: AsyncSession = Depends(get_db)):
    row = await db.get(RedeemCode, code)
    if not row:
        raise HTTPException(status_code=404, detail="兑换码不存在")
    if row.is_used:
        raise HTTPException(status_code=400, detail="已核销的兑换码不可删除")
    await db.delete(row)
    await db.commit()
    return {"ok": True}


@router.get("/codes/export", dependencies=[Depends(verify_admin)])
async def admin_export_unused_codes(db: AsyncSession = Depends(get_db)):
    """一键导出所有未使用卡密为 CSV（可直接导入小红书/淘宝自动发货）"""
    rows = (
        await db.execute(select(RedeemCode).where(RedeemCode.is_used == 0).order_by(desc(RedeemCode.created_at)))
    ).scalars().all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["兑换码", "套餐名称", "精批次数", "月卡天数", "创建时间"])
    for r in rows:
        writer.writerow([r.code, r.plan_name, r.add_quota, r.add_vip_days, r.created_at.strftime("%Y-%m-%d %H:%M")])
    csv_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=zhixingdao_codes.csv"},
    )


# =========================
# 6. 系统状态与大模型连通性自检
# =========================

def _mask_key(key: str) -> str:
    if not settings.key_is_configured(key):
        return "未配置"
    return f"{key[:6]}...{key[-4:]}" if len(key) > 10 else "已配置"


@router.get("/system", dependencies=[Depends(verify_admin)])
async def admin_system_info():
    db_type = "PostgreSQL" if "postgresql" in settings.database_url else "SQLite (本地)"
    return {
        "llm_model": settings.llm_model,
        "llm_base_url": settings.llm_base_url,
        "llm_key_masked": _mask_key(settings.llm_api_key),
        "vlm_model": settings.vlm_model,
        "vlm_base_url": settings.effective_vlm_base_url,
        "vlm_key_masked": _mask_key(settings.effective_vlm_api_key),
        "database_type": db_type,
        "mock_fallback_enabled": settings.enable_mock_fallback,
        "wx_appid_configured": bool(settings.wx_appid and settings.wx_secret),
    }


@router.post("/system/ping-llm", dependencies=[Depends(verify_admin)])
async def admin_ping_llm():
    if not settings.key_is_configured(settings.llm_api_key):
        return {"ok": False, "detail": "未配置 LLM_API_KEY"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                f"{settings.llm_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm_api_key}"},
                json={"model": settings.llm_model, "messages": [{"role": "user", "content": "ping"}], "max_tokens": 5},
            )
        if r.status_code == 200:
            return {"ok": True, "detail": f"{settings.llm_model} 连接正常、余额充足！"}
        return {"ok": False, "detail": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"ok": False, "detail": str(e)}
