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
        f"JSON: {{\"objective\": \"2-3 jumlali maqsad\", "
        f"\"skills\": [\"skill1\", \"skill2\", \"skill3\", \"skill4\", \"skill5\", \"skill6\"], "
        f"\"experience\": ["
        f"  {{\"title\":\"lavozim\",\"company\":\"kompaniya\",\"period\":\"2020-hozir\",\"desc\":\"2-3 jumla tavsif\"}},"
        f"  {{\"title\":\"lavozim2\",\"company\":\"kompaniya2\",\"period\":\"2018-2020\",\"desc\":\"2-3 jumla tavsif\"}}"
        f"], "
        f"\"education\": ["
        f"  {{\"degree\":\"daraja\",\"school\":\"universitet\",\"year\":\"2018\",\"gpa\":\"GPA: 3.8\"}}"
        f"], "
        f"\"certifications\": [\"sertifikat1\", \"sertifikat2\"], "
        f"\"languages\": [\"til1 (daraja)\", \"til2 (daraja)\"], "
        f"\"contacts\": {{\"email\":\"email@example.com\",\"phone\":\"+998 XX XXX XX XX\",\"linkedin\":\"linkedin.com/in/username\",\"location\":\"Toshkent, O'zbekiston\"}} }}"
    )
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000,
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
        return r

    def section_title(title_text):
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(12)
        p.paragraph_format.space_after = Pt(5)
        add_run(p, title_text.upper(), bold=True, size=11, color=RGBColor(0x1A, 0x73, 0xE8))
        pPr = p._p.get_or_add_pPr()
        pBdr = OxmlElement('w:pBdr')
        b = OxmlElement('w:bottom')
        b.set(qn('w:val'), 'single'); b.set(qn('w:sz'), '6')
        b.set(qn('w:space'), '1'); b.set(qn('w:color'), '1A73E8')
        pBdr.append(b); pPr.append(pBdr)

    def bullet_item(text, color=None):
        p = doc.add_paragraph()
        p.paragraph_format.left_indent = Cm(0.5)
        p.paragraph_format.space_after = Pt(3)
        add_run(p, "▸  ", bold=True, size=10, color=RGBColor(0x1A, 0x73, 0xE8))
        add_run(p, text, size=10, color=color)
        return p

    # ── Header ──
    h = doc.add_paragraph()
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(h, name.upper(), bold=True, size=22, color=RGBColor(0x1A, 0x1A, 0x6E))
    h.paragraph_format.space_after = Pt(3)

    p2 = doc.add_paragraph()
    p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(p2, profession, size=13, color=RGBColor(0x1A, 0x73, 0xE8), italic=True)
    p2.paragraph_format.space_after = Pt(6)

    # ── Kontaktlar ──
    contacts = data.get("contacts", {})
    if contacts:
        cp = doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        parts = []
        if contacts.get("location"): parts.append(f"📍 {contacts['location']}")
        if contacts.get("email"):    parts.append(f"✉ {contacts['email']}")
        if contacts.get("phone"):    parts.append(f"📞 {contacts['phone']}")
        if contacts.get("linkedin"): parts.append(f"🔗 {contacts['linkedin']}")
        add_run(cp, "  |  ".join(parts), size=9, color=RGBColor(0x44, 0x44, 0x44))
        cp.paragraph_format.space_after = Pt(4)

    # Ajratuvchi chiziq
    sep = doc.add_paragraph()
    sep.paragraph_format.space_before = Pt(2)
    sep.paragraph_format.space_after = Pt(2)
    pPr = sep._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    b = OxmlElement('w:bottom')
    b.set(qn('w:val'), 'single'); b.set(qn('w:sz'), '8')
    b.set(qn('w:space'), '1'); b.set(qn('w:color'), '1A1A6E')
    pBdr.append(b); pPr.append(pBdr)

    # ── Maqsad ──
    obj = data.get("objective", "")
    if obj:
        section_title("Maqsad" if lang == "uz" else "Objective" if lang == "en" else "Цель")
        op = doc.add_paragraph()
        op.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_run(op, obj, size=11)
        op.paragraph_format.space_after = Pt(4)
        op.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        op.paragraph_format.line_spacing = 1.2

    # ── Ko'nikmalar (2 ustunli ko'rinish) ──
    skills = data.get("skills", [])
    if skills:
        section_title("Ko'nikmalar" if lang == "uz" else "Skills" if lang == "en" else "Навыки")
        # Juft-toq qilib 2 ta bullet bir qatorda
        for i in range(0, len(skills), 2):
            p = doc.add_paragraph()
            p.paragraph_format.space_after = Pt(2)
            add_run(p, "▸  ", bold=True, size=10, color=RGBColor(0x1A, 0x73, 0xE8))
            add_run(p, skills[i], size=10)
            if i + 1 < len(skills):
                add_run(p, "          ▸  ", bold=True, size=10, color=RGBColor(0x1A, 0x73, 0xE8))
                add_run(p, skills[i+1], size=10)

    # ── Ish tajribasi ──
    exp = data.get("experience", [])
    if exp:
        section_title("Ish tajribasi" if lang == "uz" else "Experience" if lang == "en" else "Опыт работы")
        for e in exp:
            ep = doc.add_paragraph()
            ep.paragraph_format.space_before = Pt(6)
            ep.paragraph_format.space_after = Pt(2)
            add_run(ep, f"{e.get('title','')}", bold=True, size=11, color=RGBColor(0x1A, 0x1A, 0x6E))
            add_run(ep, f"  —  {e.get('company','')}", size=11)
            add_run(ep, f"  |  {e.get('period','')}", size=10, color=RGBColor(0x77,0x77,0x77), italic=True)

            dp = doc.add_paragraph()
            dp.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
            dp.paragraph_format.left_indent = Cm(0.5)
            dp.paragraph_format.space_after = Pt(4)
            dp.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
            dp.paragraph_format.line_spacing = 1.2
            add_run(dp, e.get('desc',''), size=10, color=RGBColor(0x33, 0x33, 0x33))

    # ── Ta'lim ──
    edu = data.get("education", [])
    if edu:
        section_title("Ta'lim" if lang == "uz" else "Education" if lang == "en" else "Образование")
        for e in edu:
            ep = doc.add_paragraph()
            ep.paragraph_format.space_before = Pt(5)
            ep.paragraph_format.space_after = Pt(2)
            add_run(ep, f"{e.get('degree','')}", bold=True, size=11, color=RGBColor(0x1A, 0x1A, 0x6E))
            add_run(ep, f"  —  {e.get('school','')}", size=11)
            add_run(ep, f"  |  {e.get('year','')}", size=10, color=RGBColor(0x77,0x77,0x77), italic=True)
            if e.get("gpa"):
                gp = doc.add_paragraph()
                gp.paragraph_format.left_indent = Cm(0.5)
                gp.paragraph_format.space_after = Pt(2)
                add_run(gp, e.get("gpa",""), size=10, color=RGBColor(0x44, 0x44, 0x44))

    # ── Sertifikatlar ──
    certs = data.get("certifications", [])
    if certs:
        section_title("Sertifikatlar" if lang == "uz" else "Certifications" if lang == "en" else "Сертификаты")
        for c in certs:
            bullet_item(c)

    # ── Tillar ──
    langs = data.get("languages", [])
    if langs:
        section_title("Tillar" if lang == "uz" else "Languages" if lang == "en" else "Языки")
        lp = doc.add_paragraph()
        lp.paragraph_format.space_after = Pt(4)
        for i, l in enumerate(langs):
            if i > 0:
                add_run(lp, "   •   ", size=10, color=RGBColor(0x1A, 0x73, 0xE8))
            add_run(lp, l, size=10)

    # ── Footer ──
    fp = doc.add_paragraph()
    fp.paragraph_format.space_before = Pt(16)
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_run(fp, "@slidego | t.me/slidego", size=8, color=RGBColor(0xAA, 0xAA, 0xAA), italic=True)

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
        f"{('Sabab: ' + reason) if reason else ''} "
        f"Tuzilma: 1) Murojaat jumlasi, 2) O'zim haqida (2 paragraf), "
        f"3) Nima uchun shu joy (1 paragraf), 4) Xulosa. "
        f"Rasmiy, ishonchli, 350-450 so'z. "
        f"MUHIM: Faqat xat matnini yoz. Imzo yozma — uni alohida qo'shaman."
    )
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1400,
        temperature=0.65,
    )
    return resp.choices[0].message.content.strip()


def _build_motivation_docx(text: str, name: str, target: str, lang: str) -> BytesIO:
    doc = Document()
    sec = doc.sections[0]
    sec.page_width = Cm(21); sec.page_height = Cm(29.7)
    sec.left_margin = Cm(3.0); sec.right_margin = Cm(2.5)
    sec.top_margin = Cm(3.0); sec.bottom_margin = Cm(2.5)

    def add_run(para, text, bold=False, size=12, color=None, italic=False):
        r = para.add_run(text)
        r.bold = bold; r.italic = italic
        r.font.name = "Times New Roman"; r.font.size = Pt(size)
        if color: r.font.color.rgb = color
        return r

    # ── Sarlavha ──
    title_map = {
        "uz": "MOTIVATSION XAT", "ru": "МОТИВАЦИОННОЕ ПИСЬМО",
        "en": "MOTIVATION LETTER", "ko": "자기소개서", "zh": "动机信", "de": "MOTIVATIONSSCHREIBEN"
    }
    tp = doc.add_paragraph()
    tp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    tr = tp.add_run(title_map.get(lang, "MOTIVATSION XAT"))
    tr.bold = True; tr.font.name = "Times New Roman"
    tr.font.size = Pt(16); tr.font.color.rgb = RGBColor(0x1A, 0x73, 0xE8)
    tp.paragraph_format.space_before = Pt(0)
    tp.paragraph_format.space_after = Pt(6)

    # ── Maqsad ──
    mp = doc.add_paragraph()
    mp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    mr = mp.add_run(target)
    mr.italic = True; mr.font.name = "Times New Roman"
    mr.font.size = Pt(12); mr.font.color.rgb = RGBColor(0x44, 0x44, 0x44)
    mp.paragraph_format.space_after = Pt(18)

    # ── Ajratuvchi ──
    sep = doc.add_paragraph()
    sep.paragraph_format.space_before = Pt(0)
    sep.paragraph_format.space_after = Pt(14)
    pPr = sep._p.get_or_add_pPr()
    pBdr = OxmlElement('w:pBdr')
    b = OxmlElement('w:bottom')
    b.set(qn('w:val'), 'single'); b.set(qn('w:sz'), '6')
    b.set(qn('w:space'), '1'); b.set(qn('w:color'), '1A73E8')
    pBdr.append(b); pPr.append(pBdr)

    # ── Xat matni ──
    # Imzo jumlalarini matndan tozalash
    sign_keywords = [
        "hurmat bilan", "с уважением", "sincerely", "mit freundlichen",
        "경의를 표하며", "此致", name.lower().split()[0] if name else ""
    ]
    lines = text.split("\n")
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Imzo qismini o'tkazib yuborish
        low = stripped.lower()
        if any(kw in low for kw in sign_keywords if kw):
            continue
        clean_lines.append(stripped)

    for para_text in clean_lines:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.first_line_indent = Cm(1.25)
        p.paragraph_format.space_after = Pt(10)
        p.paragraph_format.line_spacing_rule = WD_LINE_SPACING.MULTIPLE
        p.paragraph_format.line_spacing = 1.5
        r = p.add_run(para_text)
        r.font.name = "Times New Roman"; r.font.size = Pt(12)

    # ── Imzo (bir marta, o'ngda) ──
    doc.add_paragraph().paragraph_format.space_after = Pt(20)

    sign_labels = {
        "uz": "Hurmat bilan,",
        "ru": "С уважением,",
        "en": "Sincerely,",
        "ko": "경의를 표하며,",
        "zh": "此致,",
        "de": "Mit freundlichen Grüßen,"
    }
    sp = doc.add_paragraph()
    sp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    sr = sp.add_run(f"{sign_labels.get(lang, 'Hurmat bilan,')}\n{name}")
    sr.font.name = "Times New Roman"; sr.font.size = Pt(12)
    sp.paragraph_format.space_after = Pt(4)

    # ── Footer ──
    fp = doc.add_paragraph()
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    fp.paragraph_format.space_before = Pt(20)
    fr = fp.add_run("@slidego | t.me/slidego")
    fr.font.name = "Times New Roman"; fr.font.size = Pt(8)
    fr.font.color.rgb = RGBColor(0xAA, 0xAA, 0xAA)
    fr.italic = True

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
        f"{lang_inst} {topic} mavzusida aniq, haqiqiy jadval ma'lumotlari yarat. "
        f"JSON: {{\"title\": \"jadval sarlavhasi\", "
        f"\"headers\": [\"ustun1\", \"ustun2\", \"ustun3\", \"ustun4\"], "
        f"\"rows\": [[\"qiymat1\", \"qiymat2\", \"qiymat3\", \"qiymat4\"], ...], "
        f"\"summary\": \"qisqa xulosa\"}} "
        f"10-12 qator, 4-5 ustun. Raqamli ma'lumotlar bo'lsin (diagramma uchun)."
    )
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1800,
        temperature=0.5,
        response_format={"type": "json_object"},
    )
    return json.loads(resp.choices[0].message.content)


def _build_excel(data: dict, topic: str) -> BytesIO:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.chart import BarChart, Reference
    from openpyxl.chart.series import DataPoint

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = topic[:28]

    title = data.get("title", topic)
    headers = data.get("headers", [])
    rows = data.get("rows", [])
    summary = data.get("summary", "")

    thin = Side(style="thin", color="D0D8E8")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # ── Sarlavha ──
    end_col = chr(64 + max(len(headers), 1))
    ws.merge_cells(f"A1:{end_col}1")
    ws["A1"] = title
    ws["A1"].font = Font(name="Arial", bold=True, size=14, color="1A1A6E")
    ws["A1"].alignment = Alignment(horizontal="center", vertical="center")
    ws["A1"].fill = PatternFill("solid", fgColor="EBF3FE")
    ws.row_dimensions[1].height = 32

    # ── Header qatori ──
    header_fill = PatternFill("solid", fgColor="1A73E8")
    header_font = Font(name="Arial", bold=True, size=11, color="FFFFFF")

    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=2, column=col, value=h)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
        ws.column_dimensions[chr(64+col)].width = max(16, len(str(h))+5)
    ws.row_dimensions[2].height = 28

    # ── Ma'lumot qatorlari ──
    for r_idx, row in enumerate(rows, 3):
        fill_color = "F0F6FF" if r_idx % 2 == 0 else "FFFFFF"
        row_fill = PatternFill("solid", fgColor=fill_color)
        for c_idx, val in enumerate(row, 1):
            # Raqamga o'tkazishga harakat
            try:
                val_num = float(str(val).replace(",", ".").replace(" ", ""))
                display_val = val_num
            except (ValueError, TypeError):
                display_val = val
            cell = ws.cell(row=r_idx, column=c_idx, value=display_val)
            cell.font = Font(name="Arial", size=10)
            cell.fill = row_fill
            cell.border = border
            cell.alignment = Alignment(
                horizontal="right" if isinstance(display_val, float) else "left",
                vertical="center"
            )
        ws.row_dimensions[r_idx].height = 22

    # ── Xulosa qatori ──
    last_data_row = len(rows) + 2
    summary_row = last_data_row + 2
    ws.merge_cells(f"A{summary_row}:{end_col}{summary_row}")
    ws[f"A{summary_row}"] = f"📌 Xulosa: {summary}"
    ws[f"A{summary_row}"].font = Font(name="Arial", italic=True, size=10, color="444444")
    ws[f"A{summary_row}"].fill = PatternFill("solid", fgColor="FFF8E1")
    ws[f"A{summary_row}"].alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
    ws.row_dimensions[summary_row].height = 30

    # ── Footer ──
    footer_row = summary_row + 2
    ws.merge_cells(f"A{footer_row}:{end_col}{footer_row}")
    ws[f"A{footer_row}"] = "@slidego | t.me/slidego"
    ws[f"A{footer_row}"].font = Font(name="Arial", italic=True, size=8, color="AAAAAA")
    ws[f"A{footer_row}"].alignment = Alignment(horizontal="center")

    # ── Diagramma ──
    try:
        # Raqamli ustunlarni topish
        numeric_cols = []
        for c_idx in range(2, len(headers)+1):
            try:
                float(str(rows[0][c_idx-1]).replace(",", ".").replace(" ", ""))
                numeric_cols.append(c_idx)
            except (ValueError, IndexError, TypeError):
                pass

        if numeric_cols and len(rows) >= 3:
            chart = BarChart()
            chart.type = "col"
            chart.grouping = "clustered"
            chart.title = title
            chart.style = 10
            chart.y_axis.title = headers[numeric_cols[0]-1] if numeric_cols else ""
            chart.x_axis.title = headers[0]
            chart.width = 20; chart.height = 14

            # Birinchi raqamli ustun uchun
            data_ref = Reference(ws, min_col=numeric_cols[0], min_row=2,
                                 max_col=numeric_cols[0], max_row=last_data_row)
            cats = Reference(ws, min_col=1, min_row=3, max_row=last_data_row)
            chart.add_data(data_ref, titles_from_data=True)
            chart.set_categories(cats)

            # Agar 2 ta raqamli ustun bo'lsa, ikkinchisini ham qo'shish
            if len(numeric_cols) >= 2:
                data_ref2 = Reference(ws, min_col=numeric_cols[1], min_row=2,
                                      max_col=numeric_cols[1], max_row=last_data_row)
                chart.add_data(data_ref2, titles_from_data=True)

            ws.add_chart(chart, f"A{footer_row + 2}")
    except Exception as e:
        logger.warning(f"Diagramma yaratishda xatolik: {e}")

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
        f"JSON: {{\"center\": \"qisqa nom (max 3 so'z)\", "
        f"\"branches\": [{{\"title\": \"branch nomi (max 2 so'z)\", "
        f"\"nodes\": [\"node1 (max 3 so'z)\", \"node2\", \"node3\"]}}]}} "
        f"6 ta branch, har birida 4 ta node. Juda qisqa so'zlar."
    )
    resp = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=900,
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
    n = len(branches)

    # Kanvas
    fig, ax = plt.subplots(1, 1, figsize=(18, 14))
    ax.set_xlim(-11, 11); ax.set_ylim(-9, 9)
    ax.axis("off")
    fig.patch.set_facecolor("#F5F7FF")
    ax.set_facecolor("#F5F7FF")

    # Ranglar — professional
    branch_colors = [
        "#1A73E8",  # Ko'k
        "#E8711A",  # To'q sariq
        "#0F9D58",  # Yashil
        "#D93025",  # Qizil
        "#7B1FA2",  # Binafsha
        "#F4B400",  # Sariq
        "#00ACC1",  # Moviy
    ]

    # ── Markaz ──
    center_w = max(len(center) * 0.18, 3.0)
    center_h = 1.0
    ax.add_patch(mpatches.FancyBboxPatch(
        (-center_w/2, -center_h/2), center_w, center_h,
        boxstyle="round,pad=0.2", linewidth=3,
        edgecolor="#0D1B6E", facecolor="#1A1A6E", zorder=5
    ))
    ax.text(0, 0, center, ha="center", va="center",
            fontsize=14, fontweight="bold", color="white", zorder=6)

    if n == 0:
        buf = BytesIO()
        plt.savefig(buf, format="png", dpi=150, bbox_inches="tight")
        plt.close(); buf.seek(0)
        return buf

    # Branch joylashuvi — doira bo'ylab
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    # Birinchi branch yuqoridan boshlansin
    angles = angles + np.pi / 2

    # Branch masofasi
    branch_r = 5.0

    for i, (branch, angle) in enumerate(zip(branches, angles)):
        color = branch_colors[i % len(branch_colors)]
        bx = branch_r * np.cos(angle)
        by = branch_r * np.sin(angle)

        # Markaz → branch chiziq (qalin)
        ax.plot([0, bx * 0.55], [0, by * 0.55], color=color,
                linewidth=3, alpha=0.8, zorder=1, solid_capstyle='round')
        ax.plot([bx * 0.55, bx], [by * 0.55, by], color=color,
                linewidth=2, alpha=0.6, zorder=1, solid_capstyle='round')

        # Branch box
        title = branch.get("title", "")
        tw = max(len(title) * 0.16, 2.2)
        th = 0.75
        ax.add_patch(mpatches.FancyBboxPatch(
            (bx - tw/2, by - th/2), tw, th,
            boxstyle="round,pad=0.12", linewidth=2,
            edgecolor=color, facecolor=color, alpha=0.95, zorder=4
        ))
        ax.text(bx, by, title, ha="center", va="center",
                fontsize=10, fontweight="bold", color="white", zorder=5)

        # Nodes
        nodes = branch.get("nodes", [])
        nn = len(nodes)
        if nn == 0:
            continue

        # Node joylashuvi — branch atrofida yoyilgan
        # Har bir node uchun burchak hisoblash
        # Branchdan tashqariga qarab, lekin bir-biriga tegmasin
        node_r = 3.2  # Branch dan node gacha masofa
        spread = min(0.55, 0.9 / max(nn, 1))
        node_angles = np.linspace(angle - spread * (nn-1)/2,
                                  angle + spread * (nn-1)/2, nn)

        for j, (node, nangle) in enumerate(zip(nodes, node_angles)):
            nx = bx + node_r * np.cos(nangle)
            ny = by + node_r * np.sin(nangle)

            # Chegara tekshiruvi
            nx = np.clip(nx, -10.2, 10.2)
            ny = np.clip(ny, -8.2, 8.2)

            # Branch → node chiziq
            ax.plot([bx, nx], [by, ny], color=color, linewidth=1.2,
                    alpha=0.5, linestyle="-", zorder=2, solid_capstyle='round')

            # Node box
            nw = max(len(node) * 0.13, 1.8)
            nh = 0.55
            ax.add_patch(mpatches.FancyBboxPatch(
                (nx - nw/2, ny - nh/2), nw, nh,
                boxstyle="round,pad=0.08", linewidth=1.2,
                edgecolor=color, facecolor="white", alpha=0.97, zorder=3
            ))
            ax.text(nx, ny, node, ha="center", va="center",
                    fontsize=8, color="#222222", zorder=4,
                    fontfamily="DejaVu Sans")

    # ── Sarlavha ──
    ax.text(0, 8.5, f"Kontsept xarita: {topic}", ha="center", va="top",
            fontsize=15, fontweight="bold", color="#1A1A6E",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                      edgecolor="#1A73E8", linewidth=1.5, alpha=0.9))

    # ── Footer ──
    ax.text(0, -8.7, "@slidego  |  t.me/slidego", ha="center", va="bottom",
            fontsize=9, color="#AAAAAA", style="italic")

    plt.tight_layout(pad=1.5)
    buf = BytesIO()
    plt.savefig(buf, format="png", dpi=160, bbox_inches="tight",
                facecolor=fig.get_facecolor())
    plt.close()
    buf.seek(0)
    return buf


async def generate_mindmap(topic: str, lang: str) -> BytesIO:
    data = await asyncio.to_thread(_generate_mindmap_content, topic, lang)
    return await asyncio.to_thread(_build_mindmap_png, data, topic)
