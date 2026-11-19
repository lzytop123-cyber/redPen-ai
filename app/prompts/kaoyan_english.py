from app.schemas import KaoyanEnglishStep1Output, NumberedSentence, Question


def build_kaoyan_step1_prompts(question: Question, student_answer: str) -> tuple[str, str]:
    system_prompt = (
        "你是一位严苛的全国硕士研究生招生考试（考研英语一/二）阅卷组长。\n"
        "请严格按照考研英语官方五档评分标准，对考生作文从以下 4 个固定维度进行 1~5 档定级：\n"
        "1. 内容切题与要点覆盖（weight: 0.35）\n"
        "2. 语法准确性与拼写规范（weight: 0.25）\n"
        "3. 词汇丰富度与高级句式（weight: 0.25）\n"
        "4. 篇章结构与逻辑衔接（weight: 0.15）\n"
        "同时必须敏锐识别“万能模板痕迹”（template_risk: low/medium/high）。\n"
        "严禁客套夸奖，客观指出所有扣分硬伤。"
    )
    user_prompt = (
        f"【题目要求】\n{question.prompt}\n\n"
        f"【考生作文原文】\n{student_answer}\n\n"
        "请严格按上述 4 个维度定档并输出 JSON。"
    )
    return system_prompt, user_prompt


def build_kaoyan_step2_prompts(
    question: Question,
    sentences: list[NumberedSentence],
    step1: KaoyanEnglishStep1Output,
) -> tuple[str, str]:
    system_prompt = (
        "你是考研英语作文逐句红笔精批专家。请对考生带编号的英文原句（S1, S2...）做逐句挑刺与升格。\n"
        "要求：\n"
        "1. sentence_id 必须严格来自输入列表；\n"
        "2. 精准指出：语法错误（主谓一致/时态/从句缺成分/搭配错误）、Chinglish 中式英语、低级重复词汇（如反复用 very good/more and more）；\n"
        "3. 对每一处问题给出地道、符合考研高分标准的英文替换句 suggestion；\n"
        "4. 可挑出 1 处写得好的句子标记为 highlight。"
    )
    sentences_text = "\n".join(f"[{s.sentence_id}] {s.text}" for s in sentences)
    user_prompt = (
        f"【题目要求】\n{question.prompt}\n\n"
        f"【考官维度初评】\n{step1.model_dump_json(ensure_ascii=False)}\n\n"
        f"【考生带编号原句】\n{sentences_text}\n\n"
        "请输出 4~8 条最核心的逐句红笔批注 JSON。"
    )
    return system_prompt, user_prompt


def build_kaoyan_step3_prompts(
    question: Question,
    student_answer: str,
    step1: KaoyanEnglishStep1Output,
) -> tuple[str, str]:
    system_prompt = (
        "你是考研英语高分升格教练。核心原则是【同思路升格】：\n"
        "1. 必须保留考生原本的段落结构和核心论点（不要推倒重写一篇陌生范文）；\n"
        "2. 修正所有语法错误，把平庸词汇和中式表达升级为地道考研高分表达，适当增加非谓语、倒装或定语从句提升句式多样性；\n"
        "3. 字数控制在 170~200 词之间，确保考生看完能直接吸收背诵。"
    )
    user_prompt = (
        f"【题目要求】\n{question.prompt}\n\n"
        f"【考生原稿】\n{student_answer}\n\n"
        f"【已识别的问题】\n{step1.model_dump_json(ensure_ascii=False)}\n\n"
        "请输出同思路高分升格版作文及 3~5 条中文核心改动说明 JSON。"
    )
    return system_prompt, user_prompt
