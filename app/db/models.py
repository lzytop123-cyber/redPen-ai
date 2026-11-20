from datetime import datetime
from typing import Any, Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base

# PostgreSQL 下自动使用 JSONB，SQLite 本地调试下自动退化为 JSON
FlexibleJSON = JSON().with_variant(JSONB(), "postgresql")


class User(Base):
    """用户表（支持微信小程序 OpenID 登录 + 免费/付费精批额度管理）"""
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    openid: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)
    nickname: Mapped[str] = mapped_column(String(64), default="备考战友")
    free_quota: Mapped[int] = mapped_column(Integer, default=3)      # 新人默认送 3 次精批
    paid_quota: Mapped[int] = mapped_column(Integer, default=0)      # 按次购买的剩余次数
    vip_expire_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class QuestionModel(Base):
    """结构化真题与采分点库"""
    __tablename__ = "questions"

    question_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    exam_type: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    year: Mapped[int] = mapped_column(Integer, index=True, default=0)
    paper: Mapped[str] = mapped_column(String(128), default="")
    sub_type: Mapped[str] = mapped_column(String(64), index=True, default="")
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    material_summary: Mapped[str] = mapped_column(Text, default="")
    full_score: Mapped[float] = mapped_column(Float, default=15.0)
    min_words: Mapped[int] = mapped_column(Integer, default=0)
    max_words: Mapped[int] = mapped_column(Integer, default=0)
    scoring_points: Mapped[list[dict[str, Any]]] = mapped_column(FlexibleJSON, default=list)
    reference_answer: Mapped[str] = mapped_column(Text, default="")


class GradingTask(Base):
    """异步精批任务与报告沉淀表"""
    __tablename__ = "grading_tasks"

    task_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), index=True, nullable=False)
    question_id: Mapped[str] = mapped_column(String(64), ForeignKey("questions.question_id"), index=True, nullable=False)
    exam_type: Mapped[str] = mapped_column(String(32), nullable=False)
    question_title: Mapped[str] = mapped_column(String(255), nullable=False)

    status: Mapped[str] = mapped_column(String(24), index=True, default="pending")  # pending/running/completed/failed
    progress_message: Mapped[str] = mapped_column(String(255), default="任务已排队...")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    student_answer: Mapped[str] = mapped_column(Text, nullable=False)
    image_path: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    final_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    full_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    band_label: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    weakness_tags: Mapped[list[str]] = mapped_column(FlexibleJSON, default=list)
    report_json: Mapped[Optional[dict[str, Any]]] = mapped_column(FlexibleJSON, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class RedeemCode(Base):
    """兑换码表（支持按次包/月卡激活，规避 iOS 虚拟支付审核限制，适合自习室与小红书售卖）"""
    __tablename__ = "redeem_codes"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    plan_name: Mapped[str] = mapped_column(String(64), default="冲刺体验包")
    add_quota: Mapped[int] = mapped_column(Integer, default=0)      # 增加的按次精批额度
    add_vip_days: Mapped[int] = mapped_column(Integer, default=0)   # 增加的月卡天数
    is_used: Mapped[int] = mapped_column(Integer, default=0, index=True)
    used_by_user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
