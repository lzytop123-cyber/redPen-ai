"""
知行岛申论精批 — 轻量级运营管理后台 (/admin 与 /api/admin/*)
内置在 FastAPI 中，零额外前端部署成本，通过 ADMIN_PASSWORD 保护。
支持：运营数据看板、兑换码批量生成与核销查询、用户售后补次/开月卡、任务监控与题库采分点在线微调。
"""

import secrets
import string
from datetime import datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.db.models import GradingTask, QuestionModel, RedeemCode, User

router = APIRouter(tags=["运营后台"])


def verify_admin(x_admin_password: Optional[str] = Header(default=None)) -> None:
    if not x_admin_password or x_admin_password != settings.admin_password:
        raise HTTPException(status_code=401, detail="管理员密码错误")


@router.get("/api/admin/stats", dependencies=[Depends(verify_admin)])
async def admin_stats(db: AsyncSession = Depends(get_db)):
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    total_users = await db.scalar(select(func.count(User.id))) or 0
    total_tasks = await db.scalar(select(func.count(GradingTask.task_id))) or 0
    today_tasks = (
        await db.scalar(select(func.count(GradingTask.task_id)).where(GradingTask.created_at >= today_start)) or 0
    )
    failed_tasks = (
        await db.scalar(select(func.count(GradingTask.task_id)).where(GradingTask.status == "failed")) or 0
    )
    total_questions = (
        await db.scalar(
            select(func.count(QuestionModel.question_id)).where(~QuestionModel.question_id.startswith("CUSTOM_"))
        )
        or 0
    )
    unused_codes = await db.scalar(select(func.count(RedeemCode.code)).where(RedeemCode.is_used == 0)) or 0
    used_codes = await db.scalar(select(func.count(RedeemCode.code)).where(RedeemCode.is_used == 1)) or 0

    return {
        "total_users": total_users,
        "total_tasks": total_tasks,
        "today_tasks": today_tasks,
        "failed_tasks": failed_tasks,
        "total_questions": total_questions,
        "unused_codes": unused_codes,
        "used_codes": used_codes,
    }


class GenCodeReq(BaseModel):
    count: int = Field(default=5, ge=1, le=100)
    add_quota: int = Field(default=5, ge=0, le=500)
    add_vip_days: int = Field(default=0, ge=0, le=365)
    plan_name: str = Field(default="冲刺体验包(5次)", min_length=1, max_length=64)


@router.post("/api/admin/codes", dependencies=[Depends(verify_admin)])
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


@router.get("/api/admin/codes", dependencies=[Depends(verify_admin)])
async def admin_list_codes(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(RedeemCode).order_by(desc(RedeemCode.created_at)).limit(100))).scalars().all()
    return {
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
        ]
    }


@router.get("/api/admin/users", dependencies=[Depends(verify_admin)])
async def admin_list_users(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(User).order_by(desc(User.created_at)).limit(100))).scalars().all()
    now = datetime.utcnow()
    return {
        "items": [
            {
                "user_id": u.id,
                "openid": u.openid,
                "nickname": u.nickname,
                "free_quota": u.free_quota,
                "paid_quota": u.paid_quota,
                "is_vip": bool(u.vip_expire_at and u.vip_expire_at > now),
                "vip_expire_at": u.vip_expire_at,
                "created_at": u.created_at,
            }
            for u in rows
        ]
    }


class AdjustUserReq(BaseModel):
    add_quota: int = Field(default=0, ge=-100, le=500)
    add_vip_days: int = Field(default=0, ge=0, le=365)


@router.post("/api/admin/users/{user_id}/adjust", dependencies=[Depends(verify_admin)])
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


@router.get("/api/admin/tasks", dependencies=[Depends(verify_admin)])
async def admin_list_tasks(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(GradingTask).order_by(desc(GradingTask.created_at)).limit(50))).scalars().all()
    return {
        "items": [
            {
                "task_id": t.task_id,
                "user_id": t.user_id,
                "question_id": t.question_id,
                "question_title": t.question_title,
                "status": t.status,
                "final_score": t.final_score,
                "full_score": t.full_score,
                "error_message": t.error_message,
                "created_at": t.created_at,
            }
            for t in rows
        ]
    }


@router.get("/api/admin/questions/{question_id}", dependencies=[Depends(verify_admin)])
async def admin_get_question(question_id: str, db: AsyncSession = Depends(get_db)):
    q = await db.get(QuestionModel, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="真题不存在")
    return {
        "question_id": q.question_id,
        "title": q.title,
        "full_score": q.full_score,
        "scoring_points": q.scoring_points or [],
        "reference_answer": q.reference_answer or "",
    }


class UpdateQuestionPointsReq(BaseModel):
    scoring_points: list[dict[str, Any]]
    reference_answer: str = ""


@router.put("/api/admin/questions/{question_id}", dependencies=[Depends(verify_admin)])
async def admin_update_question(question_id: str, req: UpdateQuestionPointsReq, db: AsyncSession = Depends(get_db)):
    q = await db.get(QuestionModel, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="真题不存在")
    q.scoring_points = req.scoring_points
    q.reference_answer = req.reference_answer
    await db.commit()
    return {"ok": True}


ADMIN_HTML = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8" />
<meta name="viewport" content="width=device-width,initial-scale=1" />
<title>知行岛申论精批 · 运营后台</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; margin: 0; background: #f3f4f6; color: #1f2937; }
  header { background: #1e3a8a; color: #fff; padding: 16px 24px; display: flex; justify-content: space-between; align-items: center; }
  header h1 { margin: 0; font-size: 18px; }
  .wrap { max-width: 1120px; margin: 20px auto; padding: 0 16px 60px; }
  .card { background: #fff; border-radius: 12px; padding: 20px; margin-bottom: 18px; box-shadow: 0 2px 8px rgba(0,0,0,.04); }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; }
  .stat { background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 10px; padding: 14px; }
  .stat .num { font-size: 26px; font-weight: 800; color: #1d4ed8; }
  .stat .lbl { font-size: 12px; color: #64748b; margin-top: 4px; }
  .tabs { display: flex; gap: 10px; margin-bottom: 16px; flex-wrap: wrap; }
  .tab { padding: 8px 16px; border-radius: 8px; background: #e5e7eb; cursor: pointer; font-size: 14px; border: 0; }
  .tab.active { background: #2563eb; color: #fff; font-weight: 600; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th, td { border-bottom: 1px solid #e5e7eb; padding: 10px 8px; text-align: left; }
  th { background: #f9fafb; color: #4b5563; }
  input, textarea { border: 1px solid #d1d5db; border-radius: 8px; padding: 8px 10px; font-size: 14px; }
  button.primary { background: #2563eb; color: #fff; border: 0; border-radius: 8px; padding: 8px 16px; cursor: pointer; font-weight: 600; }
  button.sm { padding: 4px 10px; font-size: 12px; border-radius: 6px; border: 1px solid #93c5fd; background: #eff6ff; color: #1d4ed8; cursor: pointer; margin-right: 4px; }
  .badge { padding: 2px 8px; border-radius: 99px; font-size: 12px; }
  .ok { background: #dcfce7; color: #166534; }
  .err { background: #fee2e2; color: #991b1b; }
  .row-form { display: flex; gap: 10px; flex-wrap: wrap; align-items: center; margin-bottom: 14px; }
  .hidden { display: none; }
</style>
</head>
<body>
<header>
  <h1>知行岛申论精批 · 运营管理后台</h1>
  <button id="logoutBtn" class="sm hidden" onclick="logout()">退出登录</button>
</header>
<div class="wrap">
  <div id="loginCard" class="card" style="max-width:420px;margin:60px auto;">
    <h2 style="margin-top:0;font-size:18px;">管理员登录</h2>
    <p style="font-size:13px;color:#6b7280;">请输入 .env 中配置的 ADMIN_PASSWORD（本地默认 admin123）</p>
    <div class="row-form">
      <input id="pwdInput" type="password" placeholder="管理员密码" style="flex:1;" />
      <button class="primary" onclick="login()">登录</button>
    </div>
    <div id="loginErr" style="color:#dc2626;font-size:13px;"></div>
  </div>

  <div id="mainApp" class="hidden">
    <div class="card">
      <div class="grid" id="statsGrid"></div>
    </div>

    <div class="tabs">
      <button class="tab active" onclick="switchTab('codes', this)">🎁 兑换码发卡</button>
      <button class="tab" onclick="switchTab('users', this)">👥 用户与补次</button>
      <button class="tab" onclick="switchTab('tasks', this)">📝 批改监控</button>
      <button class="tab" onclick="switchTab('questions', this)">📚 采分点微调</button>
    </div>

    <div id="tab-codes" class="card">
      <div class="row-form">
        <input id="cName" value="冲刺体验包(5次)" placeholder="套餐名" />
        <input id="cCount" type="number" value="5" style="width:70px;" /> 个
        <input id="cQuota" type="number" value="5" style="width:70px;" /> 次
        <input id="cVip" type="number" value="0" style="width:70px;" /> 天月卡
        <button class="primary" onclick="genCodes()">一键生成</button>
      </div>
      <div id="newCodesBox" style="background:#f0fdf4;padding:12px;border-radius:8px;margin-bottom:12px;display:none;white-space:pre-wrap;font-family:monospace;"></div>
      <table><thead><tr><th>兑换码</th><th>套餐</th><th>额度</th><th>状态</th><th>使用用户</th></tr></thead><tbody id="codesBody"></tbody></table>
    </div>

    <div id="tab-users" class="card hidden">
      <table><thead><tr><th>ID</th><th>昵称</th><th>免费余次</th><th>付费余次</th><th>月卡</th><th>售后操作</th></tr></thead><tbody id="usersBody"></tbody></table>
    </div>

    <div id="tab-tasks" class="card hidden">
      <table><thead><tr><th>任务ID</th><th>用户</th><th>题目</th><th>状态</th><th>得分</th><th>错误信息</th></tr></thead><tbody id="tasksBody"></tbody></table>
    </div>

    <div id="tab-questions" class="card hidden">
      <div class="row-form">
        <input id="qIdInput" placeholder="输入真题ID，如 GK-2026-zf-S04" style="width:260px;" />
        <button class="primary" onclick="loadQuestion()">查询真题</button>
      </div>
      <div id="qEditor" class="hidden">
        <h3 id="qTitle" style="margin:8px 0;"></h3>
        <div style="font-size:13px;color:#4b5563;margin-bottom:6px;">标准采分点 JSON（可增删改分值与关键词）：</div>
        <textarea id="qPoints" style="width:100%;height:240px;font-family:monospace;box-sizing:border-box;"></textarea>
        <div style="font-size:13px;color:#4b5563;margin:10px 0 6px;">参考答案 / 立意解析：</div>
        <textarea id="qRef" style="width:100%;height:140px;box-sizing:border-box;"></textarea>
        <div style="margin-top:12px;"><button class="primary" onclick="saveQuestion()">保存并立即生效</button></div>
      </div>
    </div>
  </div>
</div>

<script>
let PWD = sessionStorage.getItem('admin_pwd') || '';
async function api(url, opts={}) {
  const res = await fetch(url, {
    ...opts,
    headers: { 'Content-Type': 'application/json', 'X-Admin-Password': PWD, ...(opts.headers||{}) }
  });
  if (!res.ok) { const d = await res.json().catch(()=>({})); throw new Error(d.detail || res.status); }
  return res.json();
}
async function login() {
  PWD = document.getElementById('pwdInput').value.trim();
  try {
    await refreshAll();
    sessionStorage.setItem('admin_pwd', PWD);
    document.getElementById('loginCard').classList.add('hidden');
    document.getElementById('mainApp').classList.remove('hidden');
    document.getElementById('logoutBtn').classList.remove('hidden');
  } catch (e) { document.getElementById('loginErr').textContent = '登录失败：' + e.message; }
}
function logout() { sessionStorage.removeItem('admin_pwd'); location.reload(); }
function switchTab(name, el) {
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  el.classList.add('active');
  ['codes','users','tasks','questions'].forEach(k => document.getElementById('tab-'+k).classList.toggle('hidden', k!==name));
}
async function refreshAll() {
  const s = await api('/api/admin/stats');
  document.getElementById('statsGrid').innerHTML = [
    ['总用户数', s.total_users], ['今日批改', s.today_tasks], ['累计批改', s.total_tasks],
    ['失败任务', s.failed_tasks], ['题库总数', s.total_questions], ['未核销码', s.unused_codes], ['已核销码', s.used_codes]
  ].map(([l,n]) => `<div class="stat"><div class="num">${n}</div><div class="lbl">${l}</div></div>`).join('');

  const c = await api('/api/admin/codes');
  document.getElementById('codesBody').innerHTML = c.items.map(r => `<tr>
    <td><b>${r.code}</b></td><td>${r.plan_name}</td><td>+${r.add_quota}次 / +${r.add_vip_days}天</td>
    <td><span class="badge ${r.is_used?'err':'ok'}">${r.is_used?'已核销':'可用'}</span></td>
    <td>${r.used_by_user_id || '-'}</td></tr>`).join('');

  const u = await api('/api/admin/users');
  document.getElementById('usersBody').innerHTML = u.items.map(r => `<tr>
    <td>${r.user_id}</td><td>${r.nickname}</td><td>${r.free_quota}</td><td>${r.paid_quota}</td>
    <td>${r.is_vip ? '生效中' : '-'}</td>
    <td><button class="sm" onclick="adjustUser(${r.user_id},5,0)">+5次</button>
    <button class="sm" onclick="adjustUser(${r.user_id},0,30)">+30天月卡</button></td></tr>`).join('');

  const t = await api('/api/admin/tasks');
  document.getElementById('tasksBody').innerHTML = t.items.map(r => `<tr>
    <td>${r.task_id}</td><td>${r.user_id}</td><td>${r.question_title}</td>
    <td><span class="badge ${r.status==='failed'?'err':'ok'}">${r.status}</span></td>
    <td>${r.final_score ?? '-'} / ${r.full_score ?? '-'}</td>
    <td style="color:#dc2626;max-width:260px;word-break:break-all;">${r.error_message || ''}</td></tr>`).join('');
}
async function genCodes() {
  const res = await api('/api/admin/codes', { method: 'POST', body: JSON.stringify({
    plan_name: document.getElementById('cName').value,
    count: Number(document.getElementById('cCount').value),
    add_quota: Number(document.getElementById('cQuota').value),
    add_vip_days: Number(document.getElementById('cVip').value),
  })});
  const box = document.getElementById('newCodesBox');
  box.style.display = 'block';
  box.textContent = '新生成的兑换码（可直接复制发货）：\\n' + res.created.join('\\n');
  refreshAll();
}
async function adjustUser(uid, q, v) {
  await api(`/api/admin/users/${uid}/adjust`, { method: 'POST', body: JSON.stringify({ add_quota: q, add_vip_days: v }) });
  alert('已更新用户额度！');
  refreshAll();
}
let currentQid = '';
async function loadQuestion() {
  const qid = document.getElementById('qIdInput').value.trim();
  if (!qid) return;
  const q = await api('/api/admin/questions/' + encodeURIComponent(qid));
  currentQid = q.question_id;
  document.getElementById('qTitle').textContent = `${q.question_id} · ${q.title} (满分 ${q.full_score})`;
  document.getElementById('qPoints').value = JSON.stringify(q.scoring_points, null, 2);
  document.getElementById('qRef').value = q.reference_answer || '';
  document.getElementById('qEditor').classList.remove('hidden');
}
async function saveQuestion() {
  const pts = JSON.parse(document.getElementById('qPoints').value);
  await api('/api/admin/questions/' + encodeURIComponent(currentQid), {
    method: 'PUT', body: JSON.stringify({ scoring_points: pts, reference_answer: document.getElementById('qRef').value })
  });
  alert('采分点已保存并立即生效！');
}
if (PWD) { document.getElementById('pwdInput').value = PWD; login(); }
</script>
</body>
</html>"""


@router.get("/admin", response_class=HTMLResponse)
async def admin_page():
    """运营管理后台单页应用"""
    return HTMLResponse(content=ADMIN_HTML)
