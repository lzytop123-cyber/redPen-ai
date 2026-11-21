import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_utils import create_access_token, get_current_user
from app.config import settings
from app.db.database import get_db
from app.db.models import RedeemCode, User

router = APIRouter(prefix="/api/auth", tags=["认证与用户"])

_USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,32}$")


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt}${dk.hex()}"


def verify_password(password: str, stored_hash: Optional[str]) -> bool:
    if not stored_hash:
        return False
    try:
        algo, salt, digest = stored_hash.split("$", 2)
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
        return hmac.compare_digest(dk.hex(), digest)
    except Exception:
        return False


class WxLoginReq(BaseModel):
    code: str
    nickname: Optional[str] = None


class RegisterReq(BaseModel):
    username: str = Field(..., min_length=3, max_length=32, description="手机号或账号（3-32位字母/数字/下划线）")
    password: str = Field(..., min_length=6, max_length=64, description="登录密码（6-64位）")
    nickname: Optional[str] = Field(default=None, max_length=32, description="显示昵称")


class LoginReq(BaseModel):
    username: str = Field(..., min_length=3, max_length=32)
    password: str = Field(..., min_length=6, max_length=64)


class UpdateProfileReq(BaseModel):
    nickname: str = Field(..., min_length=1, max_length=32)


class UserInfoResp(BaseModel):
    user_id: int
    username: Optional[str] = None
    nickname: str
    free_quota: int
    paid_quota: int
    is_vip: bool
    vip_expire_at: Optional[datetime] = None


class LoginResp(BaseModel):
    token: str
    user: UserInfoResp


def _to_user_resp(user: User) -> UserInfoResp:
    is_vip = bool(user.vip_expire_at and user.vip_expire_at > datetime.utcnow())
    return UserInfoResp(
        user_id=user.id,
        username=user.username,
        nickname=user.nickname,
        free_quota=user.free_quota,
        paid_quota=user.paid_quota,
        is_vip=is_vip,
        vip_expire_at=user.vip_expire_at,
    )


@router.post("/register", response_model=LoginResp)
async def register_web_account(req: RegisterReq, db: AsyncSession = Depends(get_db)):
    """PC Web 端账号/手机号 + 密码注册，新人自动赠送 3 次精批体验额度"""
    uname = req.username.strip()
    if not _USERNAME_RE.match(uname):
        raise HTTPException(status_code=400, detail="账号仅支持 3~32 位数字、字母、下划线、点或短横线")

    exists = (await db.execute(select(User).where(User.username == uname))).scalar_one_or_none()
    if exists:
        raise HTTPException(status_code=409, detail="该账号已注册，请直接登录")

    display_name = (req.nickname or "").strip() or (
        f"考生{uname[-4:]}" if uname.isdigit() and len(uname) >= 7 else uname
    )
    user = User(
        openid=f"web_{uname}_{secrets.token_hex(4)}",
        username=uname,
        password_hash=hash_password(req.password),
        nickname=display_name,
        free_quota=3,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)

    token = create_access_token(user.id)
    return LoginResp(token=token, user=_to_user_resp(user))


@router.post("/login", response_model=LoginResp)
async def login_web_account(req: LoginReq, db: AsyncSession = Depends(get_db)):
    """PC Web 端账号/手机号 + 密码登录"""
    uname = req.username.strip()
    user = (await db.execute(select(User).where(User.username == uname))).scalar_one_or_none()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="账号或密码错误")

    token = create_access_token(user.id)
    return LoginResp(token=token, user=_to_user_resp(user))


@router.post("/wx-login", response_model=LoginResp)
async def wx_login(req: WxLoginReq, db: AsyncSession = Depends(get_db)):
    """微信小程序 wx.login 登录换取 OpenID 与 JWT Token"""
    if settings.wechat_is_configured:
        url = "https://api.weixin.qq.com/sns/jscode2session"
        params = {
            "appid": settings.wx_appid.strip(),
            "secret": settings.wx_secret.strip(),
            "js_code": req.code,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params)
            data = r.json()
        if "openid" not in data:
            raise HTTPException(status_code=400, detail=f"微信登录失败: {data.get('errmsg', 'unknown')}")
        openid = data["openid"]
    elif settings.allows_dev_wechat_identity:
        openid = f"dev_{req.code[:24]}"
    else:
        raise HTTPException(status_code=503, detail="微信登录未配置 WX_APPID/WX_SECRET")

    res = await db.execute(select(User).where(User.openid == openid))
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            openid=openid,
            nickname=req.nickname or "上岸备考人",
            free_quota=3,
        )
        db.add(user)
        await db.commit()
        await db.refresh(user)

    token = create_access_token(user.id)
    return LoginResp(token=token, user=_to_user_resp(user))


@router.get("/me", response_model=UserInfoResp)
async def get_me(user: User = Depends(get_current_user)):
    """获取当前用户精批额度与会员状态"""
    return _to_user_resp(user)


@router.patch("/profile", response_model=UserInfoResp)
async def update_profile(
    req: UpdateProfileReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """更新用户昵称"""
    user.nickname = req.nickname.strip()
    await db.commit()
    await db.refresh(user)
    return _to_user_resp(user)


class RedeemReq(BaseModel):
    code: str = Field(..., min_length=4, max_length=32, description="激活兑换码")


@router.post("/redeem")
async def redeem_code(
    req: RedeemReq,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """核销兑换码：原子条件更新防并发双花，自动发放按次精批额度或延长上岸月卡天数"""
    normalized = req.code.strip().upper()
    row = await db.get(RedeemCode, normalized)
    if not row:
        raise HTTPException(status_code=404, detail="兑换码不存在，请核对后重试")
    if row.is_used:
        raise HTTPException(status_code=400, detail="该兑换码已被使用")

    now = datetime.utcnow()
    claim = await db.execute(
        update(RedeemCode)
        .where(RedeemCode.code == normalized, RedeemCode.is_used == 0)
        .values(is_used=1, used_by_user_id=user.id, used_at=now)
    )
    if claim.rowcount != 1:
        await db.rollback()
        raise HTTPException(status_code=400, detail="该兑换码已被使用")

    if row.add_quota > 0:
        user.paid_quota += row.add_quota
    if row.add_vip_days > 0:
        base = user.vip_expire_at if (user.vip_expire_at and user.vip_expire_at > now) else now
        user.vip_expire_at = base + timedelta(days=row.add_vip_days)

    await db.commit()
    await db.refresh(user)

    return {
        "message": f"兑换成功！已到账【{row.plan_name}】",
        "user": _to_user_resp(user),
    }
