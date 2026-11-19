import json
from app.schemas import (
    NumberedSentence,
    Question,
    ShenlunEssayStep1Output,
    ShenlunStep1Output,
)


def build_shenlun_step1_prompts(question: Question, student_answer: str) -> tuple[str, str]:
    system_prompt = (
        "你是一位极其严苛的国考/省考申论官方阅卷组长，秉持“宁严勿宽、按点给分、有据可依”的阅卷原则。\n"
        "你的任务是对照【标准采分点列表】，逐一核对【考生作答】的命中情况：\n"
        "1. 只有考生明确写出该采分点的核心意思（或高度等价的规范表述），才能判定为 hit；\n"
        "2. 仅仅沾边、表述极其口语化或只写了一半，判定为 partial；\n"
        "3. 完全未提及，判定为 miss；\n"
        "4. 凡是判定为 hit 或 partial，必须忠实摘录考生原文作为 evidence_quote，严禁编造原文不存在的内容；\n"
        "5. 绝对不要客套鼓励，直接指出遗漏和硬伤。"
    )

    points_text = json.dumps(
        [p.model_dump() for p in question.scoring_points],
        ensure_ascii=False,
        indent=2,
    )
    user_prompt = (
        f"【题目要求】\n{question.prompt}\n\n"
        f"【给定材料核心摘要】\n{question.material_summary}\n\n"
        f"【标准采分点列表】\n{points_text}\n\n"
        f"【考生作答原文】\n{student_answer}\n\n"
        "请严格逐点核对并输出 JSON。"
    )
    return system_prompt, user_prompt


def build_shenlun_step2_prompts(
    question: Question,
    sentences: list[NumberedSentence],
    step1: ShenlunStep1Output,
) -> tuple[str, str]:
    system_prompt = (
        "你是申论精细化逐句红笔批改名师。请针对考生带编号的句子（S1, S2...）给出精准红笔批注。\n"
        "要求：\n"
        "1. 每条批注的 sentence_id 必须严格来自输入列表，严禁自创编号；\n"
        "2. 重点揪出：表达口语化/大白话（需改成机关规范词）、啰嗦占字数、采分点表述不精准、逻辑混乱；\n"
        "3. 如果有写得非常凝练规范的句子，也可以给 1 条 highlight 表扬；\n"
        "4. 每条批注必须给出可直接替换的精简规范改写 suggestion。"
    )
    sentences_text = "\n".join(f"[{s.sentence_id}] {s.text}" for s in sentences)
    step1_summary = step1.model_dump_json(ensure_ascii=False)
    user_prompt = (
        f"【题目要求】\n{question.prompt}\n\n"
        f"【已核对的采分点情况】\n{step1_summary}\n\n"
        f"【考生带编号原句】\n{sentences_text}\n\n"
        "请输出逐句红笔批注 JSON（挑出最关键的 3~6 处即可，宁缺毋滥）。"
    )
    return system_prompt, user_prompt


def build_shenlun_step3_prompts(
    question: Question,
    student_answer: str,
    step1: ShenlunStep1Output,
) -> tuple[str, str]:
    system_prompt = (
        "你是申论高分升格教练。你的核心原则是【同思路升格】：\n"
        "1. 不要完全抛弃考生原稿去背一篇陌生参考答案，而是尽量保留考生的原有分条骨架；\n"
        "2. 把考生遗漏（miss/partial）的采分点自然补齐，把口语化大白话替换为精炼的申论规范词（总括词+具体表现）；\n"
        f"3. 严格控制升格后全文总字数不超过 {question.max_words or 300} 字。"
    )
    points_text = "\n".join(
        f"- {p.point_id} ({p.keyword}): {p.description}" for p in question.scoring_points
    )
    user_prompt = (
        f"【题目要求】\n{question.prompt}\n\n"
        f"【全部标准采分点】\n{points_text}\n\n"
        f"【考生原稿】\n{student_answer}\n\n"
        f"【本次核对出的遗漏与问题】\n{step1.model_dump_json(ensure_ascii=False)}\n\n"
        "请输出同思路升格版答案及 3~5 条核心改动亮点 JSON。"
    )
    return system_prompt, user_prompt


# =========================
# 申论大作文专属 3 步 Prompt
# =========================

def build_shenlun_essay_step1_prompts(question: Question, student_answer: str) -> tuple[str, str]:
    system_prompt = (
        "你是一位严苛的国考/省考申论大作文阅卷组长，秉持“立意为王、联系材料、宁严勿宽”的阅卷原则。\n"
        "请按以下 4 个固定维度对考生大作文进行 1~5 档定级：\n"
        "1. 立意切题与思想深度（weight: 0.35）\n"
        "2. 论据充实与材料结合度（weight: 0.25）\n"
        "3. 结构布局与分论点逻辑（weight: 0.20）\n"
        "4. 语言规范与公文语感（weight: 0.20）\n"
        "同时必须明确判定：中心论点是否切题（thesis_accuracy）以及是否有效结合给定材料（material_usage）。"
    )
    user_prompt = (
        f"【大作文题目要求】\n{question.prompt}\n\n"
        f"【给定材料核心摘要】\n{question.material_summary[:3000]}\n\n"
        f"【参考立意/范文参考】\n{question.reference_answer[:1500]}\n\n"
        f"【考生大作文原文】\n{student_answer}\n\n"
        "请严格按维度定档并输出 JSON。"
    )
    return system_prompt, user_prompt


def build_shenlun_essay_step2_prompts(
    question: Question,
    sentences: list[NumberedSentence],
    step1: ShenlunEssayStep1Output,
) -> tuple[str, str]:
    system_prompt = (
        "你是申论大作文逐句红笔精批名师。请对带编号原句（S1, S2...）揪出核心硬伤：\n"
        "1. sentence_id 必须严格来自输入列表；\n"
        "2. 重点批注：分论点不平行/口号化空泛、脱离材料自说自话、口语化大白话、过渡生硬；\n"
        "3. 每条批注给出可直接替换的高分公文规范改写 suggestion。"
    )
    sentences_text = "\n".join(f"[{s.sentence_id}] {s.text}" for s in sentences)
    user_prompt = (
        f"【题目要求】\n{question.prompt}\n\n"
        f"【维度初评】\n{step1.model_dump_json(ensure_ascii=False)}\n\n"
        f"【考生带编号原句】\n{sentences_text}\n\n"
        "请输出 4~8 条最关键的逐句红笔批注 JSON。"
    )
    return system_prompt, user_prompt


def build_shenlun_essay_step3_prompts(
    question: Question,
    student_answer: str,
    step1: ShenlunEssayStep1Output,
) -> tuple[str, str]:
    system_prompt = (
        "你是申论大作文升格教练。核心原则是【同思路升格】：\n"
        "1. 尽量保留考生原有的中心论点和分论点骨架（若跑题则纠偏后保留合理素材）；\n"
        "2. 强化开头破题、优化对仗工整的分论点段首句、自然融入给定材料案例、提升机关公文语感；\n"
        "3. 输出一篇字数约 1000 字的一类文升格版，并列出 3~5 条核心提分亮点。"
    )
    user_prompt = (
        f"【题目要求】\n{question.prompt}\n\n"
        f"【给定材料摘要】\n{question.material_summary[:2500]}\n\n"
        f"【考生原稿】\n{student_answer}\n\n"
        f"【本次诊断问题】\n{step1.model_dump_json(ensure_ascii=False)}\n\n"
        "请输出同思路升格版大作文及核心提分亮点 JSON。"
    )
    return system_prompt, user_prompt

