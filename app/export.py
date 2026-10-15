"""Exportación a PDF (para Goodnotes/iPad) y HTML, con la identidad visual de cada asignatura.

El PDF se genera con reportlab a partir del Markdown, sin servicios externos.
"""
from __future__ import annotations

import html
import re
from datetime import datetime
from pathlib import Path

import markdown as md_lib
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle, Preformatted)

from .config import Subject

FONT_DIR = Path(__file__).parent / "fonts"
_FONTS_READY = False
BASE, BOLD, ITALIC, BOLDITALIC = "Helvetica", "Helvetica-Bold", "Helvetica-Oblique", "Helvetica-BoldOblique"


def _register_fonts() -> None:
    global _FONTS_READY, BASE, BOLD, ITALIC, BOLDITALIC
    if _FONTS_READY:
        return
    try:
        pdfmetrics.registerFont(TTFont("DejaVu", str(FONT_DIR / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(FONT_DIR / "DejaVuSans-Bold.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu-Oblique", str(FONT_DIR / "DejaVuSans-Oblique.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu-BoldOblique", str(FONT_DIR / "DejaVuSans-BoldOblique.ttf")))
        from reportlab.pdfbase.pdfmetrics import registerFontFamily
        registerFontFamily("DejaVu", normal="DejaVu", bold="DejaVu-Bold", italic="DejaVu-Oblique", boldItalic="DejaVu-BoldOblique")
        BASE, BOLD, ITALIC, BOLDITALIC = "DejaVu", "DejaVu-Bold", "DejaVu-Oblique", "DejaVu-BoldOblique"
    except Exception:
        pass  # se usa Helvetica
    _FONTS_READY = True


# ---------------------------------------------------------------- Markdown -> bloques

def parse_blocks(text: str) -> list[tuple]:
    """Divide el Markdown en bloques simples: (tipo, contenido...)."""
    lines = text.replace("\r\n", "\n").split("\n")
    blocks, i = [], 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if not s:
            i += 1
            continue
        if s.startswith("```"):
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            blocks.append(("code", "\n".join(code)))
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            blocks.append(("h", len(m.group(1)), m.group(2).strip()))
            i += 1
            continue
        if re.match(r"^(-{3,}|\*{3,})$", s):
            blocks.append(("hr",))
            i += 1
            continue
        if s.startswith(">"):
            paras, cur = [], []
            while i < len(lines) and lines[i].strip().startswith(">"):
                content = lines[i].strip()[1:].strip()
                if content:
                    cur.append(content)
                elif cur:
                    paras.append(" ".join(cur))
                    cur = []
                i += 1
            if cur:
                paras.append(" ".join(cur))
            blocks.append(("quote", paras))
            continue
        if s.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip().strip("|")
                cells = [c.strip() for c in re.split(r"(?<!\\)\|", row)]
                if not all(re.match(r"^:?-{2,}:?$", c) for c in cells if c):
                    rows.append([c.replace("\\|", "|") for c in cells])
                i += 1
            blocks.append(("table", rows))
            continue
        lm = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)
        if lm:
            items = []
            while i < len(lines):
                lm = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", lines[i])
                if lm:
                    indent = len(lm.group(1).replace("\t", "    "))
                    items.append([indent // 2 if indent < 4 else indent // 4, lm.group(2), lm.group(3)])
                    i += 1
                elif lines[i].strip() and lines[i].startswith("  ") and items:
                    items[-1][2] += " " + lines[i].strip()
                    i += 1
                else:
                    break
            blocks.append(("list", items))
            continue
        para = [s]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(r"^\s*(#{1,4}\s|>|\||[-*+]\s|\d+[.)]\s|```)", lines[i]):
            para.append(lines[i].strip())
            i += 1
        blocks.append(("p", " ".join(para)))
    return blocks


def inline(text: str) -> str:
    """Markdown en línea -> mini-HTML que entiende reportlab."""
    t = text.replace("\\*", "\x00")
    t = html.escape(t, quote=False)
    t = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", t)
    t = re.sub(r"`([^`]+)`", r'<font face="Courier">\1</font>', t)
    t = re.sub(r"\*\*\*(.+?)\*\*\*", r"<b><i>\1</i></b>", t)
    t = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", t)
    t = re.sub(r"(?<![\w*])\*(?!\s)(.+?)(?<!\s)\*(?![\w*])", r"<i>\1</i>", t)
    t = re.sub(r"(?<![\w])_(?!\s)(.+?)(?<!\s)_(?![\w])", r"<i>\1</i>", t)
    return t.replace("\x00", "*")


# ---------------------------------------------------------------- PDF

def _styles(subject: Subject) -> dict:
    d = subject.design
    primary, accent, text = colors.HexColor(d["primary"]), colors.HexColor(d["accent"]), colors.HexColor(d["text"])
    base = dict(fontName=BASE, textColor=text, fontSize=10.5, leading=15.5, alignment=TA_LEFT)
    return {
        "title": ParagraphStyle("title", **{**base, "fontName": BOLD, "fontSize": 22, "leading": 27, "textColor": primary, "spaceAfter": 4}),
        "meta": ParagraphStyle("meta", **{**base, "fontSize": 8.5, "leading": 12, "textColor": colors.HexColor("#6B7280"), "spaceAfter": 10}),
        "h2": ParagraphStyle("h2", **{**base, "fontName": BOLD, "fontSize": 15, "leading": 19, "textColor": primary, "spaceBefore": 16, "spaceAfter": 3}),
        "h3": ParagraphStyle("h3", **{**base, "fontName": BOLD, "fontSize": 12, "leading": 16, "textColor": accent, "spaceBefore": 10, "spaceAfter": 4}),
        "h4": ParagraphStyle("h4", **{**base, "fontName": BOLD, "fontSize": 10.5, "spaceBefore": 6, "spaceAfter": 2}),
        "p": ParagraphStyle("p", **{**base, "spaceAfter": 6}),
        "li": ParagraphStyle("li", **{**base, "spaceAfter": 2.5}),
        "quote": ParagraphStyle("quote", **{**base, "fontSize": 10.5, "leading": 16}),
        "cell": ParagraphStyle("cell", **{**base, "fontSize": 9.2, "leading": 12.5}),
        "cellh": ParagraphStyle("cellh", **{**base, "fontName": BOLD, "fontSize": 9.2, "leading": 12.5, "textColor": colors.white}),
        "code": ParagraphStyle("code", **{**base, "fontName": "Courier", "fontSize": 9, "leading": 12}),
    }


def _table(rows: list[list[str]], st: dict, subject: Subject, width: float) -> Table:
    d = subject.design
    ncols = max(len(r) for r in rows)
    rows = [r + [""] * (ncols - len(r)) for r in rows]
    plain = [[re.sub(r"[*`_]", "", c) for c in r] for r in rows]
    lengths = [max(len(r[c]) for r in plain) for c in range(ncols)]
    # Ancho mínimo: que quepa la palabra más larga de la columna sin partirla
    min_w = [max((pdfmetrics.stringWidth(w, BOLD, 9.2) for r in plain for w in r[c].split()), default=20) + 14
             for c in range(ncols)]
    weights = [min(max(l, 8), 70) for l in lengths]
    col_w = [width * w / sum(weights) for w in weights]
    deficit = sum(max(0, m - w) for m, w in zip(min_w, col_w))
    if deficit:
        col_w = [max(w, m) for w, m in zip(col_w, min_w)]
        flexible = [i for i in range(ncols) if col_w[i] > min_w[i]]
        spare = sum(col_w[i] - min_w[i] for i in flexible)
        if spare > 0:
            excess = sum(col_w) - width
            for i in flexible:
                col_w[i] -= excess * (col_w[i] - min_w[i]) / spare
    data = [[Paragraph(inline(c), st["cellh"] if ri == 0 else st["cell"]) for c in r] for ri, r in enumerate(rows)]
    t = Table(data, colWidths=col_w, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(d["primary"])),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, colors.HexColor("#D5D9DE")),
    ]
    for ri in range(1, len(rows)):
        if ri % 2 == 0:
            style.append(("BACKGROUND", (0, ri), (-1, ri), colors.HexColor(d["soft"])))
    t.setStyle(TableStyle(style))
    return t


def _quote(paras: list[str], st: dict, subject: Subject, width: float) -> Table:
    d = subject.design
    content = [Paragraph(inline(p), st["quote"]) for p in paras]
    t = Table([[content]], colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(d["soft"])),
        ("LINEBEFORE", (0, 0), (0, -1), 3, colors.HexColor(d["accent"])),
        ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return t


def markdown_to_pdf(markdown_text: str, out_path: Path, subject: Subject, meta: dict) -> Path:
    _register_fonts()
    st = _styles(subject)
    d = subject.design
    left, right = 2.0 * cm, 2.6 * cm  # margen derecho más ancho para anotar en Goodnotes
    width = A4[0] - left - right
    story = []
    blocks = parse_blocks(markdown_text)

    if blocks and blocks[0][0] == "h" and blocks[0][1] == 1:
        story.append(Paragraph(inline(blocks[0][2]), st["title"]))
        blocks = blocks[1:]
    meta_line = f"{subject.name} · {meta.get('kind_label', '')} · versión {meta.get('version', 1)} · " \
                f"{datetime.now().strftime('%d/%m/%Y')} · Fuente: {html.escape(meta.get('source_filename', '—'))}"
    story.append(Paragraph(meta_line, st["meta"]))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor(d["primary"]), spaceAfter=8))

    for b in blocks:
        kind = b[0]
        if kind == "h":
            level, txt = b[1], b[2]
            if level <= 2:
                story.append(KeepTogether([Paragraph(inline(txt), st["h2"]),
                                           HRFlowable(width="100%", thickness=0.8, color=colors.HexColor(d["accent"]), spaceAfter=5)]))
            else:
                story.append(Paragraph(inline(txt), st["h3" if level == 3 else "h4"]))
        elif kind == "p":
            story.append(Paragraph(inline(b[1]), st["p"]))
        elif kind == "list":
            counters: dict[int, int] = {}
            for level, marker, txt in b[1]:
                if marker[0].isdigit():
                    counters[level] = counters.get(level, 0) + 1
                    bullet = f"{counters[level]}."
                else:
                    bullet = "•" if level == 0 else "–"
                ps = ParagraphStyle(f"li{level}", parent=st["li"], leftIndent=14 + 14 * level, bulletIndent=2 + 14 * level)
                story.append(Paragraph(inline(txt), ps, bulletText=bullet))
            story.append(Spacer(1, 4))
        elif kind == "table" and b[1]:
            story.append(Spacer(1, 3))
            story.append(_table(b[1], st, subject, width))
            story.append(Spacer(1, 8))
        elif kind == "quote":
            story.append(Spacer(1, 3))
            story.append(_quote(b[1], st, subject, width))
            story.append(Spacer(1, 8))
        elif kind == "code":
            story.append(Preformatted(b[1], st["code"]))
        elif kind == "hr":
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#C9CED4"), spaceBefore=6, spaceAfter=6))

    topic = meta.get("topic", "")

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(colors.HexColor(d["primary"]))
        canvas.rect(0, A4[1] - 0.9 * cm, A4[0], 0.9 * cm, fill=1, stroke=0)
        canvas.setFillColor(colors.white)
        canvas.setFont(BOLD, 9)
        canvas.drawString(left, A4[1] - 0.58 * cm, subject.name.upper())
        canvas.setFont(BASE, 9)
        canvas.drawRightString(A4[0] - right, A4[1] - 0.58 * cm, topic[:70])
        canvas.setFillColor(colors.HexColor("#8A9099"))
        canvas.setFont(BASE, 8)
        canvas.drawString(left, 1.0 * cm, f"{meta.get('kind_label', '')} · v{meta.get('version', 1)}")
        canvas.drawRightString(A4[0] - right, 1.0 * cm, f"{doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(str(out_path), pagesize=A4, leftMargin=left, rightMargin=right,
                            topMargin=1.9 * cm, bottomMargin=1.8 * cm,
                            title=topic, author="Sistema de Estudio", subject=subject.name)
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return out_path


# ---------------------------------------------------------------- HTML

def markdown_to_html(markdown_text: str, subject: Subject, meta: dict) -> str:
    d = subject.design
    body = md_lib.markdown(markdown_text, extensions=["tables", "sane_lists"])
    return f"""<!doctype html>
<html lang="{subject.language}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(meta.get('topic', 'Apuntes'))}</title>
<style>
:root {{ --primary:{d['primary']}; --accent:{d['accent']}; --soft:{d['soft']}; --bg:{d['background']}; --text:{d['text']}; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:16px/1.6 -apple-system, "Segoe UI", system-ui, sans-serif; }}
header {{ background:var(--primary); color:#fff; padding:10px 24px; font-size:13px; letter-spacing:.04em; display:flex; justify-content:space-between; }}
main {{ max-width:820px; margin:0 auto; padding:24px 20px 60px; }}
h1 {{ color:var(--primary); font-size:30px; line-height:1.2; margin:.4em 0 .1em; }}
h2 {{ color:var(--primary); border-bottom:2px solid var(--accent); padding-bottom:4px; margin-top:2em; }}
h3 {{ color:var(--accent); }}
table {{ border-collapse:collapse; width:100%; margin:12px 0; font-size:14.5px; display:block; overflow-x:auto; }}
th {{ background:var(--primary); color:#fff; text-align:left; padding:7px 9px; }}
td {{ padding:7px 9px; border-bottom:1px solid #dde1e5; vertical-align:top; }}
tr:nth-child(even) td {{ background:var(--soft); }}
blockquote {{ background:var(--soft); border-left:4px solid var(--accent); margin:14px 0; padding:10px 16px; }}
.meta {{ color:#6b7280; font-size:13px; }}
</style></head><body>
<header><span>{html.escape(subject.name.upper())}</span><span>{html.escape(meta.get('kind_label', ''))} · v{meta.get('version', 1)}</span></header>
<main><p class="meta">Fuente: {html.escape(meta.get('source_filename', '—'))}</p>{body}</main></body></html>"""
