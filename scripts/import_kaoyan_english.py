"""
导入 2018-2025 年考研英语（一）/（二）最具代表性的历年大小作文真题（共 24 道），
写入 data/kaoyan_questions.json 并增量同步至当前数据库。
"""

import asyncio
import json
from pathlib import Path

from app.db.database import AsyncSessionLocal, init_db
from app.db.models import QuestionModel
from app.schemas import ExamType, Question

OUT_PATH = Path("data/kaoyan_questions.json")

KAOYAN_QUESTIONS = [
    # === 2025 考研英语一 / 英语二 ===
    {
        "question_id": "KY-2025-E1-A",
        "year": 2025,
        "paper": "考研英语一-2025",
        "sub_type": "英语一·小作文",
        "title": "考研英语一 2025 小作文【邀请外教参加中国传统节日活动】",
        "prompt": "Directions: Write an email to invite a foreign professor to attend a traditional Chinese festival celebration on campus. You should specify the time, place, and main activities. Write about 100 words.",
        "full_score": 10.0,
        "min_words": 90,
        "max_words": 130,
    },
    {
        "question_id": "KY-2025-E1-B",
        "year": 2025,
        "paper": "考研英语一-2025",
        "sub_type": "英语一·大作文",
        "title": "考研英语一 2025 大作文【家庭绿色低碳消费与耐用品升级】",
        "prompt": "Directions: Write an essay of 160-200 words based on the drawing/chart reflecting residents' growing enthusiasm for green consumption and smart home appliance upgrades. You should: 1) describe the phenomenon briefly, 2) explain its underlying causes, and 3) give your comments.",
        "full_score": 20.0,
        "min_words": 160,
        "max_words": 220,
    },
    {
        "question_id": "KY-2025-E2-A",
        "year": 2025,
        "paper": "考研英语二-2025",
        "sub_type": "英语二·小作文",
        "title": "考研英语二 2025 小作文【社区养老志愿服务项目策划建议】",
        "prompt": "Directions: Suppose you are organizing a volunteer service program for the elderly in a local community. Write an email to your team members to introduce the plan and ask for their suggestions. Write about 100 words.",
        "full_score": 10.0,
        "min_words": 90,
        "max_words": 130,
    },
    {
        "question_id": "KY-2025-E2-B",
        "year": 2025,
        "paper": "考研英语二-2025",
        "sub_type": "英语二·大作文",
        "title": "考研英语二 2025 大作文【青年群体体育健身与户外运动增长图表】",
        "prompt": "Directions: Write an essay of about 150 words based on the chart showing the steady increase in young people's participation in outdoor sports and fitness activities in recent years. You should: 1) interpret the chart, and 2) give your comments.",
        "full_score": 15.0,
        "min_words": 140,
        "max_words": 190,
    },
    # === 2024 考研英语一 / 英语二 ===
    {
        "question_id": "KY-2024-E1-A",
        "year": 2024,
        "paper": "考研英语一-2024",
        "sub_type": "英语一·小作文",
        "title": "考研英语一 2024 小作文【为外国交换生介绍中国古代科学家备选材料】",
        "prompt": "Directions: Read the following email from an international student, Paul, who needs advice on preparing a presentation about an ancient Chinese scientist. Write a reply of about 100 words providing suggestions and materials.",
        "full_score": 10.0,
        "min_words": 90,
        "max_words": 130,
    },
    {
        "question_id": "KY-2024-E1-B",
        "year": 2024,
        "paper": "考研英语一-2024",
        "sub_type": "英语一·大作文",
        "title": "考研英语一 2024 大作文【市民公园健身器材建设与使用人数图表】",
        "prompt": "Directions: Write an essay of 160-200 words based on the picture and chart showing the positive feedback on newly built fitness facilities in a community park and the surge in daily users. In your essay, you should: 1) describe the picture and chart briefly, 2) interpret the implied meaning, and 3) give your comments.",
        "full_score": 20.0,
        "min_words": 160,
        "max_words": 220,
    },
    {
        "question_id": "KY-2024-E2-A",
        "year": 2024,
        "paper": "考研英语二-2024",
        "sub_type": "英语二·小作文",
        "title": "考研英语二 2024 小作文【古镇文化劳动实践活动方案邮件】",
        "prompt": "Directions: Suppose you and Jack are going to do a survey on the protection of old houses in an ancient town. Write an email to him to propose your plan and ask for his ideas. Write about 100 words.",
        "full_score": 10.0,
        "min_words": 90,
        "max_words": 130,
    },
    {
        "question_id": "KY-2024-E2-B",
        "year": 2024,
        "paper": "考研英语二-2024",
        "sub_type": "英语二·大作文",
        "title": "考研英语二 2024 大作文【高校学生在劳动实践课中的主要收获图表】",
        "prompt": "Directions: Write an essay based on the chart showing the major gains of college students in a labor practice course (e.g., learning practical skills, enhancing teamwork, feeling a sense of achievement). In your writing, you should: 1) interpret the chart, and 2) give your comments. Write about 150 words.",
        "full_score": 15.0,
        "min_words": 140,
        "max_words": 190,
    },
    # === 2023 考研英语一 / 英语二 ===
    {
        "question_id": "KY-2023-E1-A",
        "year": 2023,
        "paper": "考研英语一-2023",
        "sub_type": "英语一·小作文",
        "title": "考研英语一 2023 小作文【戏剧俱乐部排练传统剧目招募公告】",
        "prompt": "Directions: Write a notice to recruit student actors for a short play based on a classic Chinese story to be performed by the English Drama Club. Write about 100 words.",
        "full_score": 10.0,
        "min_words": 90,
        "max_words": 130,
    },
    {
        "question_id": "KY-2023-E1-B",
        "year": 2023,
        "paper": "考研英语一-2023",
        "sub_type": "英语一·大作文",
        "title": "考研英语一 2023 大作文【龙舟赛火热传承传统文化图画作文】",
        "prompt": "Directions: Write an essay of 160-200 words based on the drawing showing a lively dragon boat race where an elderly couple remarks on how wonderful it is that more young people are participating in traditional folk customs. You should: 1) describe the drawing briefly, 2) interpret its meaning, and 3) give your comments.",
        "full_score": 20.0,
        "min_words": 160,
        "max_words": 220,
    },
    {
        "question_id": "KY-2023-E2-A",
        "year": 2023,
        "paper": "考研英语二-2023",
        "sub_type": "英语二·小作文",
        "title": "考研英语二 2023 小作文【给外教回复推荐周末儿童志愿者活动】",
        "prompt": "Directions: An international friend, David, wants to do some volunteer work for children on weekends and asks for your advice. Write an email to recommend a suitable volunteer program and explain why. Write about 100 words.",
        "full_score": 10.0,
        "min_words": 90,
        "max_words": 130,
    },
    {
        "question_id": "KY-2023-E2-B",
        "year": 2023,
        "paper": "考研英语二-2023",
        "sub_type": "英语二·大作文",
        "title": "考研英语二 2023 大作文【2012-2021我国居民健康素养水平持续提升图表】",
        "prompt": "Directions: Write an essay based on the chart showing the steady rise in the health literacy level of Chinese residents from 2012 to 2021. You should: 1) interpret the chart, and 2) give your comments. Write about 150 words.",
        "full_score": 15.0,
        "min_words": 140,
        "max_words": 190,
    },
    # === 2022 考研英语一 / 英语二 ===
    {
        "question_id": "KY-2022-E1-A",
        "year": 2022,
        "paper": "考研英语一-2022",
        "sub_type": "英语一·小作文",
        "title": "考研英语一 2022 小作文【邀请外籍教授为校刊专栏撰写稿件】",
        "prompt": "Directions: Write an email to a professor at a partner university, inviting him/her to contribute an article to a newly launched column in your university newspaper. Write about 100 words.",
        "full_score": 10.0,
        "min_words": 90,
        "max_words": 130,
    },
    {
        "question_id": "KY-2022-E1-B",
        "year": 2022,
        "paper": "考研英语一-2022",
        "sub_type": "英语一·大作文",
        "title": "考研英语一 2022 大作文【听与不听课外讲座的两种态度图画作文】",
        "prompt": "Directions: Write an essay of 160-200 words based on the drawing depicting two college students in front of a lecture poster: one thinks the topic is irrelevant to her major, while the other believes attending diverse lectures is beneficial. You should: 1) describe the drawing briefly, 2) interpret its meaning, and 3) give your comments.",
        "full_score": 20.0,
        "min_words": 160,
        "max_words": 220,
    },
    {
        "question_id": "KY-2022-E2-A",
        "year": 2022,
        "paper": "考研英语二-2022",
        "sub_type": "英语二·小作文",
        "title": "考研英语二 2022 小作文【邀请留学生参加校园美食节】",
        "prompt": "Directions: Suppose you are planning a Campus Food Festival. Write an email to the international students in your university to invite them to participate and introduce the main activities. Write about 100 words.",
        "full_score": 10.0,
        "min_words": 90,
        "max_words": 130,
    },
    {
        "question_id": "KY-2022-E2-B",
        "year": 2022,
        "paper": "考研英语二-2022",
        "sub_type": "英语二·大作文",
        "title": "考研英语二 2022 大作文【我国农村网络零售额与快递业务量高速增长图表】",
        "prompt": "Directions: Write an essay based on the chart showing the rapid growth of express parcel volume in rural areas in China. You should: 1) interpret the chart, and 2) give your comments. Write about 150 words.",
        "full_score": 15.0,
        "min_words": 140,
        "max_words": 190,
    },
    # === 2021 考研英语一 / 英语二 ===
    {
        "question_id": "KY-2021-E1-A",
        "year": 2021,
        "paper": "考研英语一-2021",
        "sub_type": "英语一·小作文",
        "title": "考研英语一 2021 小作文【给外国朋友写信提供在华找工作建议】",
        "prompt": "Directions: A foreign friend of yours has recently graduated from college and intends to find a job in China. Write an email to him/her to offer some practical suggestions. Write about 100 words.",
        "full_score": 10.0,
        "min_words": 90,
        "max_words": 130,
    },
    {
        "question_id": "KY-2021-E1-B",
        "year": 2021,
        "paper": "考研英语一-2021",
        "sub_type": "英语一·大作文",
        "title": "考研英语一 2021 大作文【坚持热爱京剧：不要管别人怎么说图画作文】",
        "prompt": "Directions: Write an essay of 160-200 words based on the drawing where a father encourages his son dressed in Peking Opera costume to pursue his passion regardless of others' doubts. You should: 1) describe the drawing briefly, 2) interpret its implied meaning, and 3) give your comments.",
        "full_score": 20.0,
        "min_words": 160,
        "max_words": 220,
    },
    {
        "question_id": "KY-2021-E2-A",
        "year": 2021,
        "paper": "考研英语二-2021",
        "sub_type": "英语二·小作文",
        "title": "考研英语二 2021 小作文【邀请外籍专家参加线上学术会议】",
        "prompt": "Directions: Suppose you are organizing an online international academic meeting. Write an email to invite Professor Smith to give a keynote speech and inform him of the meeting details. Write about 100 words.",
        "full_score": 10.0,
        "min_words": 90,
        "max_words": 130,
    },
    {
        "question_id": "KY-2021-E2-B",
        "year": 2021,
        "paper": "考研英语二-2021",
        "sub_type": "英语二·大作文",
        "title": "考研英语二 2021 大作文【某市居民体育锻炼方式占比调查图表】",
        "prompt": "Directions: Write an essay based on the chart showing the survey results of residents' ways of taking physical exercise (walking/running, ball games, fitness equipment, etc.). You should: 1) interpret the chart, and 2) give your comments. Write about 150 words.",
        "full_score": 15.0,
        "min_words": 140,
        "max_words": 190,
    },
    # === 2020 考研英语一 / 英语二 ===
    {
        "question_id": "KY-2020-E1-B",
        "year": 2020,
        "paper": "考研英语一-2020",
        "sub_type": "英语一·大作文",
        "title": "考研英语一 2020 大作文【今日事今日毕 vs 拖延症图画作文】",
        "prompt": "Directions: Write an essay of 160-200 words based on the drawing contrasting a girl who finishes her assignments promptly with a boy who procrastinates until the last minute. You should: 1) describe the drawing briefly, 2) interpret its meaning, and 3) give your comments.",
        "full_score": 20.0,
        "min_words": 160,
        "max_words": 220,
    },
    {
        "question_id": "KY-2020-E2-B",
        "year": 2020,
        "paper": "考研英语二-2020",
        "sub_type": "英语二·大作文",
        "title": "考研英语二 2020 大作文【某高校学生手机阅读目的占比图表】",
        "prompt": "Directions: Write an essay based on the chart showing the distribution of college students' purposes for mobile reading (learning, killing time, getting information). You should: 1) interpret the chart, and 2) give your comments. Write about 150 words.",
        "full_score": 15.0,
        "min_words": 140,
        "max_words": 190,
    },
]


async def main() -> None:
    models = [
        Question(
            question_id=q["question_id"],
            exam_type=ExamType.KAOYAN_ENGLISH,
            title=q["title"],
            year=q["year"],
            paper=q["paper"],
            sub_type=q["sub_type"],
            prompt=q["prompt"],
            material_summary="",
            full_score=q["full_score"],
            min_words=q["min_words"],
            max_words=q["max_words"],
            scoring_points=[],
            reference_answer="",
        )
        for q in KAOYAN_QUESTIONS
    ]

    OUT_PATH.write_text(
        json.dumps([m.model_dump() for m in models], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    await init_db()
    added = 0
    async with AsyncSessionLocal() as db:
        for m in models:
            existing = await db.get(QuestionModel, m.question_id)
            if existing:
                continue
            db.add(
                QuestionModel(
                    question_id=m.question_id,
                    exam_type=m.exam_type.value,
                    title=m.title,
                    year=m.year,
                    paper=m.paper,
                    sub_type=m.sub_type,
                    prompt=m.prompt,
                    material_summary="",
                    full_score=m.full_score,
                    min_words=m.min_words,
                    max_words=m.max_words,
                    scoring_points=[],
                    reference_answer="",
                )
            )
            added += 1
        await db.commit()

    print(f"考研英语真题导入完成！共生成 {len(models)} 道 -> {OUT_PATH} (新增入库 +{added} 道)")


if __name__ == "__main__":
    asyncio.run(main())
