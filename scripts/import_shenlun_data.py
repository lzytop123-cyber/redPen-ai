"""
从 GitHub 开源 MIT 申论真题数据集 (data/raw/shenlun_github.jsonl)
自动清洗、提取分值与字数要求、拆解原子采分点，生成系统标准题库 data/shenlun_questions.json。
"""

import json
import re
from pathlib import Path

from app.schemas import ExamType, Question, ScoringPoint

RAW_PATH = Path("data/raw/shenlun_github.jsonl")
OUT_PATH = Path("data/shenlun_questions.json")


def extract_full_score(stem: str, is_essay: bool) -> float:
    """从题干中正则提取满分，如 (10 分)、（35分）、（20分）"""
    m = re.search(r"[（(]\s*(\d+(?:\.\d+)?)\s*分\s*[）)]", stem)
    if m:
        return float(m.group(1))
    m2 = re.search(r"满分\s*(\d+)\s*分", stem)
    if m2:
        return float(m2.group(1))
    return 40.0 if is_essay else 15.0


def extract_word_limits(stem: str, is_essay: bool) -> tuple[int, int]:
    """提取最少/最多字数要求"""
    # 区间格式：1000～1200字 / 800-1000字
    m_range = re.search(r"(\d{3,4})\s*[～~—\-至到]\s*(\d{3,4})\s*字", stem)
    if m_range:
        return int(m_range.group(1)), int(m_range.group(2))

    # 上限格式：不超过200字 / 300字以内
    m_max = re.search(r"(?:不超过|不多于|字数在)\s*(\d{2,4})\s*字|(\d{2,4})\s*字以内", stem)
    if m_max:
        max_w = int(m_max.group(1) or m_max.group(2))
        return int(max_w * 0.6), max_w

    # 左右格式：1000字左右 / 不少于1000字
    m_approx = re.search(r"(?:不少于|不低于)\s*(\d{3,4})\s*字|(\d{3,4})\s*字左右", stem)
    if m_approx:
        base = int(m_approx.group(1) or m_approx.group(2))
        if is_essay:
            return base, base + 200
        return int(base * 0.8), int(base * 1.2)

    return (1000, 1200) if is_essay else (100, 300)


def extract_scoring_points(ans: str, full_score: float) -> list[ScoringPoint]:
    """
    基于规则将分条参考答案（如 1. xxx / 一、xxx / （1）xxx）自动拆解为原子采分点。
    保留约 15%~20% 的分值作为条理与语言规范分，其余按采分点均分。
    """
    # 截断“参考答案说明”之后的解释文字
    core_ans = re.split(r"参考答案说明[:：]|解析[:：]|【评分标准】", ans)[0].strip()
    lines = [line.strip() for line in core_ans.splitlines() if line.strip()]

    raw_points: list[str] = []
    bullet_pattern = re.compile(r"^(?:\d+[.、．]|[一二三四五六七八九十]+[、.]|[（(]\d+[）)]|[①②③④⑤⑥⑦⑧⑨⑩])\s*(.+)")

    for line in lines:
        m = bullet_pattern.match(line)
        if m:
            content = m.group(1).strip()
            if len(content) >= 6:
                raw_points.append(content)

    # 若没匹配到典型编号，按段落切分兜底
    if not raw_points:
        raw_points = [l for l in lines if len(l) >= 12][:6]

    if not raw_points:
        return []

    # 限制最多 8 个核心采分点，留 15% 给条理分（至少留 1 分）
    raw_points = raw_points[:8]
    structure_reserve = max(1.0, round(full_score * 0.15))
    per_point_score = round((full_score - structure_reserve) / len(raw_points), 1)

    points: list[ScoringPoint] = []
    for idx, text in enumerate(raw_points, start=1):
        # 提取句首总括词（遇到冒号/句号/逗号截断前 14 字）
        kw_split = re.split(r"[。：:，,；;]", text)[0].strip()
        keyword = kw_split[:16] if kw_split else text[:12]
        points.append(
            ScoringPoint(
                point_id=f"P{idx}",
                keyword=keyword,
                description=text,
                score=per_point_score,
            )
        )
    return points


def main() -> None:
    if not RAW_PATH.exists():
        raise FileNotFoundError(f"未找到原始文件: {RAW_PATH}")

    questions: list[dict] = []
    short_count = 0
    essay_count = 0

    with RAW_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            ans = (row.get("ans") or "").strip()
            stem = (row.get("stem") or "").strip()
            if not stem or len(ans) < 30:
                continue

            sub_type = row.get("type") or "其他"
            is_essay = sub_type == "大作文"
            exam_type = ExamType.SHENLUN_ESSAY if is_essay else ExamType.SHENLUN_SHORT

            full_score = extract_full_score(stem, is_essay)
            min_w, max_w = extract_word_limits(stem, is_essay)
            scoring_points = [] if is_essay else extract_scoring_points(ans, full_score)

            paper = row.get("paper") or row.get("exam_label") or ""
            no = row.get("no") or ""
            title = f"{paper} 第{no}题【{sub_type}】"

            # 材料保留前 4500 字作为上下文摘要，避免超长 token 浪费
            material = (row.get("material") or "").strip()

            q = Question(
                question_id=row["id"],
                exam_type=exam_type,
                title=title,
                year=int(row.get("year") or 0),
                paper=paper,
                sub_type=sub_type,
                prompt=stem,
                material_summary=material,
                full_score=full_score,
                min_words=min_w,
                max_words=max_w,
                scoring_points=scoring_points,
                reference_answer=ans,
            )
            questions.append(q.model_dump())
            if is_essay:
                essay_count += 1
            else:
                short_count += 1

    # 按年份降序排列，最新真题排最前面
    questions.sort(key=lambda x: (x["year"], x["question_id"]), reverse=True)
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(questions, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"清洗完成！共导入 {len(questions)} 道带完整解析的申论真题 -> {OUT_PATH}")
    print(f"  - 申论小题（含自动拆解采分点）: {short_count} 道")
    print(f"  - 申论大作文（含参考范文与材料）: {essay_count} 道")


if __name__ == "__main__":
    main()
