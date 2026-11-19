"""
商业级采分点重建脚本（v2）。

模式 A：有官方/机构参考答案的题（国考/广东/湖北）
  -> 只允许从参考答案拆分原子采分点，禁止新增参考答案外的内容。
模式 B：无参考答案的题（山西/贵州）
  -> 基于完整给定材料生成，每个采分点必须附材料原文引用，
     由代码在材料中逐字核验，核验失败的采分点直接丢弃。

所有不达标的题写入 data/review_queue.json，供人工复核。
支持断点续跑：已完成 v2 的题自动跳过（--force 强制重跑）。
"""

import argparse
import asyncio
import json
import re
from pathlib import Path

from pydantic import BaseModel, Field

from app.db.database import AsyncSessionLocal, init_db
from app.db.models import QuestionModel
from app.llm_client import LLMRouter

QUESTIONS_JSON = Path("data/shenlun_questions.json")
REVIEW_QUEUE = Path("data/review_queue.json")
POINTS_VERSION = 2

SUB_TYPES = ["单一题（归纳概括）", "提出对策题", "综合分析题", "公文写作题", "大作文"]


class PointOut(BaseModel):
    keyword: str = Field(..., description="4~12字规范总括词")
    description: str = Field(..., description="得分细项与可接受的同义表述")
    weight: int = Field(..., ge=1, le=3, description="相对重要度：3=核心要点，2=重要，1=次要")
    material_quote: str = Field(default="", description="支撑该要点的给定材料原文（逐字摘录10~40字）")


class RebuildOut(BaseModel):
    sub_type: str = Field(..., description=f"题型，只能是：{' / '.join(SUB_TYPES)}")
    scoring_points: list[PointOut] = Field(..., min_length=1, max_length=12)
    reference_answer: str = Field(default="", description="模式B下生成的参考答案；模式A留空")


def _norm(s: str) -> str:
    return re.sub(r"[\s，。、；：:,.;“”\"'‘’（）()《》!?！？\-—…]", "", s)


def quote_in_material(quote: str, material: str, window: int = 10) -> bool:
    q, m = _norm(quote), _norm(material)
    if len(q) < window:
        return bool(q) and q in m
    return any(q[i : i + window] in m for i in range(0, len(q) - window + 1, 3))


def allocate_scores(points: list[PointOut], full_score: float) -> list[float]:
    reserve = max(1.0, round(full_score * 0.15))
    budget = full_score - reserve
    total_w = sum(p.weight for p in points) or 1
    raw = [budget * p.weight / total_w for p in points]
    scores = [round(x * 2) / 2 for x in raw]  # 0.5 分粒度
    diff = round((budget - sum(scores)) * 2) / 2
    if scores and diff:
        idx = max(range(len(points)), key=lambda i: points[i].weight)
        scores[idx] = max(0.5, scores[idx] + diff)
    return scores


def has_official_answer(item: dict) -> bool:
    return item["question_id"].startswith(("GK-", "GD-", "HB-")) and len(item.get("reference_answer", "")) >= 30


async def rebuild_one(router: LLMRouter, item: dict) -> tuple[bool, str]:
    prompt, material = item["prompt"], item.get("material_summary", "")
    full_score = float(item.get("full_score", 15.0))
    mode_a = has_official_answer(item)

    if mode_a:
        sys_p = (
            "你是公考申论阅卷组的采分点拆解专家。你的唯一依据是【参考答案】。\n"
            "规则：\n"
            "1. 把参考答案拆成原子级采分点：一个采分点只包含一个独立得分意思；\n"
            "2. 严禁添加参考答案中没有的内容，严禁合并多个不同意思；\n"
            "3. 参考答案里的“说明/解析”文字不是采分点，忽略；\n"
            "4. description 写明该点的核心意思与阅卷可接受的同义表述；\n"
            "5. weight 反映重要度，总括性核心要点给 3；\n"
            "6. material_quote 从给定材料中摘录支撑原文（找不到可留空）；\n"
            "7. 判断题型 sub_type；reference_answer 留空。"
        )
        usr_p = f"【题目要求】\n{prompt}\n\n【参考答案】\n{item['reference_answer']}\n\n【给定材料】\n{material}"
    else:
        sys_p = (
            "你是资深公考申论教研组长，严格遵循“材料为王、原词提炼、不凭空臆造”。\n"
            "规则：\n"
            "1. 先精确定位题目指定的给定资料范围（如“给定资料3”），只从该范围提炼；\n"
            "2. 每个采分点必须附 material_quote：从材料中逐字摘录10~40字原文，禁止改写，系统会逐字核验；\n"
            "3. 一个采分点只包含一个独立得分意思，数量按分值合理确定（一般每2~4分一个点）；\n"
            "4. weight 反映重要度；\n"
            "5. 判断题型 sub_type；\n"
            "6. reference_answer 写一份严格符合题目字数要求的高分答案。"
        )
        usr_p = f"【题目要求】\n{prompt}\n\n【给定材料】\n{material}"

    res = await router.call_structured(sys_p, usr_p, RebuildOut)

    points = res.scoring_points
    if not mode_a:
        points = [p for p in points if quote_in_material(p.material_quote, material)]

    reasons = []
    if len(points) < 3:
        reasons.append(f"有效采分点仅 {len(points)} 个")
    if res.sub_type not in SUB_TYPES:
        reasons.append(f"题型无法识别：{res.sub_type}")
    if not mode_a and not res.reference_answer.strip():
        reasons.append("未生成参考答案")

    if points:
        scores = allocate_scores(points, full_score)
        item["scoring_points"] = [
            {
                "point_id": f"P{i}",
                "keyword": p.keyword,
                "description": p.description,
                "score": s,
            }
            for i, (p, s) in enumerate(zip(points, scores), start=1)
        ]
    if res.sub_type in SUB_TYPES and res.sub_type != "大作文":
        item["sub_type"] = res.sub_type
    if not mode_a and res.reference_answer.strip():
        item["reference_answer"] = res.reference_answer.strip()

    item["points_version"] = POINTS_VERSION
    item["points_source"] = "official_answer" if mode_a else "material_grounded"
    return (not reasons), "；".join(reasons)


async def persist(item: dict, all_items: list[dict]) -> None:
    QUESTIONS_JSON.write_text(json.dumps(all_items, ensure_ascii=False, indent=2), encoding="utf-8")
    async with AsyncSessionLocal() as db:
        row = await db.get(QuestionModel, item["question_id"])
        if row:
            row.scoring_points = item.get("scoring_points", [])
            row.reference_answer = item.get("reference_answer", "")
            row.sub_type = item.get("sub_type", row.sub_type)
        await db.commit()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="只处理前 N 道（试跑用）")
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    await init_db()
    all_items = json.loads(QUESTIONS_JSON.read_text(encoding="utf-8"))
    targets = [
        it for it in all_items
        if it["exam_type"] == "shenlun_short"
        and (args.force or it.get("points_version") != POINTS_VERSION)
    ]
    targets.sort(key=lambda x: (x.get("year", 0), x["question_id"]), reverse=True)
    if args.limit:
        targets = targets[: args.limit]

    review = json.loads(REVIEW_QUEUE.read_text(encoding="utf-8")) if REVIEW_QUEUE.exists() else {}
    print(f"待重建采分点：{len(targets)} 道申论小题", flush=True)

    router = LLMRouter()
    sem, lock = asyncio.Semaphore(args.concurrency), asyncio.Lock()
    stats = {"ok": 0, "review": 0, "fail": 0}

    async def worker(item: dict):
        async with sem:
            for attempt in range(3):
                try:
                    ok, reason = await rebuild_one(router, item)
                    break
                except Exception as e:  # 限流/网络错误时退避重试
                    if attempt == 2:
                        async with lock:
                            stats["fail"] += 1
                            review[item["question_id"]] = f"生成失败：{e}"
                        print(f"  [FAIL] {item['question_id']}: {e}", flush=True)
                        return
                    await asyncio.sleep(5 * (attempt + 1))
            async with lock:
                await persist(item, all_items)
                if ok:
                    stats["ok"] += 1
                    review.pop(item["question_id"], None)
                else:
                    stats["review"] += 1
                    review[item["question_id"]] = reason
                REVIEW_QUEUE.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
                done = sum(stats.values())
                tag = "OK" if ok else "REVIEW"
                print(f"  [{tag}] ({done}/{len(targets)}) {item['question_id']} 采分点 {len(item.get('scoring_points') or [])} 个 {reason}", flush=True)

    await asyncio.gather(*(worker(it) for it in targets))
    print(f"\n完成：通过 {stats['ok']} | 需人工复核 {stats['review']} | 失败 {stats['fail']}")
    print(f"复核清单：{REVIEW_QUEUE}")


if __name__ == "__main__":
    asyncio.run(main())
