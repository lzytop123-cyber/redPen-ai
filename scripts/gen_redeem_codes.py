"""
批量生成商业兑换码工具（用于自习室发卡 / 小红书店铺发货）。
用法：
  python -m scripts.gen_redeem_codes --count 10 --quota 5 --name "冲刺体验包(5次)"
  python -m scripts.gen_redeem_codes --count 5 --vip-days 30 --name "上岸畅批月卡(30天)"
"""

import argparse
import asyncio
import secrets
import string

from app.db.database import AsyncSessionLocal, init_db
from app.db.models import RedeemCode


def make_code(prefix: str = "RP") -> str:
    alphabet = string.ascii_uppercase + string.digits
    body = "".join(secrets.choice(alphabet) for _ in range(8))
    return f"{prefix}-{body[:4]}-{body[4:]}"


async def main() -> None:
    ap = argparse.ArgumentParser(description="批量生成精批兑换码并写入数据库")
    ap.add_argument("--count", type=int, default=5, help="生成数量")
    ap.add_argument("--quota", type=int, default=5, help="增加精批次数")
    ap.add_argument("--vip-days", type=int, default=0, help="增加月卡天数")
    ap.add_argument("--name", type=str, default="冲刺体验包(5次)", help="套餐展示名称")
    args = ap.parse_args()

    await init_db()
    codes: list[str] = []
    async with AsyncSessionLocal() as db:
        for _ in range(args.count):
            c = make_code("VIP" if args.vip_days > 0 else "RP")
            db.add(
                RedeemCode(
                    code=c,
                    plan_name=args.name,
                    add_quota=args.quota,
                    add_vip_days=args.vip_days,
                )
            )
            codes.append(c)
        await db.commit()

    print(f"成功生成 {len(codes)} 个【{args.name}】兑换码：")
    for c in codes:
        print(f"  {c}")


if __name__ == "__main__":
    asyncio.run(main())
