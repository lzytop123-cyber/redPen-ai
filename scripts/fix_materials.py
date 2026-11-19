"""
修复题库材料截断问题：
从原始数据源回填完整给定材料，只更新 material_summary 字段，
不覆盖已生成的采分点和参考答案。同步写入 JSON 与数据库。
"""

import asyncio
import json
from pathlib import Path

from app.db.database import AsyncSessionLocal, init_db
from app.db.models import QuestionModel
from scripts.import_provinces_md import parse_md_paper

QUESTIONS_JSON = Path("data/shenlun_questions.json")
RAW_JSONL = Path("data/raw/shenlun_github.jsonl")
PROVINCE_DIR = Path("data/raw/provinces")


def load_full_materials() -> dict[str, str]:
    full: dict[str, str] = {}
    if RAW_JSONL.exists():
        for line in RAW_JSONL.open(encoding="utf-8"):
            row = json.loads(line)
            if row.get("material"):
                full[row["id"]] = row["material"].strip()
    for md in sorted(PROVINCE_DIR.glob("*.md")):
        for q in parse_md_paper(md):
            full[q.question_id] = q.material_summary
    return full


async def main() -> None:
    items = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    full = load_full_materials()

    changed: list[dict] = []
    for item in items:
        new_mat = full.get(item["question_id"])
        if new_mat and len(new_mat) > len(item.get("material_summary", "")):
            item["material_summary"] = new_mat
            changed.append(item)

    QUESTIONS_JSON.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")

    await init_db()
    async with AsyncSessionLocal() as db:
        for item in changed:
            row = await db.get(QuestionModel, item["question_id"])
            if row:
                row.material_summary = item["material_summary"]
        await db.commit()

    lens = [len(i.get("material_summary", "")) for i in items]
    print(f"已回填完整材料：{len(changed)} 道")
    print(f"材料长度：最长 {max(lens)} 字，平均 {sum(lens) // len(lens)} 字")


if __name__ == "__main__":
    asyncio.run(main())
