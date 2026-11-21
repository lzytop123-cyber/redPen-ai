import json
from app.schemas import (
    NumberedSentence,
    Question,
    ShenlunEssayStep1Output,
    ShenlunStep1Output,
)


def is_396_argument_analysis(question: Question) -> bool:
    """判断 396 写作题目是否为「论证有效性分析」（小作文）"""
    if question.scoring_points:
        return True
    meta = f"{question.sub_type} {question.title} {question.prompt}"
    return any(k in meta for k in ("论证有效性", "缺陷", "漏洞"))


# =========================
# 一、396 论证有效性分析（小作文，20分，600字左右）— 逻辑漏洞采分点驱动
# =========================

def build_396_analysis_step1_prompts(question: Question, student_answer: str) -> tuple[str, str]:
    system_prompt = (
        "你是一位极其严苛的全国硕士研究生招生考试（396经济类综合能力 / 199管理类联考）"
        "「论证有效性分析」官方阅卷组长，秉持“按点找错、重在析理、宁严勿宽”的阅卷原则。\n"
        "你的任务是对照【标准逻辑漏洞采分点列表】，逐一核对【考生作答】的找错与析错命中情况：\n"
        "1. 只有考生准确找出了该处逻辑漏洞（定位准），并且清晰剖析了“为什么前提推不出结论/逻辑为何不成立”（说理透），才能判定为 hit；\n"
        "2. 如果考生找到了该处漏洞，但只贴了逻辑谬误标签、套用空洞万能模板而未结合材料具体分析，或说理牵强浮于表面，判定为 partial；\n"
        "3. 如果考生完全未指出该处漏洞，或误把材料中的背景事实当作逻辑漏洞攻击，判定为 miss；\n"
        "4. 凡是判定为 hit 或 partial，必须忠实逐字摘录考生原文作为 evidence_quote，严禁编造或改写；\n"
        "5. structure_score_ratio（0~1）重点评估：标题是否具有质疑性（如《……未必……》《……果真如此吗？》）、"
        "首段是否简明概括原论证结论并亮明质疑态度、尾段是否收束有力、全文语言是否客观平实（严禁主观辱骂或情绪化用词）。"
    )

    points_text = json.dumps(
        [p.model_dump() for p in question.scoring_points],
        ensure_ascii=False,
        indent=2,
    )
    user_prompt = (
        f"【题目要求】\n{question.prompt}\n\n"
        f"【给定论证材料原文】\n{question.material_summary}\n\n"
        f"【标准逻辑漏洞采分点列表】\n{points_text}\n\n"
        f"【考生作答原文】\n{student_answer}\n\n"
        "每个给定编号必须且只能出现一次。命中证据（evidence_quote）必须逐字摘录考生连续原文。请输出 JSON。"
    )
    return system_prompt, user_prompt


def build_396_analysis_step2_prompts(
    question: Question,
    sentences: list[NumberedSentence],
    step1: ShenlunStep1Output,
) -> tuple[str, str]:
    system_prompt = (
        "你是 396 经综 / 199 管综「论证有效性分析」逐句红笔精批名师。请针对考生带编号的句子（S1, S2...）给出精准红笔批注。\n"
        "要求：\n"
        "1. 每条批注的 sentence_id 必须严格来自输入列表，严禁自创编号；\n"
        "2. 重点揪出：引用原材料过长占字数（建议“引述不超过1行”）、只贴标签不讲道理（模板化套话）、"
        "误把背景事实当漏洞、语言主观情绪化（如“作者简直荒谬至极”应改为“这一推论有失偏颇”）、析错因果链条断裂；\n"
        "3. 如果有析错一针见血、逻辑术语运用极佳的句子，可给 1 条 highlight 表扬；\n"
        "4. 每条批注必须给出可直接替换的高分规范析错改写 suggestion。"
    )
    sentences_text = "\n".join(f"[{s.sentence_id}] {s.text}" for s in sentences)
    step1_summary = step1.model_dump_json(ensure_ascii=False)
    user_prompt = (
        f"【题目要求】\n{question.prompt}\n\n"
        f"【给定论证材料】\n{question.material_summary}\n\n"
        f"【已核对的逻辑漏洞命中情况】\n{step1_summary}\n\n"
        f"【考生带编号原句】\n{sentences_text}\n\n"
        "请输出逐句红笔批注 JSON（挑出最关键的 4~7 处即可，宁缺毋滥）。"
    )
    return system_prompt, user_prompt


def build_396_analysis_step3_prompts(
    question: Question,
    student_answer: str,
    step1: ShenlunStep1Output,
) -> tuple[str, str]:
    system_prompt = (
        "你是 396 经综「论证有效性分析」高分升格教练。核心原则是【同思路升格】：\n"
        "1. 保留考生已经找准的逻辑漏洞段落顺序与基本切入视角；\n"
        "2. 将考生说理薄弱（partial）的段落按照“引述原论证（精简）+ 指出逻辑漏洞本质 + 剖析为何A推不出B（多元归因/反例/概念界定）”进行强化；\n"
        "3. 将考生遗漏（miss）的核心逻辑漏洞自然补齐，确保全文精准覆盖 4 个核心逻辑漏洞；\n"
        "4. 拟定规范的质疑性标题，全文控制在 600 字左右（560~650 字）。"
    )
    points_text = "\n".join(
        f"- {p.point_id} ({p.keyword}): {p.description}" for p in question.scoring_points
    )
    user_prompt = (
        f"【题目要求】\n{question.prompt}\n\n"
        f"【给定论证材料】\n{question.material_summary}\n\n"
        f"【标准逻辑漏洞采分点】\n{points_text}\n\n"
        f"【考生原稿】\n{student_answer}\n\n"
        f"【本次核对出的遗漏与问题】\n{step1.model_dump_json(ensure_ascii=False)}\n\n"
        "请输出同思路升格版论证有效性分析（含规范标题）及 3~5 条核心改动亮点 JSON。"
    )
    return system_prompt, user_prompt


# =========================
# 二、396 论说文（大作文，20分，700字左右）& 自定义无预置采分点题目 — 四维五档量表驱动
# =========================

def build_396_essay_step1_prompts(question: Question, student_answer: str) -> tuple[str, str]:
    if is_396_argument_analysis(question):
        system_prompt = (
            "你是一位严苛的 396 经济类综合能力「论证有效性分析」阅卷组长。\n"
            "请按以下 4 个固定维度对考生作文进行 1~5 档定级：\n"
            "1. 逻辑漏洞识别准确度（weight: 0.35）：是否精准找到材料中 4 处核心推理谬误，有无误伤背景事实；\n"
            "2. 析错说理深度与有效性（weight: 0.35）：是否清晰讲透“为什么前提推不出结论”，有无生搬硬套万能模板；\n"
            "3. 篇章结构与质疑性标题（weight: 0.15）：标题是否规范、首尾段是否干净利落、四段析错是否层次分明；\n"
            "4. 语言客观简练与逻辑语感（weight: 0.15）：引述是否精炼、用词是否客观严谨。\n"
            "同时必须判定：thesis_accuracy（accurate=核心漏洞找准4处, partial=找准2~3处或有偏差, off_topic=未找准漏洞或写成驳论文）"
            "以及 material_usage（结合原论证具体内容析错的程度：strong/moderate/weak）。"
        )
    else:
        system_prompt = (
            "你是一位严苛的全国硕士研究生招生考试（396经济类综合能力 / 199管理类联考）"
            "「论说文」官方阅卷组长，秉持“立意精准、说理为王、忌堆砌例子”的阅卷原则。\n"
            "请按以下 4 个固定维度对考生论说文进行 1~5 档定级：\n"
            "1. 审题立意与中心论点（weight: 0.30）：是否紧扣材料核心矛盾/主旨，立意是否明确、辩证深刻；\n"
            "2. 逻辑论证与说理深度（weight: 0.35）：是否深入剖析因果机理与内在逻辑（严厉打击“分论点+长篇故事/例子堆砌”的以叙代议写法）；\n"
            "3. 篇章结构与层次衔接（weight: 0.20）：标题是否鲜明、引论-本论-结论结构是否严谨、分论点之间是否逻辑递进或平行；\n"
            "4. 语言规范与经管思维素养（weight: 0.15）：语言是否理性流畅、有经济学/管理学思维深度，杜绝空洞抒情或口号堆砌。\n"
            "同时必须明确判定：中心论点是否切题（thesis_accuracy: accurate/partial/off_topic）以及对给定材料的提炼结合度（material_usage: strong/moderate/weak）。"
        )

    user_prompt = (
        f"【396写作题目要求】\n{question.prompt}\n\n"
        f"【给定材料】\n{question.material_summary}\n\n"
        f"【参考立意/范文参考】\n{question.reference_answer}\n\n"
        f"【考生作答原文】\n{student_answer}\n\n"
        "请严格按 4 个维度定档并输出 JSON。"
    )
    return system_prompt, user_prompt


def build_396_essay_step2_prompts(
    question: Question,
    sentences: list[NumberedSentence],
    step1: ShenlunEssayStep1Output,
) -> tuple[str, str]:
    is_analysis = is_396_argument_analysis(question)
    role_desc = "396论证有效性分析" if is_analysis else "396论说文（大作文）"
    focus_points = (
        "引用材料过长、只贴谬误标签不讲道理、误把背景当漏洞、语言情绪化"
        if is_analysis
        else "以叙代议（只举例子不做因果说理分析）、分论点口号化/不平行、开头引材料过长、结尾空喊口号、逻辑跳跃"
    )
    system_prompt = (
        f"你是{role_desc}逐句红笔精批名师。请对带编号原句（S1, S2...）揪出核心硬伤：\n"
        "1. sentence_id 必须严格来自输入列表；\n"
        f"2. 重点批注：{focus_points}；\n"
        "3. 每条批注必须给出可直接替换的高分理性说理改写 suggestion（可包含 1 条 highlight 表扬精彩说理句）。"
    )
    sentences_text = "\n".join(f"[{s.sentence_id}] {s.text}" for s in sentences)
    user_prompt = (
        f"【题目要求】\n{question.prompt}\n\n"
        f"【给定材料】\n{question.material_summary}\n\n"
        f"【维度初评】\n{step1.model_dump_json(ensure_ascii=False)}\n\n"
        f"【考生带编号原句】\n{sentences_text}\n\n"
        "请输出 4~8 条最关键的逐句红笔批注 JSON。"
    )
    return system_prompt, user_prompt


def build_396_essay_step3_prompts(
    question: Question,
    student_answer: str,
    step1: ShenlunEssayStep1Output,
) -> tuple[str, str]:
    is_analysis = is_396_argument_analysis(question)
    if is_analysis:
        system_prompt = (
            "你是 396 经综「论证有效性分析」高分升格教练。核心原则是【同思路升格】：\n"
            "1. 尽量保留考生已找出的合理逻辑漏洞切入点，补齐遗漏的核心漏洞（共 4 个核心漏洞点）；\n"
            "2. 每个漏洞段严格遵循“精简引述 + 明确逻辑缺陷 + 深入剖析为何推不出”的高分范式；\n"
            "3. 拟定规范质疑性标题，全文控制在 600 字左右，并列出 3~5 条核心提分亮点。"
        )
    else:
        system_prompt = (
            "你是 396 经综「论说文」高分升格教练。核心原则是【同思路升格】：\n"
            "1. 尽量保留考生原有的中心论点和分论点框架（若立意偏题则纠偏后保留考生已有的合理案例素材）；\n"
            "2. 把考生原本“只摆观点+堆砌例子”的段落，升格为“观点提炼 + 因果机理深度说理 + 精炼例证融合 + 回扣论点”的经管高分议论文范式；\n"
            "3. 强化首段一针见血破题，全文控制在 700 字左右（660~750 字），并列出 3~5 条核心提分亮点。"
        )
    user_prompt = (
        f"【题目要求】\n{question.prompt}\n\n"
        f"【给定材料】\n{question.material_summary}\n\n"
        f"【参考立意/范文参考】\n{question.reference_answer}\n\n"
        f"【考生原稿】\n{student_answer}\n\n"
        f"【本次诊断问题】\n{step1.model_dump_json(ensure_ascii=False)}\n\n"
        "请输出同思路升格版作文及 3~5 条核心提分亮点 JSON。"
    )
    return system_prompt, user_prompt
