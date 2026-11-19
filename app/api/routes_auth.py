from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth_utils import create_access_token, get_current_user
from app.config import settings
from app.db.database import get_db
from app.db.models import User

router = APIRouter(prefix="/api/auth", tags=["认证与用户"])


class WxLoginReq(BaseModel):
    code: str
    nickname: Optional[str] = None


class UserInfoResp(BaseModel):
    user_id: int
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
        nickname=user.nickname,
        free_quota=user.free_quota,
        paid_quota=user.paid_quota,
        is_vip=is_vip,
        vip_expire_at=user.vip_expire_at,
    )


@router.post("/wx-login", response_model=LoginResp)
async def wx_login(req: WxLoginReq, db: AsyncSession = Depends(get_db)):
    """微信小程序 wx.login 登录换取 OpenID 与 JWT Token"""
    if settings.wx_appid and settings.wx_secret:
        url = "https://api.weixin.qq.com/sns/jscode2session"
        params = {
            "appid": settings.wx_appid,
            "secret": settings.wx_secret,
            "js_code": req.code,
            "grant_type": "authorization_code",
        }
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(url, params=params)
            data = r.json()
        if "openid" not in data:
            raise HTTPException(status_code=400, detail=f"微信登录失败: {data.get('errmsg', 'unknown')}")
        openid = data["openid"]
    else:
        # 本地未配置 AppID/Secret 时，基于 code 生成稳定的开发用 OpenID
        openid = f"dev_{req.code[:24]}"

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
