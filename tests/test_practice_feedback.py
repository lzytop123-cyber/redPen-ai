import unittest

from app.api.routes_questions import _word_limits
from app.api.routes_grading import _attach_material_evidence
from app.db.models import QuestionModel
from app.prompts.kaoyan_english import build_kaoyan_step1_prompts
from app.schemas import Question
from app.utils import check_word_count_warning


class PracticeFeedbackTests(unittest.TestCase):
    def english_question(self, prompt, low, high):
        row = dict(question_id="test", title="Writing", exam_type="kaoyan_english",
                   full_score=20, prompt=prompt, min_words=low, max_words=high)
        return QuestionModel(**row), Question(**row)

    def test_prompt_range_overrides_old_database_limits_in_api_and_grading(self):
        row, question = self.english_question("Write 160–200 words.", 150, 240)
        self.assertEqual(_word_limits(row), {
            "min_words": 160, "max_words": 200, "word_requirement": "160～200 词"})
        self.assertEqual((question.min_words, question.max_words), (160, 200))
        self.assertIn("1 词", check_word_count_warning(201, question))

    def test_approximate_target_is_displayed_separately_from_scoring_tolerance(self):
        row, question = self.english_question("Write about 100 words.", 90, 130)
        self.assertEqual(_word_limits(row)["word_requirement"], "约 100 词")
        self.assertIsNone(check_word_count_warning(96, question))

    def test_custom_short_letter_is_not_graded_as_a_long_essay(self):
        row, question = self.english_question("Write about 100 words.", 160, 220)
        self.assertIsNone(check_word_count_warning(100, question))
        self.assertEqual(_word_limits(row)["word_requirement"], "约 100 词")

    def test_only_exact_material_text_can_be_used_as_evidence(self):
        question = Question(question_id="S", title="申论", exam_type="shenlun_short",
                            prompt="概括做法", full_score=10, material_summary="材料2：居民和社区共同出资。",
                            scoring_points=[
                                dict(point_id="P1", score=2, keyword="资金共筹",
                                     description="居民和社区共同出资", material_quote="编造的摘录"),
                                dict(point_id="P2", score=2, keyword="另一种做法", description="材料没有提到"),
                            ])
        matches = [{"point_id": "P1"}, {"point_id": "P2"}]
        _attach_material_evidence({"shenlun_detail": {"point_matches": matches}}, question)
        self.assertEqual(matches[0]["material_quote"], "居民和社区共同出资")
        self.assertEqual(matches[0]["keyword"], "资金共筹")
        self.assertEqual(matches[0]["material_section"], "材料2")
        self.assertNotIn("material_quote", matches[1])

    def test_english_grader_receives_the_values_in_the_practice_chart(self):
        _, question = self.english_question("Write about 150 words based on the chart.", 140, 190)
        question.question_id = "KY-2023-E2-B"
        _, prompt = build_kaoyan_step1_prompts(question, "The rate increased.")
        self.assertIn("8.8%", prompt)
        self.assertIn("25.4%", prompt)

    def test_kaoyan_396_word_limits_and_pipeline_grading(self):
        import asyncio
        import json
        from pathlib import Path
        from app.pipeline import GradingPipeline

        rows = json.loads(Path("data/kaoyan_396_questions.json").read_text(encoding="utf-8"))
        q_analysis_dict = next(r for r in rows if r["question_id"] == "KY396-2023-A")
        q_essay_dict = next(r for r in rows if r["question_id"] == "KY396-2025-B")

        q_analysis = Question.model_validate(q_analysis_dict)
        q_essay = Question.model_validate(q_essay_dict)
        self.assertEqual((q_analysis.min_words, q_analysis.max_words), (540, 680))
        self.assertEqual((q_essay.min_words, q_essay.max_words), (630, 780))

        row_396 = QuestionModel(**{k: v for k, v in q_analysis_dict.items() if k != "scoring_points"}, scoring_points=q_analysis_dict["scoring_points"])
        self.assertIn("600", _word_limits(row_396)["word_requirement"])

        pipeline = GradingPipeline()
        rep_a = asyncio.run(
            pipeline.run(
                q_analysis,
                student_answer="首先，降低期望值未必马上减轻负担。其次，将学习类比马拉松不当。再次，素质教育未必减负。最后，出台法规并非充分条件。",
                mock=True,
            )
        )
        self.assertIsNotNone(rep_a.shenlun_detail)
        self.assertEqual(len(rep_a.shenlun_detail.point_matches), 4)
        payload_a = rep_a.model_dump()
        _attach_material_evidence(payload_a, q_analysis)
        self.assertEqual(
            payload_a["shenlun_detail"]["point_matches"][0]["material_quote"],
            "破除“望子成龙”的传统观念，把家长的期望值降低一些，中小学生过重的学习负担马上就减轻了",
        )

        rep_b = asyncio.run(
            pipeline.run(
                q_essay,
                student_answer="企业发展既需要专注深耕筑牢技术壁垒，又需要审慎跨界激发第二增长曲线。唯有守正出奇方能行稳致远。",
                mock=True,
            )
        )
        self.assertIsNotNone(rep_b.shenlun_essay_detail)
        self.assertEqual(len(rep_b.shenlun_essay_detail.dimensions), 4)

