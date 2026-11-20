"""
将单道真题的【标题 + 题目要求 + 完整给定材料】排版为标准 A4 印刷级 PDF，
方便考生直接打印纸质卷子，或转发至微信文件传输助手导入 iPad (GoodNotes/Notability) 勾画做题。
"""

import io
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

_FONT_REGISTERED: str | None = None


def _ensure_chinese_font() -> str:
    global _FONT_REGISTERED
    if _FONT_REGISTERED:
        return _FONT_REGISTERED

    # 优先使用系统清晰黑体/宋体（Windows 微软雅黑/宋体，Linux Noto/SimSun），兜底内置 STSong-Light
    candidates = [
        ("CNFont", r"C:\Windows\Fonts\msyh.ttc", 0),
        ("CNFont", r"C:\Windows\Fonts\simsun.ttc", 0),
        ("CNFont", r"C:\Windows\Fonts\simhei.ttf", None),
        ("CNFont", "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc", 0),
        ("CNFont", "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", 0),
    ]
    for name, path, sub_idx in candidates:
        if Path(path).exists():
            try:
                if sub_idx is not None:
                    pdfmetrics.registerFont(TTFont(name, path, subfontIndex=sub_idx))
                else:
                    pdfmetrics.registerFont(TTFont(name, path))
                _FONT_REGISTERED = name
                return name
            except Exception:
                continue

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    _FONT_REGISTERED = "STSong-Light"
    return _FONT_REGISTERED


def build_question_pdf(
    title: str,
    prompt: str,
    material: str,
    word_limit_text: str = "",
) -> bytes:
    """生成适合纸质打印与 iPad 勾画的宽行距 A4 试卷 PDF 字节流"""
    font_name = _ensure_chinese_font()
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=title,
    )

    title_style = ParagraphStyle(
        "TitleCN",
        fontName=font_name,
        fontSize=15,
        leading=22,
        spaceAfter=8,
    )
    meta_style = ParagraphStyle(
        "MetaCN",
        fontName=font_name,
        fontSize=9.5,
        leading=14,
        textColor="#4B5563",
        spaceAfter=10,
    )
    h2_style = ParagraphStyle(
        "H2CN",
        fontName=font_name,
        fontSize=12,
        leading=18,
        spaceBefore=10,
        spaceAfter=6,
    )
    body_style = ParagraphStyle(
        "BodyCN",
        fontName=font_name,
        fontSize=10.5,
        leading=19,  # 宽松行距，方便纸质或 iPad 用笔勾画批注
        firstLineIndent=0,
        spaceAfter=6,
    )

    story = [
        Paragraph(escape(title), title_style),
        Paragraph(
            escape(
                f"知行岛申论精批真题卷 ｜ {word_limit_text or '按题干要求作答'} ｜ 写完拍照上传小程序即可获逐句红笔精批"
            ),
            meta_style,
        ),
        Paragraph("【作答要求】", h2_style),
    ]

    for line in (prompt or "").splitlines():
        s = line.strip()
        if s:
            story.append(Paragraph(escape(s), body_style))

    if material and material.strip():
        story.append(Spacer(1, 6))
        story.append(Paragraph("【给定材料】", h2_style))
        for para in material.splitlines():
            p = para.strip()
            if p:
                story.append(Paragraph(escape(p), body_style))

    def draw_footer(canvas, doc_obj):
        canvas.saveState()
        canvas.setFont(font_name, 8.5)
        canvas.setFillColorRGB(0.45, 0.48, 0.55)
        canvas.drawCentredString(
            A4[0] / 2,
            10 * mm,
            f"第 {doc_obj.page} 页  ·  知行岛申论精批真题卷（可打印或导入 iPad 勾画）",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    return buf.getvalue()
