import asyncio
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from app.llm_client import LLMRouter
from app.pipeline import GradingPipeline

from pydantic import ValidationError

from app.schemas import Question, ShenlunStep1Output
from app.utils import calculate_shenlun_score
from app.word_limits import short_answer_limits


class ShenlunGradingTests(unittest.TestCase):
    def setUp(self):
        rows = json.loads(Path("data/shenlun_questions.json").read_text(encoding="utf-8"))
        row = next(item for item in rows if item["question_id"] == "GD-2026-zf-S01")
        self.question = Question.model_validate(dict(row, min_words=120))
        self.matches = [
            dict(point_id=p.point_id, status="hit", evidence_quote="原文", comment="测试")
            for p in self.question.scoring_points
        ]
        self.context = dict(point_ids={p.point_id for p in self.question.scoring_points},
                            student_answer="答卷原文")

    def validate(self, matches):
        return ShenlunStep1Output.model_validate(
            dict(point_matches=matches, structure_score_ratio=1, structure_comment="测试"),
            context=self.context,
        )

    def test_upper_limit_only(self):
        self.assertEqual((self.question.min_words, self.question.max_words), (0, 200))
        detail = self.validate(self.matches)
        for words in (89, 90, 200):
            self.assertEqual(calculate_shenlun_score(self.question, detail, words)[0], 15)
        self.assertLess(calculate_shenlun_score(self.question, detail, 250)[0], 15)

    def test_pipeline_retries_unverified_quote(self):
        valid = self.validate(self.matches).model_dump()
        invalid = dict(valid, point_matches=[dict(self.matches[0], evidence_quote="编造"), *self.matches[1:]])
        payloads = [invalid, valid, {"annotations": []}, {"upgraded_answer": "改写", "key_improvements": []}]
        responses = [
            SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(payload)))])
            for payload in payloads
        ]
        router = LLMRouter()
        with patch.object(router.text_client.chat.completions, "create",
                          new=AsyncMock(side_effect=responses)) as call:
            report = asyncio.run(GradingPipeline(router).run(self.question, "答卷原文"))
        self.assertEqual(call.await_count, 4)
        self.assertEqual(report.final_score, 15)
        self.assertEqual(report.shenlun_detail.point_matches[0].evidence_quote, "原文")

    def test_other_limits(self):
        for prompt, expected in [
            ("不少于100字，不超过200字", (100, 200)),
            ("100至200字", (100, 200)),
            ("不少于100字", (100, 0)),
            ("请概括原因", (80, 150)),
        ]:
            self.assertEqual(short_answer_limits(prompt, 80, 150), expected)

    def test_reject_invalid_matches(self):
        first, *rest = self.matches
        for matches in [rest, [first, first, *rest], [dict(first, point_id="unknown"), *rest],
                        [dict(first, evidence_quote="编造"), *rest],
                        [dict(first, status="partial", evidence_quote=" "), *rest]]:
            with self.subTest(matches=matches), self.assertRaises(ValidationError):
                self.validate(matches)
        self.validate([dict(first, status="miss", evidence_quote=""), *rest])

    def test_quote_allows_whitespace_and_punctuation_normalization(self):
        ctx = dict(
            point_ids={p.point_id for p in self.question.scoring_points},
            student_answer="1.提升艺术设计能力,\n注重原创外观。",
        )
        matches = [
            dict(point_id=p.point_id, status="hit", evidence_quote="提升艺术设计能力，注重原创外观", comment="测试")
            for p in self.question.scoring_points
        ]
        ShenlunStep1Output.model_validate(
            dict(point_matches=matches, structure_score_ratio=1, structure_comment="测试"),
            context=ctx,
        )

    def test_point_builder_filters_ungrounded_quotes(self):
        from app.point_builder import PointBuildOutput, PointDraft, build_grounded_scoring_points

        q = Question(
            question_id="SC-2023-TEST-S01",
            exam_type="shenlun_short",
            title="四川测试题",
            prompt="概括主要做法（15分），不超过200字。",
            material_summary="给定材料1：S市通过建立数字化监测平台实现了全天候精准监管，同时引入社会资本参与老旧管网改造。",
            full_score=15.0,
        )
        fake_out = PointBuildOutput(
            sub_type="单一题（归纳概括）",
            scoring_points=[
                PointDraft(keyword="数字精准监管", description="建立数字化监测平台", weight=3, material_quote="建立数字化监测平台实现了全天候精准监管"),
                PointDraft(keyword="幻觉编造点", description="不存在的内容", weight=2, material_quote="这段话在原文里根本不存在"),
            ],
            reference_answer="1.数字精准监管。",
        )
        router = LLMRouter()
        with patch.object(router, "call_structured", new=AsyncMock(return_value=fake_out)):
            pts, ref, sub = asyncio.run(build_grounded_scoring_points(router, q))
        self.assertEqual(len(pts), 1)
        self.assertEqual(pts[0].keyword, "数字精准监管")
        self.assertEqual(sub, "单一题（归纳概括）")
