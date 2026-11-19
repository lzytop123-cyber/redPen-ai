"""
解析 data/raw/provinces/*.md（山西、贵州等历年省考申论真题 Markdown），
合并写入 data/shenlun_questions.json，并增量导入当前数据库。
"""

import asyncio
import json
import re
from pathlib import Path

from app.db.database import AsyncSessionLocal, init_db
from app.db.models import QuestionModel
from app.schemas import ExamType, Question
from scripts.import_shenlun_data import extract_full_score, extract_word_limits

PROVINCE_DIR = Path("data/raw/provinces")
OUT_JSON = Path("data/shenlun_questions.json")


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    meta: dict[str, str] = {}
    body = text
    m = re.match(r"^---\s*\n([\s\S]*?)\n---\s*\n([\s\S]*)$", text)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
        body = m.group(2)
    return meta, body


def detect_sub_type(prompt: str, full_score: float) -> tuple[ExamType, str]:
    essay_signals = ["自拟题目", "写一篇文章", "写一篇议论文", "议论文", "1000字", "800～1000", "1000～1200", "不少于1000"]
    if full_score >= 30 and any(sig in prompt for sig in essay_signals):
        return ExamType.SHENLUN_ESSAY, "大作文"
    if any(k in prompt for k in ["倡议书", "公开信", "发言稿", "讲话稿", "汇报材料", "短评", "调研报告", "简报", "宣传稿", "提纲"]):
        return ExamType.SHENLUN_SHORT, "公文写作题"
    if any(k in prompt for k in ["对策", "建议", "措施"]):
        return ExamType.SHENLUN_SHORT, "提出对策题"
    if any(k in prompt for k in ["理解", "谈谈", "启示", "认识", "评析"]):
        return ExamType.SHENLUN_SHORT, "综合分析题"
    return ExamType.SHENLUN_SHORT, "单一题（归纳概括）"


def parse_md_paper(path: Path) -> list[Question]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    meta, body = parse_frontmatter(raw)

    province = meta.get("province") or path.name.split("_")[0]
    year_str = meta.get("year") or (re.search(r"(20\d{2})", path.name).group(1) if re.search(r"(20\d{2})", path.name) else "0")
    year = int(year_str)
    paper_title = meta.get("title") or path.stem

    # 切分“给定材料”与“作答要求”（兼容作答要求后紧跟全角空格或直接跟题号）
    split_match = re.split(
        r"(?:\n|^)\s*(?:#{1,3}\s*)?(?:三、|二、)?(?:作答要求|申论要求|题目要求)\s*",
        body,
        maxsplit=1,
    )
    if len(split_match) < 2:
        # 兜底：直接从第一个“问题一：”或“第一题：”处切分
        split_match = re.split(r"(?=\n\s*(?:问题一[:：]|第一题[:：]))", body, maxsplit=1)
    if len(split_match) < 2:
        return []

    materials_text = split_match[0].strip()
    tasks_text = split_match[1].strip()

    # 按 “问题一：/一、/第一题/【问题一】” 切分各小题（兼容全角空格 \u3000）
    parts = re.split(
        r"(?:\n|[\u3000\s]{2,})(?=(?:问题[一二三四五六][:：]|[一二三四五六]、|第[一二三四五六]题[:：]?|【问题[一二三四五六]】))",
        "\n" + tasks_text,
    )
    parts = [p.strip() for p in parts if len(p.strip()) >= 15]

    prov_code = {"山西": "SX", "贵州": "GZ"}.get(province, "PV")
    tid = meta.get("tid") or path.stem[-4:]

    result: list[Question] = []
    for idx, prompt in enumerate(parts, start=1):
        # 先按大作文常见特征粗判，用于默认满分兜底
        is_essay_hint = any(k in prompt for k in ["写一篇文章", "自拟题目", "议论文", "1000字"])
        full_score = extract_full_score(prompt, is_essay_hint)
        exam_type, sub_type = detect_sub_type(prompt, full_score)
        min_w, max_w = extract_word_limits(prompt, exam_type == ExamType.SHENLUN_ESSAY)

        qid = f"{prov_code}-{year}-{tid}-S{idx:02d}"
        # 精简试卷名
        short_paper = re.sub(r"公务员考试|《申论》|_申论_|试题", "", paper_title).strip(" _")
        title = f"{province}-{year} ({short_paper}) 第{idx}题【{sub_type}】"

        result.append(
            Question(
                question_id=qid,
                exam_type=exam_type,
                title=title,
                year=year,
                paper=f"{province}-{year}",
                sub_type=sub_type,
                prompt=prompt,
                material_summary=materials_text[:4500],
                full_score=full_score,
                min_words=min_w,
                max_words=max_w,
                scoring_points=[],
                reference_answer="",
            )
        )
    return result


async def upsert_to_db(new_questions: list[Question]) -> int:
    await init_db()
    added = 0
    async with AsyncSessionLocal() as db:
        for q in new_questions:
            existing = await db.get(QuestionModel, q.question_id)
            if existing:
                continue
            db.add(
                QuestionModel(
                    question_id=q.question_id,
                    exam_type=q.exam_type.value,
                    title=q.title,
                    year=q.year,
                    paper=q.paper,
                    sub_type=q.sub_type,
                    prompt=q.prompt,
                    material_summary=q.material_summary,
                    full_score=q.full_score,
                    min_words=q.min_words,
                    max_words=q.max_words,
                    scoring_points=[p.model_dump() for p in q.scoring_points],
                    reference_answer=q.reference_answer,
                )
            )
            added += 1
        await db.commit()
    return added


async def main() -> None:
    md_files = sorted(PROVINCE_DIR.glob("*.md"))
    parsed: list[Question] = []
    sx_cnt, gz_cnt = 0, 0
    for f in md_files:
        qs = parse_md_paper(f)
        parsed.extend(qs)
        if f.name.startswith("山西"):
            sx_cnt += len(qs)
        elif f.name.startswith("贵州"):
            gz_cnt += len(qs)

    # 1. 合并写入 data/shenlun_questions.json（按 question_id 去重）
    existing_items = json.loads(OUT_JSON.read_text(encoding="utf-8")) if OUT_JSON.exists() else []
    by_id = {item["question_id"]: item for item in existing_items}
    for q in parsed:
        by_id[q.question_id] = q.model_dump()
    merged = sorted(by_id.values(), key=lambda x: (x.get("year", 0), x["question_id"]), reverse=True)
    OUT_JSON.write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")

    # 2. 直接增量写入当前运行中的数据库
    db_added = await upsert_to_db(parsed)

    print(f"解析完成！共新增山西 {sx_cnt} 道 + 贵州 {gz_cnt} 道 = {len(parsed)} 道省考申论真题")
    print(f"  - JSON 题库总计: {len(merged)} 道 ({OUT_JSON})")
    print(f"  - 已实时写入数据库: +{db_added} 道")


if __name__ == "__main__":
    asyncio.run(main())
