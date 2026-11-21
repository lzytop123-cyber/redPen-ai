import asyncio
from pathlib import Path
from typing import Callable, Optional

from app.llm_client import LLMRouter
from app.prompts.kaoyan_396 import (
    build_396_analysis_step1_prompts,
    build_396_analysis_step2_prompts,
    build_396_analysis_step3_prompts,
    build_396_essay_step1_prompts,
    build_396_essay_step2_prompts,
    build_396_essay_step3_prompts,
)
from app.prompts.kaoyan_english import (
    build_kaoyan_step1_prompts,
    build_kaoyan_step2_prompts,
    build_kaoyan_step3_prompts,
)
from app.prompts.shenlun import (
    build_shenlun_essay_step1_prompts,
    build_shenlun_essay_step2_prompts,
    build_shenlun_essay_step3_prompts,
    build_shenlun_step1_prompts,
    build_shenlun_step2_prompts,
    build_shenlun_step3_prompts,
)
from app.schemas import (
    DimensionRating,
    ExamType,
    GradingReport,
    KaoyanEnglishStep1Output,
    PointMatchResult,
    Question,
    SentenceAnnotation,
    ShenlunEssayStep1Output,
    ShenlunStep1Output,
    Step2AnnotationOutput,
    Step3UpgradeOutput,
)
from app.utils import (
    calculate_kaoyan_english_score,
    calculate_shenlun_essay_score,
    calculate_shenlun_score,
    check_word_count_warning,
    count_words,
    split_numbered_sentences,
)

ProgressCallback = Optional[Callable[[str], None]]


class GradingPipeline:
    """
    核心 3 步确定性批改管线：
    Step 0 (可选): 手写答卷照片 -> 视觉模型 OCR 识别
    Step 1: 采分点 / 官方五档量表核对 -> 后端代码确定性算分
    Step 2: 带 ID 句子切分 -> 逐句红笔批注（严格绑定 sentence_id，过滤非法 ID）
    Step 3: 基于原稿生成「同思路升格范文」
    """

    def __init__(self, router: Optional[LLMRouter] = None) -> None:
        self.router = router or LLMRouter()

    async def run(
        self,
        question: Question,
        student_answer: Optional[str] = None,
        image_path: Optional[str | Path] = None,
        mock: bool = False,
        on_progress: ProgressCallback = None,
    ) -> GradingReport:
        def notify(msg: str) -> None:
            if on_progress:
                on_progress(msg)

        # Step 0: 获取文本（支持拍照 OCR 或直接文本）
        if not student_answer and image_path:
            notify("Step 0/3: 正在识别手写答卷照片...")
            if mock:
                raise ValueError("Mock 模式请直接传入文本作答，或去掉 --mock 使用真实视觉模型识别图片。")
            student_answer = await self.router.ocr_handwriting(image_path)

        if not student_answer or not student_answer.strip():
            raise ValueError("考生作答内容不能为空（请提供文本或手写图片路径）。")

        word_count = count_words(student_answer, question.exam_type)
        word_warning = check_word_count_warning(word_count, question)
        sentences = split_numbered_sentences(student_answer, question.exam_type)
        valid_ids = {s.sentence_id for s in sentences}

        if mock:
            return self._build_mock_report(question, student_answer, word_count, word_warning, sentences, notify)

        # Step 1: 采分点/量表核对 + 代码确定性算分
        notify("Step 1/3: 正在对照官方评分细则与采分点核对...")
        shenlun_detail: Optional[ShenlunStep1Output] = None
        shenlun_essay_detail: Optional[ShenlunEssayStep1Output] = None
        kaoyan_detail: Optional[KaoyanEnglishStep1Output] = None

        if question.exam_type == ExamType.SHENLUN_SHORT:
            sys1, usr1 = build_shenlun_step1_prompts(question, student_answer)
            shenlun_detail = await self.router.call_structured(
                sys1, usr1, ShenlunStep1Output,
                validation_context={
                    "point_ids": {point.point_id for point in question.scoring_points},
                    "student_answer": student_answer,
                },
            )
            final_score, band_label = calculate_shenlun_score(question, shenlun_detail, word_count)
            weakness_tags = shenlun_detail.weakness_tags

            sys2, usr2 = build_shenlun_step2_prompts(question, sentences, shenlun_detail)
            sys3, usr3 = build_shenlun_step3_prompts(question, student_answer, shenlun_detail)
        elif question.exam_type == ExamType.SHENLUN_ESSAY:
            sys1, usr1 = build_shenlun_essay_step1_prompts(question, student_answer)
            shenlun_essay_detail = await self.router.call_structured(sys1, usr1, ShenlunEssayStep1Output)
            final_score, band_label = calculate_shenlun_essay_score(question, shenlun_essay_detail, word_count)
            weakness_tags = shenlun_essay_detail.weakness_tags

            sys2, usr2 = build_shenlun_essay_step2_prompts(question, sentences, shenlun_essay_detail)
            sys3, usr3 = build_shenlun_essay_step3_prompts(question, student_answer, shenlun_essay_detail)
        elif question.exam_type == ExamType.KAOYAN_396:
            if question.scoring_points:
                sys1, usr1 = build_396_analysis_step1_prompts(question, student_answer)
                shenlun_detail = await self.router.call_structured(
                    sys1, usr1, ShenlunStep1Output,
                    validation_context={
                        "point_ids": {point.point_id for point in question.scoring_points},
                        "student_answer": student_answer,
                    },
                )
                final_score, band_label = calculate_shenlun_score(question, shenlun_detail, word_count)
                weakness_tags = shenlun_detail.weakness_tags

                sys2, usr2 = build_396_analysis_step2_prompts(question, sentences, shenlun_detail)
                sys3, usr3 = build_396_analysis_step3_prompts(question, student_answer, shenlun_detail)
            else:
                sys1, usr1 = build_396_essay_step1_prompts(question, student_answer)
                shenlun_essay_detail = await self.router.call_structured(sys1, usr1, ShenlunEssayStep1Output)
                final_score, band_label = calculate_shenlun_essay_score(question, shenlun_essay_detail, word_count)
                weakness_tags = shenlun_essay_detail.weakness_tags

                sys2, usr2 = build_396_essay_step2_prompts(question, sentences, shenlun_essay_detail)
                sys3, usr3 = build_396_essay_step3_prompts(question, student_answer, shenlun_essay_detail)
        else:
            sys1, usr1 = build_kaoyan_step1_prompts(question, student_answer)
            kaoyan_detail = await self.router.call_structured(sys1, usr1, KaoyanEnglishStep1Output)
            final_score, band_label = calculate_kaoyan_english_score(question, kaoyan_detail, word_count)
            weakness_tags = kaoyan_detail.weakness_tags

            sys2, usr2 = build_kaoyan_step2_prompts(question, sentences, kaoyan_detail)
            sys3, usr3 = build_kaoyan_step3_prompts(question, student_answer, kaoyan_detail)

        # Step 2 & Step 3 相互独立，可并发执行大幅缩短用户等待时间！
        notify("Step 2 & 3/3: 正在并发生成逐句红笔批注与同思路升格范文...")
        step2_res, step3_res = await asyncio.gather(
            self.router.call_structured(sys2, usr2, Step2AnnotationOutput),
            self.router.call_structured(sys3, usr3, Step3UpgradeOutput),
        )

        # 二次防线：过滤掉任何未绑定有效 sentence_id 的幻觉批注
        clean_annotations = [
            ann for ann in step2_res.annotations if ann.sentence_id in valid_ids
        ]

        notify("精批完成！")
        return GradingReport(
            question_id=question.question_id,
            exam_type=question.exam_type,
            question_title=question.title,
            student_answer=student_answer,
            word_count=word_count,
            word_count_warning=word_warning,
            final_score=final_score,
            full_score=question.full_score,
            band_label=band_label,
            shenlun_detail=shenlun_detail,
            shenlun_essay_detail=shenlun_essay_detail,
            kaoyan_detail=kaoyan_detail,
            sentences=sentences,
            annotations=clean_annotations,
            upgraded_answer=step3_res.upgraded_answer,
            key_improvements=step3_res.key_improvements,
            weakness_tags=weakness_tags,
        )

    def _build_mock_report(
        self,
        question: Question,
        student_answer: str,
        word_count: int,
        word_warning: Optional[str],
        sentences,
        notify,
    ) -> GradingReport:
        """零费用本地演示模式：用于验证代码算分引擎、Schema 与红笔报告渲染"""
        notify("[Mock 模式] 正在模拟 3 步精批流水线...")
        s1_id = sentences[0].sentence_id if sentences else "S1"
        s2_id = sentences[1].sentence_id if len(sentences) > 1 else s1_id

        if question.exam_type == ExamType.KAOYAN_396:
            if question.scoring_points:
                mock_396_step1 = ShenlunStep1Output(
                    point_matches=[
                        PointMatchResult(
                            point_id=p.point_id,
                            status="hit" if idx < 2 else ("partial" if idx == 2 else "miss"),
                            evidence_quote=sentences[0].text[:25] if idx < 3 and sentences else "",
                            comment=(
                                f"准确定位了「{p.keyword}」这一逻辑漏洞，且析错说理切中要害。"
                                if idx < 2
                                else (
                                    f"指出了「{p.keyword}」位置，但仅套用模板化术语，未结合材料具体分析为何前提推不出结论。"
                                    if idx == 2
                                    else f"遗漏了材料中关键的「{p.keyword}」逻辑漏洞，建议补充剖析。"
                                )
                            ),
                        )
                        for idx, p in enumerate(question.scoring_points)
                    ],
                    structure_score_ratio=0.75,
                    structure_comment="具备“引论—析错—结论”基本框架，但部分段落引述原题干过长，且析错深度不均衡。",
                    weakness_tags=["漏找核心逻辑漏洞", "析错流于模板套话", "引述原材料偏长"],
                )
                final_score, band = calculate_shenlun_score(question, mock_396_step1, word_count)
                return GradingReport(
                    question_id=question.question_id,
                    exam_type=question.exam_type,
                    question_title=question.title,
                    student_answer=student_answer,
                    word_count=word_count,
                    word_count_warning=word_warning,
                    final_score=final_score,
                    full_score=question.full_score,
                    band_label=band,
                    shenlun_detail=mock_396_step1,
                    sentences=sentences,
                    annotations=[
                        SentenceAnnotation(
                            sentence_id=s1_id,
                            issue_type="logic",
                            severity="medium",
                            original_excerpt=sentences[0].text[:22] if sentences else "",
                            comment="对逻辑漏洞的剖析停留在表面贴标签，需具体指出“他因”或“条件不充分”的中间机制。",
                            suggestion="即使降低家长主观期望值，在升学选拔机制与同辈竞争压力尚未改变的客观环境下，学生课业负担也未必能“马上减轻”，论证犯了条件不充分（简单归因）的逻辑谬误。",
                        ),
                        SentenceAnnotation(
                            sentence_id=s2_id,
                            issue_type="redundancy",
                            severity="low",
                            original_excerpt=sentences[1].text[:22] if len(sentences) > 1 else "",
                            comment="引述原论证材料的字数偏多，396论证有效性分析建议“引述不超过一行”，把篇幅留给析错说理。",
                            suggestion="材料由“马拉松冠军未必赢在起跑线”类比得出“学习不必在意起跑线”，属于不当类比。",
                        ),
                    ],
                    upgraded_answer=(
                        f"{question.reference_answer}"
                        if question.reference_answer
                        else (
                            "《如此论证果真严谨吗？》\n\n"
                            "上述材料通过一系列类比与因果推断，试图论证其核心结论的必然性。然而，该论证在推理过程中存在多处明显的逻辑漏洞，其结论有待商榷。\n\n"
                            "首先，材料犯了“条件不充分（绝对化）”的逻辑错误。单一主体的观念转变只是解决复杂问题的必要而非充分条件，忽视了制度环境与外部竞争等多重变量，因此无法必然推出立竿见影的效果。\n\n"
                            "其次，材料存在“类比不当”的缺陷。两个领域在运行周期、资源累积效应及评价规则上存在本质差异，简单将二者画等号并以此否定初始基础的作用，在逻辑上难以成立。\n\n"
                            "再次，材料混淆了“局部样本”与“整体总体”，犯了“以偏概全”的谬误。仅凭特定群体或个别案例的表现，不足以代表普遍规律。\n\n"
                            "综上所述，由于上述论证存在条件不充分、不当类比及以偏概全等逻辑缺陷，其得出的结论难以令人信服。"
                        )
                    ),
                    key_improvements=[
                        "保留了你原本找到的前三个逻辑漏洞段落顺序，将冗长的原文引述精简为“一句话定位论点→论据”。",
                        "把原本套用模板的空泛批驳，升格为结合材料具体情境的“多元归因+概念界定”深度析错。",
                        "补齐了第 4 处核心逻辑漏洞，并规范了质疑性标题与首尾段闭环。",
                    ],
                    weakness_tags=mock_396_step1.weakness_tags,
                )

            mock_396_essay = ShenlunEssayStep1Output(
                dimensions=[
                    DimensionRating(dimension="审题立意与中心论点", level=4, weight=0.30, comment="立意切合材料核心矛盾，中心论点明确，但辩证边界交代略欠。"),
                    DimensionRating(dimension="逻辑论证与说理深度", level=3, weight=0.35, comment="分论点后偏重举例叙述，缺少对“为什么”和“内在机理”的经济学/管理学层层剖析。"),
                    DimensionRating(dimension="篇章结构与层次衔接", level=4, weight=0.20, comment="五段三分式结构清晰，但段与段之间缺少递进过渡。"),
                    DimensionRating(dimension="语言规范与经管思维素养", level=4, weight=0.15, comment="行文流畅，若能适当融入成本收益、核心壁垒、系统协同等理性视角会更出彩。"),
                ],
                thesis_accuracy="accurate",
                material_usage="moderate",
                overall_comment="审题立意准确、结构完整，主要失分点在于本论段存在“以叙代议（用长例子代替逻辑说理）”倾向，说理纵深度有待加强。",
                weakness_tags=["以叙代议（重举例轻说理）", "辩证边界交代不足", "分论点递进感偏弱"],
            )
            final_score, band = calculate_shenlun_essay_score(question, mock_396_essay, word_count)
            return GradingReport(
                question_id=question.question_id,
                exam_type=question.exam_type,
                question_title=question.title,
                student_answer=student_answer,
                word_count=word_count,
                word_count_warning=word_warning,
                final_score=final_score,
                full_score=question.full_score,
                band_label=band,
                shenlun_essay_detail=mock_396_essay,
                sentences=sentences,
                annotations=[
                    SentenceAnnotation(
                        sentence_id=s1_id,
                        issue_type="logic",
                        severity="medium",
                        original_excerpt=sentences[0].text[:22] if sentences else "",
                        comment="396论说文忌讳“提出分论点后直接讲长篇故事”，应先做 2~3 句因果机理论证，再用一句话精炼点例。",
                        suggestion="任何组织与个体的资源禀赋都是有限的，唯有聚焦主航道深耕细作，才能通过持续的经验积累与技术迭代构筑起难以复制的核心护城河。",
                    ),
                    SentenceAnnotation(
                        sentence_id=s2_id,
                        issue_type="expression",
                        severity="low",
                        original_excerpt=sentences[1].text[:22] if len(sentences) > 1 else "",
                        comment="表述略显口号化，建议补充辩证限定条件，体现396经综考生的理性思辨素养。",
                        suggestion="诚然，专注并非闭门造车，而是在筑牢主业根基的前提下审慎评估边际风险，实现守正与创新的动态平衡。",
                    ),
                ],
                upgraded_answer=(
                    question.reference_answer
                    if question.reference_answer
                    else (
                        "《以深耕筑牢根基，以协同拓宽边界》\n\n"
                        "材料中展现的现象深刻揭示了现代经济社会发展的一条核心法则：任何个体与组织的持续成长，既需要聚焦核心领域的定力，也离不开顺应系统的协同与变革。\n\n"
                        "深耕主业、保持战略定力，是构筑核心竞争力的基石。从经济学视角看，注意力与资源永远是稀缺的。如果在发展的初级阶段盲目追逐短期风口，势必导致资源分散与边际效益递减。唯有耐住寂寞、将单一领域的专业能力锤炼至极致，才能形成深厚的技术壁垒与品牌声誉。\n\n"
                        "然而，专注绝非固步自封，系统思维与适度破界同样不可或缺。现代社会事务与商业竞争具有高度的复杂性与关联性，孤立的要素难以应对全局性挑战。在夯实核心优势的基础上，主动打破部门与行业壁垒，实现资源互补与多元协同，方能激活新的增长曲线。\n\n"
                        "综上所述，无论是个人求索还是企业经营，都应秉持“守正出奇”的理性智慧：以专注深耕铸就立身之本，以开放协同顺应时代之变，在动态平衡中行稳致远。"
                    )
                ),
                key_improvements=[
                    "保留了你原有的中心论点与段落骨架，把原本冗长的故事叙述压缩为一句话点例，大幅增加了因果机理说理比重。",
                    "自然融入了“稀缺资源配置”、“边际效益”、“核心壁垒”等契合 396 经综阅卷偏好的理性表达。",
                    "在倒数第二段补充了辩证限定分析，使论证逻辑无懈可击。",
                ],
                weakness_tags=mock_396_essay.weakness_tags,
            )

        if question.exam_type == ExamType.SHENLUN_SHORT:
            mock_step1 = ShenlunStep1Output(
                point_matches=[
                    PointMatchResult(
                        point_id=p.point_id,
                        status="hit" if idx == 0 else ("partial" if idx == 1 else "miss"),
                        evidence_quote=sentences[0].text[:25] if idx < 2 and sentences else "",
                        comment=(
                            "准确踩中核心关键词。"
                            if idx == 0
                            else ("方向沾边，但表述过于口语化，缺少规范总括词。" if idx == 1 else "原文未提及该关键采分点，需补充。")
                        ),
                    )
                    for idx, p in enumerate(question.scoring_points)
                ],
                structure_score_ratio=0.7,
                structure_comment="分条意识尚可，但缺少前置核心总括词，部分句子口语化偏啰嗦。",
                weakness_tags=["漏核心采分点", "表达口语化", "缺少前置总括词"],
            )
            final_score, band = calculate_shenlun_score(question, mock_step1, word_count)
            return GradingReport(
                question_id=question.question_id,
                exam_type=question.exam_type,
                question_title=question.title,
                student_answer=student_answer,
                word_count=word_count,
                word_count_warning=word_warning,
                final_score=final_score,
                full_score=question.full_score,
                band_label=band,
                shenlun_detail=mock_step1,
                sentences=sentences,
                annotations=[
                    SentenceAnnotation(
                        sentence_id=s1_id,
                        issue_type="expression",
                        severity="medium",
                        original_excerpt=sentences[0].text[:18] if sentences else "",
                        comment="表述偏大白话，申论小题建议提炼 4~6 字总括词放句首，方便阅卷老师秒找采分点。",
                        suggestion="完善基础设施建设，推进老旧管网改造与停车位扩容。",
                    ),
                    SentenceAnnotation(
                        sentence_id=s2_id,
                        issue_type="missing_point",
                        severity="high",
                        original_excerpt=sentences[1].text[:18] if len(sentences) > 1 else "",
                        comment="只提到了管理不好，遗漏了材料中明确提到的“资金筹措难”和“多元共治机制缺失”。",
                        suggestion="健全多元共治与长效运维机制，拓宽社会资本参与渠道，破解资金瓶颈。",
                    ),
                ],
                upgraded_answer=(
                    "1. 硬件设施滞后：老旧管网老化、公共停车位与适老化设施不足。\n"
                    "2. 治理机制缺位：物业监管不力，缺乏居民参与和多元共治平台。\n"
                    "3. 资金保障不足：过度依赖财政补贴，长效运维资金筹措渠道单一。\n"
                    "4. 精细服务欠缺：未能精准对接一老一小等差异化民生需求。"
                ),
                key_improvements=[
                    "保留了你原本的分条作答框架，每条前置 6 字核心总括词，阅卷扫一眼即给分。",
                    "补齐了遗漏的“资金保障”与“精细服务”两个高分采分点。",
                    "将口语化长句压缩精炼，控制在最佳字数区间内。",
                ],
                weakness_tags=mock_step1.weakness_tags,
            )

        mock_ky = KaoyanEnglishStep1Output(
            dimensions=[
                DimensionRating(dimension="内容切题与要点覆盖", level=4, weight=0.35, comment="基本覆盖图画/图表核心含义，但原因分析略浅。"),
                DimensionRating(dimension="语法准确性与拼写规范", level=3, weight=0.25, comment="存在主谓一致与中式语序问题。"),
                DimensionRating(dimension="词汇丰富度与高级句式", level=3, weight=0.25, comment="反复使用 very important / more and more 等平庸表达。"),
                DimensionRating(dimension="篇章结构与逻辑衔接", level=4, weight=0.15, comment="三段式清晰，但段内衔接词偏单一。"),
            ],
            template_risk="medium",
            overall_comment="整体切题、结构完整，但语言平庸且有明显中式英语与低级语法硬伤，目前停留在中等偏上水平。",
            weakness_tags=["词汇重复平庸", "中式英语表达", "句式单一"],
        )
        final_score, band = calculate_kaoyan_english_score(question, mock_ky, word_count)
        return GradingReport(
            question_id=question.question_id,
            exam_type=question.exam_type,
            question_title=question.title,
            student_answer=student_answer,
            word_count=word_count,
            word_count_warning=word_warning,
            final_score=final_score,
            full_score=question.full_score,
            band_label=band,
            kaoyan_detail=mock_ky,
            sentences=sentences,
            annotations=[
                SentenceAnnotation(
                    sentence_id=s1_id,
                    issue_type="expression",
                    severity="medium",
                    original_excerpt=sentences[0].text[:35] if sentences else "",
                    comment="“more and more people” 属于考研高频低分套话，建议升级为更地道的学术表达。",
                    suggestion="An increasing number of young individuals have come to embrace traditional culture.",
                ),
                SentenceAnnotation(
                    sentence_id=s2_id,
                    issue_type="grammar",
                    severity="high",
                    original_excerpt=sentences[1].text[:35] if len(sentences) > 1 else "",
                    comment="存在主谓不一致或逗号拼接两个完整句（Comma Splice）的典型扣分硬伤。",
                    suggestion="Not only does this trend enrich their spiritual lives, but it also revitalizes cultural heritage.",
                ),
            ],
            upgraded_answer=(
                "As is vividly depicted in the chart, an increasing number of young people are gravitating toward "
                "traditional cultural venues such as museums and heritage workshops. Behind this encouraging phenomenon "
                "lie two primary driving forces.\n\n"
                "First and foremost, digital innovation has breathed new life into time-honored traditions, making them "
                "far more accessible and engaging for Generation Z. Furthermore, rising cultural confidence motivates "
                "youngsters to seek spiritual resonance from their own historical roots rather than blindly chasing fleeting trends.\n\n"
                "From my perspective, this trend deserves wholehearted encouragement. Only by blending heritage with "
                "modernity can traditional culture thrive continuously in the new era."
            ),
            key_improvements=[
                "完整保留了你原有的“描述现象—双因分析—总结展望”三段思路。",
                "将 more and more / very good 等低级词升级为 gravitating toward / breathed new life into。",
                "修正了中式语序，并自然融入倒装句（Only by... can...）提升句式档次。",
            ],
            weakness_tags=mock_ky.weakness_tags,
        )
