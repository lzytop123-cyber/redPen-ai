import asyncio
from pathlib import Path
from typing import Callable, Optional

from app.llm_client import LLMRouter
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
