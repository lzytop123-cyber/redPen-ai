import html
from pathlib import Path

from app.schemas import ExamType, GradingReport

ISSUE_LABEL_MAP = {
    "grammar": "语法/拼写",
    "expression": "表达规范",
    "missing_point": "漏采分点",
    "logic": "逻辑问题",
    "redundancy": "啰嗦超字",
    "highlight": "亮点表扬",
}


def render_html_report(report: GradingReport, output_path: str | Path) -> Path:
    """将批改报告渲染为红笔阅卷级可视化 HTML（方便直观预览，也方便直接给自习室学员看）"""
    ann_by_sid: dict[str, list] = {}
    for ann in report.annotations:
        ann_by_sid.setdefault(ann.sentence_id, []).append(ann)

    # 1. 采分点或维度详情 HTML
    detail_html = ""
    if report.exam_type == ExamType.SHENLUN_SHORT and report.shenlun_detail:
        rows = []
        status_badge = {
            "hit": '<span class="badge hit">命中</span>',
            "partial": '<span class="badge partial">部分命中</span>',
            "miss": '<span class="badge miss">未命中</span>',
        }
        for m in report.shenlun_detail.point_matches:
            rows.append(
                f"<tr><td><b>{html.escape(m.point_id)}</b></td>"
                f"<td>{status_badge.get(m.status, m.status)}</td>"
                f"<td>{html.escape(m.evidence_quote or '—')}</td>"
                f"<td>{html.escape(m.comment)}</td></tr>"
            )
        detail_html = f"""
        <section class="card">
          <h2>一、标准采分点核对明细</h2>
          <table>
            <thead><tr><th>编号</th><th>判定</th><th>原文依据</th><th>考官点评</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
          <p class="sub-note"><b>条理与规范评价：</b>{html.escape(report.shenlun_detail.structure_comment)}</p>
        </section>
        """
    elif report.exam_type == ExamType.SHENLUN_ESSAY and report.shenlun_essay_detail:
        rows = []
        for d in report.shenlun_essay_detail.dimensions:
            rows.append(
                f"<tr><td><b>{html.escape(d.dimension)}</b></td>"
                f"<td>第 {d.level} 档 / 5 档（权重 {int(d.weight*100)}%）</td>"
                f"<td>{html.escape(d.comment)}</td></tr>"
            )
        detail_html = f"""
        <section class="card">
          <h2>一、申论大作文四维量表核对</h2>
          <table>
            <thead><tr><th>评分维度</th><th>定档</th><th>考官点评</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
          <p class="sub-note"><b>立意判定：</b>{html.escape(report.shenlun_essay_detail.thesis_accuracy)} ｜ <b>结合材料：</b>{html.escape(report.shenlun_essay_detail.material_usage)} ｜ <b>总评：</b>{html.escape(report.shenlun_essay_detail.overall_comment)}</p>
        </section>
        """
    elif report.kaoyan_detail:
        rows = []
        for d in report.kaoyan_detail.dimensions:
            rows.append(
                f"<tr><td><b>{html.escape(d.dimension)}</b></td>"
                f"<td>第 {d.level} 档 / 5 档（权重 {int(d.weight*100)}%）</td>"
                f"<td>{html.escape(d.comment)}</td></tr>"
            )
        detail_html = f"""
        <section class="card">
          <h2>一、考研官方五档维度核对</h2>
          <table>
            <thead><tr><th>评分维度</th><th>定档</th><th>考官点评</th></tr></thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
          <p class="sub-note"><b>模板痕迹风险：</b>{html.escape(report.kaoyan_detail.template_risk.upper())} ｜ <b>总评：</b>{html.escape(report.kaoyan_detail.overall_comment)}</p>
        </section>
        """

    # 2. 逐句红笔批注 HTML
    sentence_blocks = []
    for s in report.sentences:
        anns = ann_by_sid.get(s.sentence_id, [])
        if not anns:
            sentence_blocks.append(
                f'<div class="sent"><span class="sid">{s.sentence_id}</span>{html.escape(s.text)}</div>'
            )
        else:
            has_issue = any(a.severity != "positive" for a in anns)
            cls = "sent has-issue" if has_issue else "sent has-highlight"
            notes = []
            for a in anns:
                label = ISSUE_LABEL_MAP.get(a.issue_type, a.issue_type)
                tag_cls = "tag-good" if a.severity == "positive" else "tag-red"
                notes.append(
                    f'<div class="note">'
                    f'<span class="{tag_cls}">{label}</span> '
                    f'<span>{html.escape(a.comment)}</span>'
                    f'<div class="suggest">建议改写：{html.escape(a.suggestion)}</div>'
                    f'</div>'
                )
            sentence_blocks.append(
                f'<div class="{cls}"><span class="sid">{s.sentence_id}</span>'
                f'<span class="stext">{html.escape(s.text)}</span>'
                f'{"".join(notes)}</div>'
            )

    tags_html = "".join(
        f'<span class="wtag">#{html.escape(t)}</span>' for t in report.weakness_tags
    )
    improvements_html = "".join(
        f"<li>{html.escape(item)}</li>" for item in report.key_improvements
    )
    warning_html = (
        f'<div class="warn">⚠️ {html.escape(report.word_count_warning)}</div>'
        if report.word_count_warning
        else ""
    )

    page = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8" />
  <title>AI 精批报告 - {html.escape(report.question_title)}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Microsoft YaHei", sans-serif; background: #f5f7fa; color: #1f2937; margin: 0; padding: 24px; }}
    .wrap {{ max-width: 900px; margin: 0 auto; }}
    .hero {{ background: linear-gradient(135deg, #1e3a8a, #2563eb); color: #fff; border-radius: 14px; padding: 24px 28px; display: flex; justify-content: space-between; align-items: center; }}
    .score-box {{ text-align: right; }}
    .score {{ font-size: 42px; font-weight: 800; line-height: 1; }}
    .band {{ font-size: 14px; opacity: 0.9; margin-top: 6px; }}
    .card {{ background: #fff; border-radius: 12px; padding: 20px 24px; margin-top: 18px; box-shadow: 0 2px 10px rgba(0,0,0,0.04); }}
    h2 {{ margin: 0 0 14px; font-size: 18px; border-left: 4px solid #2563eb; padding-left: 10px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 14px; }}
    th, td {{ border-bottom: 1px solid #e5e7eb; padding: 10px 8px; text-align: left; vertical-align: top; }}
    th {{ background: #f9fafb; color: #4b5563; }}
    .badge {{ display: inline-block; padding: 2px 8px; border-radius: 99px; font-size: 12px; font-weight: 600; }}
    .hit {{ background: #dcfce7; color: #166534; }}
    .partial {{ background: #fef3c7; color: #92400e; }}
    .miss {{ background: #fee2e2; color: #991b1b; }}
    .warn {{ background: #fff7ed; border: 1px solid #fdba74; color: #c2410c; padding: 10px 14px; border-radius: 8px; margin-top: 14px; font-size: 14px; }}
    .sent {{ padding: 10px 12px; margin-bottom: 10px; border-radius: 8px; background: #f9fafb; line-height: 1.7; }}
    .sent.has-issue {{ background: #fff5f5; border-left: 4px solid #ef4444; }}
    .sent.has-highlight {{ background: #f0fdf4; border-left: 4px solid #22c55e; }}
    .sid {{ display: inline-block; font-size: 12px; font-weight: 700; color: #6b7280; margin-right: 8px; }}
    .note {{ margin-top: 8px; padding: 8px 10px; background: #fff; border-radius: 6px; font-size: 13px; border: 1px dashed #fca5a5; }}
    .tag-red {{ background: #ef4444; color: #fff; padding: 1px 6px; border-radius: 4px; font-size: 12px; margin-right: 6px; }}
    .tag-good {{ background: #22c55e; color: #fff; padding: 1px 6px; border-radius: 4px; font-size: 12px; margin-right: 6px; }}
    .suggest {{ color: #1d4ed8; margin-top: 4px; font-weight: 500; }}
    .upgrade {{ white-space: pre-wrap; background: #f0f9ff; border: 1px solid #bae6fd; padding: 16px; border-radius: 8px; line-height: 1.85; font-size: 15px; }}
    .wtag {{ display: inline-block; background: #eef2ff; color: #3730a3; padding: 3px 10px; border-radius: 99px; font-size: 12px; margin-right: 6px; margin-top: 8px; }}
    .sub-note {{ font-size: 14px; color: #374151; margin-top: 12px; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div>
        <div style="font-size:13px;opacity:.85;">AI 主观题精批报告 · {html.escape(report.exam_type.value)}</div>
        <h1 style="margin:6px 0 8px;font-size:22px;">{html.escape(report.question_title)}</h1>
        <div style="font-size:13px;opacity:.9;">统计字数：{report.word_count} ｜ 薄弱项：{tags_html or '无'}</div>
      </div>
      <div class="score-box">
        <div class="score">{report.final_score} <span style="font-size:18px;font-weight:400;">/ {report.full_score}</span></div>
        <div class="band">{html.escape(report.band_label)}</div>
      </div>
    </div>

    {warning_html}
    {detail_html}

    <section class="card">
      <h2>二、逐句红笔批注</h2>
      {''.join(sentence_blocks)}
    </section>

    <section class="card">
      <h2>三、同思路高分升格版</h2>
      <div class="upgrade">{html.escape(report.upgraded_answer)}</div>
      <h3 style="font-size:15px;margin:16px 0 8px;">核心提分改动说明：</h3>
      <ul style="line-height:1.8;font-size:14px;">{improvements_html}</ul>
    </section>
  </div>
</body>
</html>
"""
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(page, encoding="utf-8")
    return out
