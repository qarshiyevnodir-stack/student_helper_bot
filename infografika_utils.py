"""
infografika_utils.py — Infografika generatsiya moduli

Turlari:
  - statistik   : grafiklar va diagrammalar
  - jarayon     : qadamba-qadam ko'rsatma
  - taqqoslash  : ikki narsa/tushuncha taqqoslash
  - umumiy      : matn + ikonkalar + ranglar

Rang sxemalari:
  - ko'k        : professional ko'k
  - yashil      : tabiiy yashil
  - qizil       : issiq qizil
  - binafsha    : zamonaviy binafsha
  - to'q sariq  : quyosh sariq
"""

import os
import io
import json
import logging
import textwrap
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from openai import OpenAI

client = OpenAI()
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# Font sozlamalari
# ─────────────────────────────────────────────
FONT_REGULAR = "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"
FONT_BOLD    = "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"

# ─────────────────────────────────────────────
# Rang sxemalari
# ─────────────────────────────────────────────
COLOR_SCHEMES = {
    "ko'k": {
        "primary":    "#1565C0",
        "secondary":  "#42A5F5",
        "accent":     "#E3F2FD",
        "text":       "#0D1B2A",
        "light":      "#BBDEFB",
        "bg":         "#F0F7FF",
        "header_bg":  "#1565C0",
        "header_fg":  "#FFFFFF",
    },
    "yashil": {
        "primary":    "#2E7D32",
        "secondary":  "#66BB6A",
        "accent":     "#E8F5E9",
        "text":       "#1B2E1C",
        "light":      "#C8E6C9",
        "bg":         "#F1FBF1",
        "header_bg":  "#2E7D32",
        "header_fg":  "#FFFFFF",
    },
    "qizil": {
        "primary":    "#C62828",
        "secondary":  "#EF5350",
        "accent":     "#FFEBEE",
        "text":       "#2D0A0A",
        "light":      "#FFCDD2",
        "bg":         "#FFF5F5",
        "header_bg":  "#C62828",
        "header_fg":  "#FFFFFF",
    },
    "binafsha": {
        "primary":    "#6A1B9A",
        "secondary":  "#AB47BC",
        "accent":     "#F3E5F5",
        "text":       "#1A0A2E",
        "light":      "#E1BEE7",
        "bg":         "#F9F0FF",
        "header_bg":  "#6A1B9A",
        "header_fg":  "#FFFFFF",
    },
    "to'q sariq": {
        "primary":    "#E65100",
        "secondary":  "#FFA726",
        "accent":     "#FFF3E0",
        "text":       "#2E1A00",
        "light":      "#FFE0B2",
        "bg":         "#FFFAF0",
        "header_bg":  "#E65100",
        "header_fg":  "#FFFFFF",
    },
}

# ─────────────────────────────────────────────
# GPT yordamchi
# ─────────────────────────────────────────────
def gpt_generate(prompt: str, system: str = "Siz foydali yordamchisiz.") -> str:
    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": system},
                {"role": "user",   "content": prompt},
            ],
            temperature=0.7,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"GPT xatolik: {e}")
        return ""


def gpt_json(prompt: str, system: str) -> dict | list:
    """GPT dan JSON formatda javob oladi."""
    raw = gpt_generate(prompt, system)
    # JSON blokni ajratib olish
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    try:
        return json.loads(raw)
    except Exception:
        return {}


# ─────────────────────────────────────────────
# Rang yordamchisi
# ─────────────────────name─────────────────────
def hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))


# ─────────────────────────────────────────────
# PIL yordamchilari
# ─────────────────────────────────────────────
def get_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REGULAR
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def draw_wrapped_text(draw, text, x, y, max_width, font, fill, line_spacing=8):
    """Matnni qatorlarga bo'lib chizadi, y koordinatini qaytaradi."""
    words = text.split()
    lines = []
    current = ""
    for word in words:
        test = (current + " " + word).strip()
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)

    for line in lines:
        draw.text((x, y), line, font=font, fill=fill)
        bbox = draw.textbbox((0, 0), line, font=font)
        y += (bbox[3] - bbox[1]) + line_spacing
    return y


def draw_rounded_rect(draw, x1, y1, x2, y2, radius, fill, outline=None, outline_width=2):
    """Yumaloq burchakli to'rtburchak chizadi."""
    draw.rounded_rectangle([x1, y1, x2, y2], radius=radius, fill=fill,
                           outline=outline, width=outline_width)


# ─────────────────────────────────────────────
# 1. STATISTIK infografika
# ─────────────────────────────────────────────
def generate_statistik(topic: str, lang: str, colors: dict) -> Image.Image:
    """Bar chart + pie chart kombinatsiyasi."""
    system = f"Siz infografika mazmuni tayyorlovchi mutaxassissiz. Javobni faqat JSON formatida bering."
    prompt = f"""
Mavzu: "{topic}"
Til: {lang}

Quyidagi JSON strukturasida ma'lumot bering:
{{
  "title": "Infografika sarlavhasi",
  "subtitle": "Qisqa tavsif (1 jumla)",
  "bar_chart": {{
    "title": "Grafik sarlavhasi",
    "labels": ["Kategoriya1", "Kategoriya2", "Kategoriya3", "Kategoriya4", "Kategoriya5"],
    "values": [85, 72, 60, 45, 30],
    "unit": "foiz yoki boshqa birlik"
  }},
  "pie_chart": {{
    "title": "Taqsimot sarlavhasi",
    "labels": ["Qism1", "Qism2", "Qism3", "Qism4"],
    "values": [40, 30, 20, 10]
  }},
  "key_facts": [
    "Muhim fakt 1",
    "Muhim fakt 2",
    "Muhim fakt 3"
  ],
  "footer": "Manba yoki qo'shimcha ma'lumot"
}}
Faqat JSON qaytaring, boshqa hech narsa yozmang.
"""
    data = gpt_json(prompt, system)
    if not data:
        data = {
            "title": topic,
            "subtitle": "Ma'lumotlar tahlili",
            "bar_chart": {"title": "Ko'rsatkichlar", "labels": ["A","B","C","D","E"], "values": [80,65,55,40,25], "unit": "%"},
            "pie_chart": {"title": "Taqsimot", "labels": ["1-qism","2-qism","3-qism","4-qism"], "values": [40,30,20,10]},
            "key_facts": ["Fakt 1", "Fakt 2", "Fakt 3"],
            "footer": "Ma'lumotlar asosida tayyorlandi"
        }

    W, H = 1200, 1600
    img = Image.new("RGB", (W, H), color=data.get("bg", colors["bg"]) if "bg" in colors else colors["bg"])
    draw = ImageDraw.Draw(img)

    # Header
    draw_rounded_rect(draw, 0, 0, W, 140, 0, fill=colors["primary"])
    title_font = get_font(42, bold=True)
    sub_font   = get_font(22)
    draw.text((W//2, 45), data.get("title", topic), font=title_font, fill=colors["header_fg"], anchor="mm")
    draw.text((W//2, 105), data.get("subtitle", ""), font=sub_font, fill=colors["light"], anchor="mm")

    # Bar chart (matplotlib)
    bar_data = data.get("bar_chart", {})
    labels = bar_data.get("labels", [])
    values = bar_data.get("values", [])
    if labels and values:
        fig, ax = plt.subplots(figsize=(9, 4), dpi=120)
        bar_colors = [colors["primary"], colors["secondary"]] * (len(labels) // 2 + 1)
        bars = ax.barh(labels, values, color=bar_colors[:len(labels)], edgecolor="white", linewidth=1.5)
        ax.set_title(bar_data.get("title", ""), fontsize=14, fontweight="bold", color=colors["text"], pad=10)
        ax.set_xlabel(bar_data.get("unit", ""), fontsize=11, color=colors["text"])
        ax.tick_params(colors=colors["text"])
        for spine in ax.spines.values():
            spine.set_visible(False)
        ax.set_facecolor(colors["bg"])
        fig.patch.set_facecolor(colors["bg"])
        for bar, val in zip(bars, values):
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                    f"{val}", va="center", fontsize=11, color=colors["text"], fontweight="bold")
        buf = io.BytesIO()
        plt.savefig(buf, format="PNG", bbox_inches="tight", facecolor=colors["bg"])
        plt.close(fig)
        buf.seek(0)
        bar_img = Image.open(buf).convert("RGBA")
        bar_img = bar_img.resize((1100, 440))
        img.paste(bar_img, (50, 160), bar_img)

    # Pie chart
    pie_data = data.get("pie_chart", {})
    pie_labels = pie_data.get("labels", [])
    pie_values = pie_data.get("values", [])
    if pie_labels and pie_values:
        pie_colors = [colors["primary"], colors["secondary"], colors["light"], colors["accent"]]
        fig2, ax2 = plt.subplots(figsize=(5, 4), dpi=120)
        wedges, texts, autotexts = ax2.pie(
            pie_values, labels=pie_labels,
            colors=pie_colors[:len(pie_labels)],
            autopct="%1.0f%%", startangle=140,
            textprops={"fontsize": 10, "color": colors["text"]}
        )
        for at in autotexts:
            at.set_color("white")
            at.set_fontweight("bold")
        ax2.set_title(pie_data.get("title", ""), fontsize=13, fontweight="bold", color=colors["text"])
        fig2.patch.set_facecolor(colors["bg"])
        buf2 = io.BytesIO()
        plt.savefig(buf2, format="PNG", bbox_inches="tight", facecolor=colors["bg"])
        plt.close(fig2)
        buf2.seek(0)
        pie_img = Image.open(buf2).convert("RGBA")
        pie_img = pie_img.resize((560, 440))
        img.paste(pie_img, (50, 620), pie_img)

    # Key facts
    facts = data.get("key_facts", [])
    fact_font = get_font(24)
    fact_title_font = get_font(28, bold=True)
    y_facts = 1090
    draw_rounded_rect(draw, 30, y_facts - 10, W - 30, y_facts + 50, 10, fill=colors["primary"])
    draw.text((W//2, y_facts + 20), "Asosiy faktlar", font=fact_title_font, fill=colors["header_fg"], anchor="mm")
    y_facts += 70
    for i, fact in enumerate(facts[:4]):
        draw_rounded_rect(draw, 50, y_facts, W - 50, y_facts + 70, 12, fill=colors["accent"], outline=colors["secondary"], outline_width=2)
        draw.text((90, y_facts + 22), f"✦  {fact}", font=fact_font, fill=colors["text"])
        y_facts += 90

    # Footer
    footer_font = get_font(18)
    draw_rounded_rect(draw, 0, H - 60, W, H, 0, fill=colors["primary"])
    draw.text((W//2, H - 30), data.get("footer", ""), font=footer_font, fill=colors["light"], anchor="mm")

    return img


# ─────────────────────────────────────────────
# 2. JARAYON infografika
# ─────────────────────────────────────────────
def generate_jarayon(topic: str, lang: str, colors: dict) -> Image.Image:
    """Qadamba-qadam jarayon ko'rsatmasi."""
    system = "Siz infografika mazmuni tayyorlovchi mutaxassissiz. Faqat JSON qaytaring."
    prompt = f"""
Mavzu: "{topic}"
Til: {lang}

JSON strukturasi:
{{
  "title": "Jarayon sarlavhasi",
  "subtitle": "Qisqa tavsif",
  "steps": [
    {{"number": 1, "title": "Qadam sarlavhasi", "description": "Qisqa tavsif (1-2 jumla)"}},
    {{"number": 2, "title": "Qadam sarlavhasi", "description": "Qisqa tavsif"}},
    {{"number": 3, "title": "Qadam sarlavhasi", "description": "Qisqa tavsif"}},
    {{"number": 4, "title": "Qadam sarlavhasi", "description": "Qisqa tavsif"}},
    {{"number": 5, "title": "Qadam sarlavhasi", "description": "Qisqa tavsif"}},
    {{"number": 6, "title": "Qadam sarlavhasi", "description": "Qisqa tavsif"}}
  ],
  "conclusion": "Xulosa yoki natija (1 jumla)",
  "footer": "Manba"
}}
Faqat JSON qaytaring.
"""
    data = gpt_json(prompt, system)
    if not data or "steps" not in data:
        data = {
            "title": topic, "subtitle": "Jarayon bosqichlari",
            "steps": [{"number": i, "title": f"Qadam {i}", "description": "Tavsif"} for i in range(1, 7)],
            "conclusion": "Muvaffaqiyatli natija",
            "footer": "Infografika"
        }

    steps = data.get("steps", [])[:6]
    W, H = 1000, 1600
    img = Image.new("RGB", (W, H), color=colors["bg"])
    draw = ImageDraw.Draw(img)

    # Header
    draw_rounded_rect(draw, 0, 0, W, 150, 0, fill=colors["primary"])
    draw.text((W//2, 55), data.get("title", topic), font=get_font(40, bold=True),
              fill=colors["header_fg"], anchor="mm")
    draw.text((W//2, 115), data.get("subtitle", ""), font=get_font(22),
              fill=colors["light"], anchor="mm")

    # Steps
    step_h = 195
    y = 180
    for i, step in enumerate(steps):
        # Connector line
        if i < len(steps) - 1:
            draw.line([(W//2, y + step_h - 10), (W//2, y + step_h + 25)],
                      fill=colors["secondary"], width=4)

        # Card
        is_left = i % 2 == 0
        card_x1 = 40 if is_left else W // 2 + 20
        card_x2 = W // 2 - 20 if is_left else W - 40
        draw_rounded_rect(draw, card_x1, y, card_x2, y + step_h - 20, 16,
                          fill=colors["accent"], outline=colors["secondary"], outline_width=2)

        # Number circle
        cx = card_x1 + 45 if is_left else card_x2 - 45
        cy = y + (step_h - 20) // 2
        draw.ellipse([cx - 30, cy - 30, cx + 30, cy + 30], fill=colors["primary"])
        draw.text((cx, cy), str(step.get("number", i+1)), font=get_font(26, bold=True),
                  fill=colors["header_fg"], anchor="mm")

        # Text
        tx = card_x1 + 90 if is_left else card_x1 + 10
        tw = (card_x2 - card_x1) - 110
        ty = y + 20
        ty = draw_wrapped_text(draw, step.get("title", ""), tx, ty, tw,
                               get_font(22, bold=True), colors["primary"])
        draw_wrapped_text(draw, step.get("description", ""), tx, ty + 5, tw,
                          get_font(18), colors["text"])
        y += step_h

    # Conclusion
    conc_y = y + 10
    draw_rounded_rect(draw, 40, conc_y, W - 40, conc_y + 80, 16, fill=colors["primary"])
    draw.text((W//2, conc_y + 40), "✓  " + data.get("conclusion", ""),
              font=get_font(24, bold=True), fill=colors["header_fg"], anchor="mm")

    # Footer
    draw_rounded_rect(draw, 0, H - 55, W, H, 0, fill=colors["secondary"])
    draw.text((W//2, H - 28), data.get("footer", ""), font=get_font(18),
              fill=colors["header_fg"], anchor="mm")

    return img


# ─────────────────────────────────────────────
# 3. TAQQOSLASH infografika
# ─────────────────────────────────────────────
def generate_taqqoslash(topic: str, lang: str, colors: dict) -> Image.Image:
    """Ikki narsa/tushuncha taqqoslash."""
    system = "Siz infografika mazmuni tayyorlovchi mutaxassissiz. Faqat JSON qaytaring."
    prompt = f"""
Mavzu: "{topic}"
Til: {lang}

JSON strukturasi:
{{
  "title": "Taqqoslash sarlavhasi",
  "item_a": {{
    "name": "Birinchi narsa nomi",
    "icon": "A",
    "points": ["Xususiyat 1", "Xususiyat 2", "Xususiyat 3", "Xususiyat 4", "Xususiyat 5"]
  }},
  "item_b": {{
    "name": "Ikkinchi narsa nomi",
    "icon": "B",
    "points": ["Xususiyat 1", "Xususiyat 2", "Xususiyat 3", "Xususiyat 4", "Xususiyat 5"]
  }},
  "common": ["Umumiy xususiyat 1", "Umumiy xususiyat 2"],
  "verdict": "Xulosa yoki tavsiya",
  "footer": "Manba"
}}
Faqat JSON qaytaring.
"""
    data = gpt_json(prompt, system)
    if not data or "item_a" not in data:
        data = {
            "title": topic,
            "item_a": {"name": "A", "icon": "A", "points": ["Xususiyat " + str(i) for i in range(1,6)]},
            "item_b": {"name": "B", "icon": "B", "points": ["Xususiyat " + str(i) for i in range(1,6)]},
            "common": ["Umumiy 1", "Umumiy 2"],
            "verdict": "Xulosa",
            "footer": "Infografika"
        }

    W, H = 1100, 1500
    img = Image.new("RGB", (W, H), color=colors["bg"])
    draw = ImageDraw.Draw(img)

    # Header
    draw_rounded_rect(draw, 0, 0, W, 140, 0, fill=colors["primary"])
    draw.text((W//2, 70), data.get("title", topic), font=get_font(40, bold=True),
              fill=colors["header_fg"], anchor="mm")

    # Column headers
    col_w = (W - 60) // 2
    # A column
    draw_rounded_rect(draw, 30, 160, 30 + col_w, 260, 16, fill=colors["primary"])
    draw.text((30 + col_w//2, 210), data["item_a"]["name"], font=get_font(30, bold=True),
              fill=colors["header_fg"], anchor="mm")
    # B column
    draw_rounded_rect(draw, W - 30 - col_w, 160, W - 30, 260, 16, fill=colors["secondary"])
    draw.text((W - 30 - col_w//2, 210), data["item_b"]["name"], font=get_font(30, bold=True),
              fill=colors["header_fg"], anchor="mm")

    # VS divider
    draw.ellipse([W//2 - 35, 185, W//2 + 35, 255], fill=colors["accent"], outline=colors["primary"], width=3)
    draw.text((W//2, 220), "VS", font=get_font(26, bold=True), fill=colors["primary"], anchor="mm")

    # Points
    y = 290
    a_pts = data["item_a"].get("points", [])[:5]
    b_pts = data["item_b"].get("points", [])[:5]
    for i in range(max(len(a_pts), len(b_pts))):
        row_color = colors["accent"] if i % 2 == 0 else colors["bg"]
        draw_rounded_rect(draw, 30, y, 30 + col_w, y + 75, 10, fill=row_color, outline=colors["light"], outline_width=1)
        if i < len(a_pts):
            draw.text((50, y + 15), "✦", font=get_font(20), fill=colors["primary"])
            draw_wrapped_text(draw, a_pts[i], 80, y + 12, col_w - 60, get_font(20), colors["text"])

        draw_rounded_rect(draw, W - 30 - col_w, y, W - 30, y + 75, 10, fill=row_color, outline=colors["light"], outline_width=1)
        if i < len(b_pts):
            draw.text((W - 30 - col_w + 20, y + 15), "✦", font=get_font(20), fill=colors["secondary"])
            draw_wrapped_text(draw, b_pts[i], W - 30 - col_w + 50, y + 12, col_w - 60, get_font(20), colors["text"])
        y += 85

    # Common
    common = data.get("common", [])
    if common:
        y += 10
        draw_rounded_rect(draw, 30, y, W - 30, y + 50, 10, fill=colors["primary"])
        draw.text((W//2, y + 25), "Umumiy xususiyatlar", font=get_font(24, bold=True),
                  fill=colors["header_fg"], anchor="mm")
        y += 60
        for c in common:
            draw_rounded_rect(draw, 50, y, W - 50, y + 60, 10, fill=colors["accent"], outline=colors["secondary"], outline_width=1)
            draw.text((W//2, y + 30), "⟳  " + c, font=get_font(22), fill=colors["text"], anchor="mm")
            y += 70

    # Verdict
    y += 15
    draw_rounded_rect(draw, 30, y, W - 30, y + 90, 16, fill=colors["primary"])
    draw.text((W//2, y + 20), "Xulosa", font=get_font(22, bold=True), fill=colors["light"], anchor="mm")
    draw_wrapped_text(draw, data.get("verdict", ""), 60, y + 48, W - 120, get_font(20), colors["header_fg"])

    # Footer
    draw_rounded_rect(draw, 0, H - 55, W, H, 0, fill=colors["secondary"])
    draw.text((W//2, H - 28), data.get("footer", ""), font=get_font(18),
              fill=colors["header_fg"], anchor="mm")

    return img


# ─────────────────────────────────────────────
# 4. UMUMIY infografika
# ─────────────────────────────────────────────
def generate_umumiy(topic: str, lang: str, colors: dict) -> Image.Image:
    """Umumiy ma'lumotli infografika — sarlavha, tavsif, asosiy tushunchalar, statistika."""
    system = "Siz infografika mazmuni tayyorlovchi mutaxassissiz. Faqat JSON qaytaring."
    prompt = f"""
Mavzu: "{topic}"
Til: {lang}

JSON strukturasi:
{{
  "title": "Asosiy sarlavha (qisqa, 5-7 so'z)",
  "subtitle": "Qisqa tavsif (1 jumla)",
  "intro": "Kirish matni (2 jumla)",
  "sections": [
    {{"icon": "01", "title": "Bo'lim sarlavhasi (3-4 so'z)", "text": "Qisqa matn (1 jumla)"}},
    {{"icon": "02", "title": "Bo'lim sarlavhasi", "text": "Qisqa matn (1 jumla)"}},
    {{"icon": "03", "title": "Bo'lim sarlavhasi", "text": "Qisqa matn (1 jumla)"}},
    {{"icon": "04", "title": "Bo'lim sarlavhasi", "text": "Qisqa matn (1 jumla)"}}
  ],
  "stats": [
    {{"value": "95%", "label": "Qisqa nom"}},
    {{"value": "2x", "label": "Qisqa nom"}},
    {{"value": "500+", "label": "Qisqa nom"}}
  ],
  "conclusion": "Xulosa matni (1 jumla)",
  "footer": "Manba"
}}
Faqat JSON qaytaring.
"""
    data = gpt_json(prompt, system)
    if not data or "sections" not in data:
        data = {
            "title": topic, "subtitle": "Umumiy ma'lumot",
            "intro": "Bu mavzu haqida umumiy ma'lumot.",
            "sections": [{"icon": str(i), "title": f"Bo'lim {i}", "text": "Tavsif"} for i in range(1, 5)],
            "stats": [{"value": "100%", "label": "Ko'rsatkich"}],
            "conclusion": "Xulosa",
            "footer": "Infografika"
        }

    W = 1100
    # Balandlikni dinamik hisoblash
    sections = data.get("sections", [])[:4]
    sec_rows = (len(sections) // 2 + len(sections) % 2)
    sec_h = 210
    stats_h = 130 if data.get("stats") else 0
    H = 160 + 130 + stats_h + sec_rows * (sec_h + 15) + 130 + 60 + 30
    H = max(H, 1400)

    img = Image.new("RGB", (W, H), color=colors["bg"])
    draw = ImageDraw.Draw(img)

    # Header
    draw_rounded_rect(draw, 0, 0, W, 160, 0, fill=colors["primary"])
    draw.text((W//2, 60), data.get("title", topic), font=get_font(40, bold=True),
              fill=colors["header_fg"], anchor="mm")
    draw.text((W//2, 120), data.get("subtitle", ""), font=get_font(20),
              fill=colors["light"], anchor="mm")

    # Intro
    y = 180
    intro_text = data.get("intro", "")
    intro_lines = len(textwrap.wrap(intro_text, width=70)) + 1
    intro_h = max(80, intro_lines * 30 + 20)
    draw_rounded_rect(draw, 30, y, W - 30, y + intro_h, 14,
                      fill=colors["accent"], outline=colors["secondary"], outline_width=2)
    draw_wrapped_text(draw, intro_text, 55, y + 15, W - 110, get_font(21), colors["text"])
    y += intro_h + 20

    # Stats
    stats = data.get("stats", [])
    if stats:
        stat_w = (W - 60) // len(stats)
        sx = 30
        for stat in stats:
            draw_rounded_rect(draw, sx, y, sx + stat_w - 10, y + 110, 14, fill=colors["primary"])
            draw.text((sx + (stat_w - 10)//2, y + 38), stat.get("value", ""),
                      font=get_font(38, bold=True), fill=colors["header_fg"], anchor="mm")
            label = stat.get("label", "")
            # Labelni qisqartirish agar juda uzun bo'lsa
            if len(label) > 20:
                label = label[:18] + "..."
            draw_wrapped_text(draw, label, sx + 8, y + 68, stat_w - 26, get_font(16), colors["light"])
            sx += stat_w
        y += 130

    # Sections (2x2 grid)
    sec_w = (W - 70) // 2
    for i, sec in enumerate(sections):
        col = i % 2
        row = i // 2
        sx = 30 + col * (sec_w + 10)
        sy = y + row * (sec_h + 15)
        draw_rounded_rect(draw, sx, sy, sx + sec_w, sy + sec_h, 16,
                          fill=colors["accent"], outline=colors["secondary"], outline_width=2)
        # Icon circle
        draw.ellipse([sx + 15, sy + 15, sx + 75, sy + 75], fill=colors["primary"])
        draw.text((sx + 45, sy + 45), sec.get("icon", str(i+1)),
                  font=get_font(26, bold=True), fill=colors["header_fg"], anchor="mm")
        # Title
        draw_wrapped_text(draw, sec.get("title", ""), sx + 90, sy + 15, sec_w - 105,
                          get_font(21, bold=True), colors["primary"])
        draw_wrapped_text(draw, sec.get("text", ""), sx + 20, sy + 85, sec_w - 40,
                          get_font(18), colors["text"])

    y += sec_rows * (sec_h + 15) + 20

    # Conclusion
    conc_text = data.get("conclusion", "")
    conc_lines = len(textwrap.wrap(conc_text, width=65)) + 1
    conc_h = max(100, conc_lines * 28 + 40)
    draw_rounded_rect(draw, 30, y, W - 30, y + conc_h, 16, fill=colors["primary"])
    draw.text((W//2, y + 20), "Xulosa", font=get_font(24, bold=True),
              fill=colors["light"], anchor="mm")
    draw_wrapped_text(draw, conc_text, 55, y + 50, W - 110,
                      get_font(20), colors["header_fg"])
    y += conc_h + 15

    # Footer
    draw_rounded_rect(draw, 0, y, W, y + 55, 0, fill=colors["secondary"])
    draw.text((W//2, y + 28), data.get("footer", ""), font=get_font(18),
              fill=colors["header_fg"], anchor="mm")

    # Rasmni to'g'ri o'lchamga kesish
    final_h = y + 55
    img = img.crop((0, 0, W, final_h))
    return img


# ─────────────────────────────────────────────
# Asosiy generatsiya funksiyasi
# ─────────────────────────────────────────────
def generate_infografika(
    topic: str,
    infotype: str,
    lang: str,
    color_scheme: str,
    output_path: str = None
) -> str:
    """
    Infografika yaratadi va faylga saqlaydi.

    Args:
        topic: Mavzu
        infotype: 'statistik' | 'jarayon' | 'taqqoslash' | 'umumiy'
        lang: Til (O'zbek, Rus, Ingliz va h.k.)
        color_scheme: "ko'k" | "yashil" | "qizil" | "binafsha" | "to'q sariq"
        output_path: Saqlash yo'li (None bo'lsa temp fayl)

    Returns:
        Saqlangan fayl yo'li
    """
    colors = COLOR_SCHEMES.get(color_scheme, COLOR_SCHEMES["ko'k"])

    generators = {
        "statistik":  generate_statistik,
        "jarayon":    generate_jarayon,
        "taqqoslash": generate_taqqoslash,
        "umumiy":     generate_umumiy,
    }
    gen_func = generators.get(infotype, generate_umumiy)

    img = gen_func(topic, lang, colors)

    if output_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        output_path = tmp.name
        tmp.close()

    img.save(output_path, "PNG", quality=95)
    return output_path
