"""
批改精准度评测脚本（商业上线前的质量闸门）。

用法：
  python -m scripts.eval_grading                     # 跑 data/eval/gold.jsonl 全部样卷
  python -m scripts.eval_grading --repeat 3          # 每份批 3 次，测稳定性
  python -m scripts.eval_grading --limit 5

样卷格式（data/eval/gold.jsonl，每行一份）：
  {"question_id": "GK-2024-fs-S01",
   "student_answer": "考生原文……",
   "human_score": 7.5,
   "human_points": {"P1": "hit", "P2": "miss"},   # 可选：人工逐点判定
   "grader": "张老师（申论 78 分）"}                # 可选：打分人

上线标准（默认）：
  小题 MAE ≤ 1.5 分；大作文 MAE ≤ 3 分；考研英语 MAE ≤ 1.5 分
  重复批改分差 ≤ 1 分；采分点判定一致率 ≥ 90%
"""

import argparse
import asyncio
import json
import statistics
from datetime import datetime
from pathlib import Path

from app.pipeline import GradingPipeline
from app.schemas import ExamType, Question

GOLD = Path("data/eval/gold.jsonl")
OUT_DIR = Path("output/eval")

THRESHOLDS = {
    ExamType.SHENLUN_SHORT: 1.5,
    ExamType.SHENLUN_ESSAY: 3.0,
    ExamType.KAOYAN_ENGLISH: 1.5,
}


def load_questions() -> dict[str, Question]:
    qs: dict[str, Question] = {}
    for p in ["data/shenlun_questions.json", "data/kaoyan_questions.json", "data/sample_questions.json"]:
        path = Path(p)
        if path.exists():
            for item in json.loads(path.read_text(encoding="utf-8")):
                qs[item["question_id"]] = Question.model_validate(item)
    return qs


async def eval_one(pipeline: GradingPipeline, q: Question, sample: dict, repeat: int) -> dict:
    scores, point_agree = [], []
    for _ in range(repeat):
        rep = await pipeline.run(question=q, student_answer=sample["student_answer"])
        scores.append(rep.final_score)
        hp = sample.get("human_points")
        if hp and rep.shenlun_detail:
            ai = {m.point_id: m.status for m in rep.shenlun_detail.point_matches}
            common = [k for k in hp if k in ai]
            if common:
                point_agree.append(sum(hp[k] == ai[k] for k in common) / len(common))
    avg = statistics.mean(scores)
    return {
        "question_id": q.question_id,
        "exam_type": q.exam_type.value,
        "human_score": sample["human_score"],
        "ai_scores": scores,
        "ai_avg": round(avg, 2),
        "error": round(avg - sample["human_score"], 2),
        "spread": round(max(scores) - min(scores), 2),
        "point_agreement": round(statistics.mean(point_agree), 3) if point_agree else None,
    }


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    if not GOLD.exists():
        print(f"未找到样卷集 {GOLD}，请参考 data/eval/gold.example.jsonl 准备人工打分样卷。")
        return

    samples = [json.loads(l) for l in GOLD.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        samples = samples[: args.limit]
    questions = load_questions()
    pipeline = GradingPipeline()

    results = []
    for i, s in enumerate(samples, 1):
        q = questions.get(s["question_id"])
        if not q:
            print(f"  [跳过] 题库中找不到 {s['question_id']}")
            continue
        r = await eval_one(pipeline, q, s, args.repeat)
        results.append(r)
        print(f"  ({i}/{len(samples)}) {r['question_id']} 人工 {r['human_score']} | AI {r['ai_scores']} | 误差 {r['error']:+}", flush=True)

    if not results:
        return

    print("\n================ 评测结果 ================")
    all_pass = True
    for et in ExamType:
        group = [r for r in results if r["exam_type"] == et.value]
        if not group:
            continue
        errs = [abs(r["error"]) for r in group]
        mae = statistics.mean(errs)
        bias = statistics.mean(r["error"] for r in group)
        spread = max(r["spread"] for r in group)
        agrees = [r["point_agreement"] for r in group if r["point_agreement"] is not None]
        thr = THRESHOLDS[et]
        ok = mae <= thr and (args.repeat == 1 or spread <= 1.0) and (not agrees or statistics.mean(agrees) >= 0.9)
        all_pass &= ok
        print(f"\n[{et.value}] 样卷 {len(group)} 份  {'✅ 达标' if ok else '❌ 未达标'}")
        print(f"  平均误差 MAE: {mae:.2f}（标准 ≤ {thr}）")
        print(f"  系统偏差: {bias:+.2f}（正数=AI 打分偏高，需下调系数）")
        print(f"  最大误差: {max(errs):.2f}")
        if args.repeat > 1:
            print(f"  重复批改最大分差: {spread:.2f}（标准 ≤ 1.0）")
        if agrees:
            print(f"  采分点判定一致率: {statistics.mean(agrees):.1%}（标准 ≥ 90%）")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"eval_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n总体结论：{'✅ 可以上线' if all_pass else '❌ 暂不建议上线'}")
    print(f"明细已保存：{out}")


if __name__ == "__main__":
    asyncio.run(main())
