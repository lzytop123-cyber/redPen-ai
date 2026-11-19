import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from app.html_renderer import render_html_report
from app.pipeline import GradingPipeline
from app.schemas import ExamType, GradingReport, Question

console = Console()

SAMPLE_ANSWERS = {
    ExamType.SHENLUN_SHORT: (
        "第一，老旧小区的地下管道很旧了，而且小区里面停车位特别少，老人上下楼也不方便。\n"
        "第二，小区改完以后物业管得不好，大家平时也不太管小区的公共事务，业委会一直建不起来。\n"
        "第三，有些地方改造就是刷刷墙搞面子工程，没有真正问问老人和小孩需要什么。"
    ),
    ExamType.KAOYAN_ENGLISH: (
        "From the chart we can see that more and more young people go to museums and traditional workshops in recent years. "
        "This is a very good phenomenon, it shows young people like traditional culture very much.\n"
        "There are two reasons for this. First, technology make traditional culture more interesting and easy to see on phone. "
        "Second, young people become more confident about our own culture and want to learn history.\n"
        "In my opinion, we should support this trend because traditional culture is very important for our country."
    ),
}


def load_all_questions() -> list[Question]:
    questions: list[Question] = []
    for path in [Path("data/shenlun_questions.json"), Path("data/sample_questions.json")]:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            questions.extend(Question.model_validate(item) for item in data)
    return questions


def load_question(exam: str, qid: str | None = None) -> Question:
    all_q = load_all_questions()
    if qid:
        for q in all_q:
            if q.question_id == qid:
                return q
        raise ValueError(f"未找到真题 ID: {qid}（可运行 --list 查看可用真题）")

    target = ExamType.SHENLUN_SHORT if exam == "shenlun" else ExamType.KAOYAN_ENGLISH
    for q in all_q:
        if q.exam_type == target:
            return q
    raise ValueError(f"未找到示例真题: {exam}")


def print_console_report(report: GradingReport) -> None:
    console.print()
    console.print(
        Panel(
            f"[bold cyan]{report.question_title}[/bold cyan]\n"
            f"预估得分：[bold green]{report.final_score} / {report.full_score}[/bold green]  "
            f"档位：[bold yellow]{report.band_label}[/bold yellow]  "
            f"统计字数：{report.word_count}",
            title="AI 主观题精批报告",
            expand=False,
        )
    )
    if report.word_count_warning:
        console.print(f"[bold red]⚠️ {report.word_count_warning}[/bold red]")

    if report.shenlun_detail:
        table = Table(title="一、标准采分点核对明细")
        table.add_column("编号", style="cyan")
        table.add_column("判定", style="bold")
        table.add_column("考官点评")
        for m in report.shenlun_detail.point_matches:
            color = {"hit": "green", "partial": "yellow", "miss": "red"}[m.status]
            table.add_row(m.point_id, f"[{color}]{m.status.upper()}[/{color}]", m.comment)
        console.print(table)

    if report.kaoyan_detail:
        table = Table(title="一、考研官方五档维度核对")
        table.add_column("维度", style="cyan")
        table.add_column("定档", style="bold yellow")
        table.add_column("点评")
        for d in report.kaoyan_detail.dimensions:
            table.add_row(d.dimension, f"第 {d.level} 档", d.comment)
        console.print(table)

    console.print("\n[bold red]二、逐句红笔批注：[/bold red]")
    for a in report.annotations:
        console.print(
            f"  • [{a.sentence_id}] ({a.issue_type}) {a.comment}\n"
            f"    [blue]建议改写：{a.suggestion}[/blue]"
        )

    console.print("\n[bold green]三、同思路高分升格版：[/bold green]")
    console.print(Panel(report.upgraded_answer, border_style="green"))


async def main() -> None:
    parser = argparse.ArgumentParser(description="主观题 AI 精批核心引擎本地测试脚本")
    parser.add_argument(
        "--exam",
        choices=["shenlun", "english"],
        default="shenlun",
        help="测试题型：shenlun（考公申论小题）或 english（考研英语作文）",
    )
    parser.add_argument("--qid", type=str, help="指定真题 ID（如 GK-2024-fs-S01），优先于 --exam")
    parser.add_argument("--list", action="store_true", help="列出最新 20 道已导入的申论真题 ID 与标题")
    parser.add_argument("--mock", action="store_true", help="开启零费用 Mock 模式验证全流程与报告渲染")
    parser.add_argument("--answer-file", type=str, help="自定义考生文本答卷路径（.txt）")
    parser.add_argument("--image", type=str, help="手写答卷照片路径（.jpg/.png，需配置视觉模型 Key）")
    args = parser.parse_args()

    if args.list:
        qs = load_all_questions()[:20]
        table = Table(title="最新 20 道已导入真题（完整题库共 287+ 道）")
        table.add_column("真题 ID", style="cyan")
        table.add_column("类型", style="yellow")
        table.add_column("满分")
        table.add_column("采分点数")
        table.add_column("标题")
        for q in qs:
            table.add_row(
                q.question_id,
                q.exam_type.value,
                str(q.full_score),
                str(len(q.scoring_points)) if q.scoring_points else "量表",
                q.title,
            )
        console.print(table)
        return

    question = load_question(args.exam, args.qid)

    student_answer = None
    if args.answer_file:
        student_answer = Path(args.answer_file).read_text(encoding="utf-8")
    elif not args.image:
        student_answer = SAMPLE_ANSWERS[question.exam_type]

    pipeline = GradingPipeline()
    report = await pipeline.run(
        question=question,
        student_answer=student_answer,
        image_path=args.image,
        mock=args.mock,
        on_progress=lambda msg: console.print(f"[dim]▶ {msg}[/dim]"),
    )

    print_console_report(report)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)
    json_path = out_dir / f"report_{args.exam}_{ts}.json"
    html_path = out_dir / f"report_{args.exam}_{ts}.html"

    json_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    render_html_report(report, html_path)

    console.print(f"\n[bold]已生成结构化 JSON：[/bold]{json_path.resolve()}")
    console.print(f"[bold]已生成红笔可视化 HTML 报告（可直接浏览器打开）：[/bold]{html_path.resolve()}")


if __name__ == "__main__":
    asyncio.run(main())
