"""
hujjat_utils.py — Hujjat & Dizayn xizmatlari
1. Rezyume / CV     — DOCX
2. Motivatsion xat  — DOCX
3. Jadval           — Excel (.xlsx)
4. Kontsept xarita  — PNG (matplotlib)

Optimizatsiyalangan: qisqa prompt, 1 ta so'rov, 5-10 soniya.
"""
import os
import json
import logging
import asyncio
from io import BytesIO
from openai import OpenAI
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

logger = logging.getLogger(__name__)

def get_client():
    return OpenAI()

# ─────────────────────────────────────────────
# Narxlar
# ─────────────────────────────────────────────
HUJJAT_PRICES = {
    "rezyume":    3000,
    "motivatsion": 2000,
    "jadval":     2000,
    "mindmap":    2000,
}

LANG_PROMPTS = {
    "uz": "O'zbek tilida yoz.",
    "ru": "Пиши на русском.",
    "en": "Write in English.",
    "ko": "한국어로 작성하세요.",
    "zh": "用中文写。",
    "de": "Schreibe auf Deutsch.",
}
LANG_LABELS = {
    "uz": "O'zbek", "ru": "Rus", "en": "Ingliz",
    "ko": "Kores", "zh": "Xitoy", "de": "Nemis",
}

# ═══════════════════════════════════════════════
# 1. REZYUME / CV
# ═══════════════════════════════════════════════
def _generate_cv_content(name: str, profession: str, lang: str, extra: str = "") -> dict:
    """Optimizatsiyalangan CV kontent — 1 so'rov, qisqa prompt."""
    lang_inst = LANG_PROMPTS.get(lang, LANG_PROMPTS["uz"])
    client = get_client()
    prompt = (
        f"{lang_inst} Professional CV yoz. "
        f"Ism: {name}. Kasb: {profession}. "
        f"{('Qoshimcha: ' + extra) if extra else ''} "
        f"JSON: {{\"objective\": \"...\", \"skills\": [\"...\"], "
        f"\"experience\": [{{\"title\":\"...\",\"company\":\"...\",\"period\":\"...\",\"desc\":\"...\"}}], "
        f"\"education\": [{{\"degree\":\"...\",\"school\":\"...\",\"year\":\"...\"}}], "
        f"\"languages\": [\"...\"], \"contacts\": {{\"email\":\"...\",\"phone\":\"...\",\"linkedin\":\"...\"}} }}"
    )
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1800,
        temperature=0.6,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def _build_cv_docx(data: dict, name: str, profession: str, lang: str) -> BytesIO:
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21); sec.page_height = Cm(29.7)
    sec.left_margin = Cm(2.5); sec.right_margin = Cm(2.0)
    sec.top_margin = Cm(2.0); sec.bottom_margin = Cm(2.0)

    def add_run(para, text, bold=False, size=12, color=None, italic=False):
        r = para.add_run(text)
        r.bold = bold; r.italic = italic
        r.font.name = "Arial"; r.font.size = Pt(size)
        if color: r.font.color.rgb = color

    def section_title(title):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(4)
        add_run(p, title.upper(), bold=True, size=11, color=RGBColor(0x1A, 0x73, 0xE8))
        pPr = p._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        b = OxmlElement('w:bottom')
        b.set(qn('w:val'), 'single'); b.set(qn('w:sz'), '4')
        b.set(qn('w:space'), '1'); b.set(qn('w:color'), '1A73E8')
        pBdr.append(b); pPr.append(pBdr)

    # Header
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(h, name.upper(), bold=True, size=20, color=RGBColor(0x1A, 0x1A, 0x6E))
    h.paragraph_format.space_after = Pt(2)

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(p2, profession, size=13, color=RGBColor(0x1A, 0x73, 0xE8), italic=True)
    p2.paragraph_format.space_after = Pt(8)

    # Contacts
    contacts = data.get("contacts", {})
    if contacts:
        cp = doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        contact_str = "  |  ".join(filter(None, [
            contacts.get("email", ""), contacts.get("phone", ""), contacts.get("linkedin", "")
        ]))
        add_run(cp, contact_str, size=9, color=RGBColor(0x55, 0x55, 0x55))
        cp.paragraph_format.space_after = Pt(10)

    # Objective
    obj = data.get("objective", "")
    if obj:
        section_title("Maqsad" if lang == "uz" else "Objective")
        op = doc.add_paragraph()
        add_run(op, obj, size=11)
        op.paragraph_format.space_after = Pt(6)
        op.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        op.paragraph_format.line_spacing = 1.15

    # Skills
    skills = data.get("skills", [])
    if skills:
        section_title("Ko'nikmalar" if lang == "uz" else "Skills")
        sp = doc.add_paragraph()
        add_run(sp, " • ".join(skills), size=11)
        sp.paragraph_format.space_after = Pt(6)

    # Experience
    exp = data.get("experience", [])
    if exp:
        section_title("Ish tajribasi" if lang == "uz" else "Experience")
        for e in exp:
            ep = doc.add_paragraph()
            add_run(ep, f"{e.get('title','')} — {e.get('company','')}", bold=True, size=11)
            add_run(ep, f"  ({e.get('period','')})", size=10, color=RGBColor(0x77,0x77,0x77))
            ep.paragraph_format.space_before = Pt(4)
            ep.paragraph_format.space_after = Pt(2)
            dp = doc.add_paragraph()
            add_run(dp, e.get('desc',''), size=11)
            dp.paragraph_format.first_line_indent = Cm(0.5)
            dp.paragraph_format.space_after = Pt(4)

    # Education
    edu = data.get("education", [])
    if edu:
        section_title("Ta'lim" if lang == "uz" else "Education")
        for e in edu:
            ep = doc.add_paragraph()
            add_run(ep, f"{e.get('degree','')} — {e.get('school','')}", bold=True, size=11)
            add_run(ep, f"  ({e.get('year','')})", size=10, color=RGBColor(0x77,0x77,0x77))
            ep.paragraph_format.space_before = Pt(4)
            ep.paragraph_format.space_after = Pt(4)

    # Languages
    langs = data.get("languages", [])
    if langs:
        section_title("Tillar" if lang == "uz" else "Languages")
        lp = doc.add_paragraph()
        add_run(lp, " • ".join(langs), size=11)

    buf = BytesIO(); doc.save(buf); buf.seek(0)
    return buf


async def generate_cv(name: str, profession: str, lang: str, extra: str = "") -> BytesIO:
    data = await asyncio.to_thread(_generate_cv_content, name, profession, lang, extra)
    return await asyncio.to_thread(_build_cv_docx, data, name, profession, lang)


# ═══════════════════════════════════════════════
# 2. MOTIVATSION XAT
# ═══════════════════════════════════════════════
def _generate_motivation_content(name: str, target: str, lang: str, reason: str = "") -> str:
    """Optimizatsiyalangan motivatsion xat — 1 so'rov, to'g'ridan-to'g'ri matn."""
    lang_inst = LANG_PROMPTS.get(lang, LANG_PROMPTS["uz"])
    client = get_client()
    prompt = (
        f"{lang_inst} Professional motivatsion xat yoz. "
        f"Muallif: {name}. Maqsad: {target}. "
        f"{f'Sabab: {reason}' if reason else ''} "
        f"Tuzilma: Murojaat → O'zim haqida (2 paragraf) → Nima uchun shu joy (1 paragraf) → Xulosa. "
        f"Rasmiy, ishonchli, 300-400 so'z. Faqat xat matnini yoz."
    )
    resp = get_client().chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1200,
        temperature=0.65,
    )
    return resp.choices[0].message.content.strip()


def _build_motivation_docx(text: str, name: str, target: str, lang: str) -> BytesIO:
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21); sec.page_height = Cm(29.7)
    sec.left_margin = Cm(3.0); sec.right_margin = Cm(1.5)
    sec.top_margin = Cm(2.5); sec.bottom_margin = Cm(2.0)

    # Sarlavha
    title_map = {"uz": "MOTIVATSION XAT", "ru": "МОТИВАЦИОННОЕ ПИСЬМО",
                 "en": "MOTIVATION LETTER", "ko": "자기소개서", "zh": "动机信", "de": "MOTIVATIONSSCHREIBEN"}
    tp = doc.add_paragraph()
    tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = tp.add_run(title_map.get(lang, "MOTIVATSION XAT"))
    tr.bold = True; tr.font.name = "Times New Roman"
    tr.font.size = Pt(16); tr.font.color.rgb = RGBColor(0x1A, 0x73, 0xE8)
    tp.paragraph_format.space_after = Pt(4)

    # Maqsad
    mp = doc.add_paragraph()
    mp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    mr = mp.add_run(target)
    mr.italic = True; mr.font.name = "Times New Roman"
    mr.font.size = Pt(12); mr.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
    mp.paragraph_format.space_after = Pt(20)

    # Xat matni
    for para in text.split("\n"):
        para = para.strip()
        if not para:
            continue
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.first_line_indent = Cm(1.25)
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        p.paragraph_format.line_spacing = 1.5
        r = p.add_run(para)
        r.font.name = "Times New Roman"; r.font.size = Pt(12)

    # Imzo
    doc.add_paragraph()
    sp = doc.add_paragraph()
    sp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    sr = sp.add_run(f"Hurmat bilan,\n{name}" if lang == "uz" else
                    f"С уважением,\n{name}" if lang == "ru" else
                    f"Sincerely,\n{name}")
    sr.font.name = "Times New Roman"; sr.font.size = Pt(12)

    buf = BytesIO(); doc.save(buf); buf.seek(0)
    return buf


async def generate_motivation(name: str, target: str, lang: str, reason: str = "") -> BytesIO:
    text = await asyncio.to_thread(_generate_motivation_content, name, target, lang, reason)
    return await asyncio.to_thread(_build_motivation_docx, text, name, target, lang)


# ═══════════════════════════════════════════════
# 3. JADVAL / DIAGRAMMA (Excel)
# ═══════════════════════════════════════════════
def _generate_table_content(topic: str, lang: str) -> dict:
    """Jadval ma'lumotlarini GPT dan oladi."""
    lang_inst = LANG_PROMPTS.get(lang, LANG_PROMPTS["uz"])
    client = get_client()
    prompt = (
        f"{lang_inst} {topic} mavzusida jadval ma'lumotlari yarat. "
        f"JSON: {{\"title\": \"...\", \"headers\": [\"...\"], "
        f"\"rows\": [[\"...\"], ...], \"summary\": \"...\"}} "
        f"Kamida 8-12 qator, 4-6 ustun. Haqiqiy, foydali ma'lumotlar."
    )
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1500,
        temperature=0.5,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def _build_excel(data: dict, topic: str) -> BytesIO:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.chart import BarChart, Reference

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = topic[:30]

    title = data.get("title", topic)
    headers = data.get("headers", [])
    rows = data.get("rows", [])
    summary = data.get("summary", "")

    # Sarlavha
    ws.merge_cells(f"A1:{chr(64+max(len(headers),1))}1")
    ws["A1"] = title
    ws["A1"].font = Font(name="Arial", bold=True, size=14, color="1A73E8")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws["A1"].fill = PatternFill("solid", fgColor="EBF3FE")
    ws.row_dimensions[1].height = 30

    # Header qatori
    header_fill = PatternFill("solid", fgColor="1A73E8")
    header_font = Font(name="Arial", bold=True, size=11, color="FFFFFF")
    thin = Side(style="thin", color="CCCCCC")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
        ws.column_dimensions[chr(64+col)].width = max(15, len(str(h))+4)
    ws.row_dimensions[2].height = 25

    # Ma'lumot qatorlari
    for r_idx, row in enumerate(rows, 3):
        fill_color = "F8FBFF" if r_idx % 2 == 0 else "FFFFFF"
        row_fill = PatternFill("solid", fgColor=fill_color)
        for c_idx, val in enumerate(row, 1):
            cell = ws.cell(row=r_idx, column=c_idx, value=val)
            cell.font = Font(name="Arial", size=10)
            cell.fill = row_fill
            cell.border = border
            cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[r_idx].height = 20

    # Xulosa
    last_row = len(rows) + 4
    ws.cell(row=last_row, column=1, value=f"Xulosa: {summary}")
    ws.cell(row=last_row, column=1).font = Font(name="Arial", italic=True, size=10, color="555555")

    # Diagramma (agar raqamli ma'lumot bo'lsa)
    try:
        numeric_cols = []
        for c_idx in range(2, len(headers)+1):
            try:
                float(rows[0][c_idx-1])
                numeric_cols.append(c_idx)
            except (ValueError, IndexError, TypeError):
                pass

        if numeric_cols and len(rows) >= 2:
            chart = BarChart()
            chart.type = "col"
            chart.title = title
            chart.style = 10
            chart.y_axis.title = headers[numeric_cols[0]-1] if numeric_cols else ""
            chart.x_axis.title = headers[0]
            chart.width = 18; chart.height = 12

            data_ref = Reference(ws, min_col=numeric_cols[0], min_row=2,
                                 max_col=numeric_cols[0], max_row=len(rows)+2)
            cats = Reference(ws, min_col=1, min_row=3, max_row=len(rows)+2)
            chart.add_data(data_ref, titles_from_data=True)
            chart.set_categories(cats)
            ws.add_chart(chart, f"A{last_row+2}")
    except Exception:
        pass

    buf = BytesIO(); wb.save(buf); buf.seek(0)
    return buf


async def generate_table(topic: str, lang: str) -> BytesIO:
    data = await asyncio.to_thread(_generate_table_content, topic, lang)
    return await asyncio.to_thread(_build_excel, data, topic)


# ═══════════════════════════════════════════════
# 4. KONTSEPT XARITA (Mind Map) — PNG
# ═══════════════════════════════════════════════
def _generate_mindmap_content(topic: str, lang: str) -> dict:
    """Mind map tuzilmasini GPT dan oladi."""
    lang_inst = LANG_PROMPTS.get(lang, LANG_PROMPTS["uz"])
    client = get_client()
    prompt = (
        f"{lang_inst} {topic} mavzusida mind map tuzilmasi yarat. "
        f"JSON: {{\"center\": \"...\", "
        f"\"branches\": [{{\"title\": \"...\", \"nodes\": [\"...\", \"...\"]}}]}} "
        f"5-7 ta branch, har birida 3-5 ta node. Qisqa, aniq so'zlar."
    )
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000,
        temperature=0.6,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def _build_mindmap_png(data: dict, topic: str) -> BytesIO:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np

    center = data.get("center", topic)
    branches = data.get("branches", [])

    fig, ax = plt.subplots(1, 1, figsize=(16, 12))
    ax.set_xlim(-10, 10); ax.set_ylim(-8, 8)
    ax.axis("off")
    fig.patch.set_facecolor("#F0F4FF")
    ax.set_facecolor("#F0F4FF")

    # Ranglar
    branch_colors = [
        "#1A73E8", "#E8711A", "#1AE871", "#E81A73",
        "#711AE8", "#E8E81A", "#1AE8E8"
    ]

    # Markaz
    ax.add_patch(mpatches.FancyBboxPatch(
        (-2.2, -0.7), 4.4, 1.4,
        boxstyle="round,pad=0.15", linewidth=2,
        edgecolor="#1A1A6E", facecolor="#1A1A6E"
    ))
    ax.text(0, 0, center, ha="center", va="center",
            fontsize=13, fontweight="bold", color="white",
            wrap=True, zorder=5)

    n = len(branches)
    if n == 0:
        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close()
        buf.seek(0)
        return buf

    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)

    for i, (branch, angle) in enumerate(zip(branches, angles)):
        color = branch_colors[i % len(branch_colors)]
        bx = 4.5 * np.cos(angle)
        by = 3.5 * np.sin(angle)

        # Markaz → branch chiziq
        ax.plot([0, bx], [0, by], color=color, linewidth=2, alpha=0.7, zorder=1)

        # Branch box
        title = branch.get("title", "")
        tw = max(len(title) * 0.12, 2.0)
        ax.add_patch(mpatches.FancyBboxPatch(
            (bx - tw/2, by - 0.4), tw, 0.8,
            boxstyle="round,pad=0.1", linewidth=1.5,
            edgecolor=color, facecolor=color, alpha=0.9, zorder=2
        ))
        ax.text(bx, by, title, ha="center", va="center",
                fontsize=9, fontweight="bold", color="white", zorder=3)

        # Nodes
        nodes = branch.get("nodes", [])
        nn = len(nodes)
        if nn == 0:
            continue

        # Node burchaklari — branch atrofida
        spread = 0.6
        node_angles = np.linspace(angle - spread, angle + spread, nn)
        for j, (node, nangle) in enumerate(zip(nodes, node_angles)):
            nx = bx + 3.0 * np.cos(nangle)
            ny = by + 2.2 * np.sin(nangle)

            # Chegara tekshiruvi
            nx = max(-9, min(9, nx))
            ny = max(-7, min(7, ny))

            # Branch → node chiziq
            ax.plot([bx, nx], [by, ny], color=color, linewidth=1,
                    alpha=0.5, linestyle="--", zorder=1)

            # Node box
            nw = max(len(node) * 0.11, 1.5)
            ax.add_patch(mpatches.FancyBboxPatch(
                (nx - nw/2, ny - 0.3), nw, 0.6,
                boxstyle="round,pad=0.08", linewidth=1,
                edgecolor=color, facecolor="white", alpha=0.95, zorder=2
            ))
            ax.text(nx, ny, node, ha="center", va="center",
                    fontsize=7.5, color="#333333", zorder=3)

    # Sarlavha
    ax.text(0, 7.5, f"Kontsept xarita: {topic}", ha="center", va="top",
            fontsize=14, fontweight="bold", color="#1A1A6E")

    # Footer
    ax.text(0, -7.7, "@slidego | t.me/slidego", ha="center", va="bottom",
            fontsize=8, color="#AAAAAA")

    plt.tight_layout()
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=150, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    buf.seek(0)
    return buf


async def generate_mindmap(topic: str, lang: str) -> BytesIO:
    data = await asyncio.to_thread(_generate_mindmap_content, topic, lang)
    return await asyncio.to_thread(_build_mindmap_png, data, topic)
