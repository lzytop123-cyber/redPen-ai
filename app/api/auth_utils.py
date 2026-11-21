import base64
import hashlib
import hmac
import json
import time
from typing import Optional

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.database import get_db
from app.db.models import User


def create_access_token(user_id: int, expires_in: int = 86400 * 30) -> str:
    payload = {"uid": user_id, "exp": int(time.time()) + expires_in}
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    b64 = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    sig = hmac.new(settings.jwt_secret.encode("utf-8"), b64.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{b64}.{sig}"


def verify_access_token(token: str) -> int:
    try:
        b64, sig = token.split(".", 1)
        expected = hmac.new(settings.jwt_secret.encode("utf-8"), b64.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected):
            raise ValueError("Invalid signature")
        padded = b64 + "=" * (-len(b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if payload.get("exp", 0) < time.time():
            raise ValueError("Token expired")
        return int(payload["uid"])
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"无效或过期的登录凭证: {e}")


async def get_current_user(
    authorization: Optional[str] = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        uid = verify_access_token(token)
        user = await db.get(User, uid)
        if not user:
            raise HTTPException(status_code=401, detail="用户不存在")
        return user

    # 仅开发环境且 ENABLE_MOCK_FALLBACK=true 时保留无 Token 测试账号。生产环境一律 401。
    if settings.allows_anonymous_dev_user:
        res = await db.execute(select(User).where(User.openid == "dev_local_user"))
        user = res.scalar_one_or_none()
        if not user:
            user = User(openid="dev_local_user", nickname="自习室体验官", free_quota=10)
            db.add(user)
            await db.commit()
            await db.refresh(user)
        return user

    raise HTTPException(status_code=401, detail="请先登录")
