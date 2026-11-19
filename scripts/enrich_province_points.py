"""
使用 DeepSeek 基于完整给定材料，自动为缺少采分点的省考申论真题（山西/贵州等）
独立生成自有版权的标准原子采分点 (scoring_points) 与参考答案 (reference_answer)，
并同步更新 data/shenlun_questions.json 与数据库。
"""

import argparse
import asyncio
import json
from pathlib import Path

from pydantic import BaseModel, Field

from app.db.database import AsyncSessionLocal, init_db
from app.db.models import QuestionModel
from app.llm_client import LLMRouter
from app.schemas import ExamType, ScoringPoint

QUESTIONS_JSON = Path("data/shenlun_questions.json")


class GeneratedKeyPoint(BaseModel):
    keyword: str = Field(..., description="4~12字精炼规范总括词")
    description: str = Field(..., description="该采分点在给定材料中的具体表现与同义得分词")


class EnrichShortOutput(BaseModel):
    scoring_points: list[GeneratedKeyPoint] = Field(
        ..., min_length=3, max_length=7, description="4~6个核心原子采分点"
    )
    reference_answer: str = Field(..., description="严格控制在题干字数上限内的高分示范答案")


class EnrichEssayOutput(BaseModel):
    reference_answer: str = Field(
        ..., description="核心中心论点 + 3个平行分论点立意解析 + 给定材料可用论据提炼"
    )


async def enrich_one(router: LLMRouter, item: dict) -> dict:
    exam_type = item["exam_type"]
    prompt = item["prompt"]
    material = item.get("material_summary", "")
    full_score = float(item.get("full_score", 15.0))
    max_words = int(item.get("max_words", 300))

    if exam_type == ExamType.SHENLUN_SHORT.value:
        sys_p = (
            "你是资深公考申论教研组长。请严格秉持“材料为王、原词提炼、不凭空臆造”原则，"
            "通读【给定材料】与【题目要求】，提炼出本题的标准原子采分点（4~6条）及高分参考答案。\n"
            "要求：\n"
            "1. 每个采分点必须直接源自给定材料，先给 4~10 字机关规范总括词(keyword)，再写材料里的具体得分细项(description)；\n"
            f"2. reference_answer 必须严格控制在 {max_words} 字以内，分条清晰、语言凝练。"
        )
        usr_p = f"【题目要求】\n{prompt}\n\n【给定材料】\n{material}"
        res = await router.call_structured(sys_p, usr_p, EnrichShortOutput)

        # 保留 15%（至少 1 分）给条理/格式分，其余均分给各采分点
        structure_reserve = max(1.0, round(full_score * 0.15))
        per_score = round((full_score - structure_reserve) / len(res.scoring_points), 1)
        item["scoring_points"] = [
            ScoringPoint(
                point_id=f"P{idx}",
                keyword=kp.keyword,
                description=kp.description,
                score=per_score,
            ).model_dump()
            for idx, kp in enumerate(res.scoring_points, start=1)
        ]
        item["reference_answer"] = res.reference_answer
    else:
        sys_p = (
            "你是资深申论大作文教研组长。请通读【给定材料】与【大作文题目要求】，"
            "提炼出精准的官方高分立意解析（中心论点 + 3个对仗平行分论点 + 可引用的材料案例清单），作为后续阅卷参考基准。"
        )
        usr_p = f"【题目要求】\n{prompt}\n\n【给定材料】\n{material}"
        res = await router.call_structured(sys_p, usr_p, EnrichEssayOutput)
        item["reference_answer"] = res.reference_answer

    return item


async def save_updates(updated_items: list[dict], all_items: list[dict]) -> None:
    QUESTIONS_JSON.write_text(json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8")
    await init_db()
    async with AsyncSessionLocal() as db:
        for item in updated_items:
            row = await db.get(QuestionModel, item["question_id"])
            if row:
                row.scoring_points = item.get("scoring_points", [])
                row.reference_answer = item.get("reference_answer", "")
        await db.commit()


async def main() -> None:
    parser = argparse.ArgumentParser(description="为山西/贵州等缺失采分点的真题自动生成标准采分点")
    parser.add_argument("--limit", type=int, default=4, help="本次试跑题数（默认 4 道最新题）")
    parser.add_argument("--all", action="store_true", help="全量补齐所有缺采分点的山西/贵州真题")
    parser.add_argument("--concurrency", type=int, default=4, help="并发数")
    args = parser.parse_args()

    all_items = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    targets = [
        item
        for item in all_items
        if (item["question_id"].startswith("SX-") or item["question_id"].startswith("GZ-"))
        and not item.get("reference_answer")
    ]
    # 按年份降序，优先处理 2025 山西 / 2024 贵州最新卷
    targets.sort(key=lambda x: (x.get("year", 0), x["question_id"]), reverse=True)

    if not args.all:
        targets = targets[: args.limit]

    if not targets:
        print("所有山西/贵州真题均已具备采分点与参考解析，无需重复生成。")
        return

    print(f"准备为 {len(targets)} 道山西/贵州真题生成标准采分点与参考解析...")
    router = LLMRouter()
    sem = asyncio.Semaphore(args.concurrency)
    updated: list[dict] = []

    async def worker(item: dict):
        async with sem:
            try:
                await enrich_one(router, item)
                updated.append(item)
                pts = len(item.get("scoring_points") or [])
                print(f"  [OK] {item['question_id']} | {item['title']} (采分点: {pts})")
            except Exception as e:
                print(f"  [FAIL] {item['question_id']}: {e}")

    await asyncio.gather(*(worker(it) for it in targets))
    await save_updates(updated, all_items)

    print(f"\n已更新 {len(updated)} 道真题至 JSON 与数据库！\n")
    for it in updated:
        print("=" * 60)
        print(f"【{it['question_id']}】{it['title']} (满分 {it['full_score']} 分)")
        if it.get("scoring_points"):
            print("标准采分点：")
            for p in it["scoring_points"]:
                print(f"  - {p['point_id']} ({p['score']}分) 【{p['keyword']}】：{p['description']}")
        print(f"参考答案/立意解析：\n{it['reference_answer']}\n")


if __name__ == "__main__":
    asyncio.run(main())
