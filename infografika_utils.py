"""
infografika_utils.py — Professional infografika generatsiya moduli
Yuqori sifatli, ko'p ustunli, ikonkalar va diagrammalar bilan.
"""
import os
import io
import json
import logging
import textwrap
import tempfile
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Circle, Wedge, FancyArrowPatch
from matplotlib.gridspec import GridSpec
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from openai import OpenAI

logger = logging.getLogger(__name__)
client = OpenAI()

# ─── Rang sxemalari ───────────────────────────────────────────────────────────
COLOR_SCHEMES = {
    "ko'k": {
        "primary":   "#1565C0",
        "secondary": "#42A5F5",
        "accent":    "#FFC107",
        "light":     "#E3F2FD",
        "dark":      "#0D47A1",
        "text":      "#1A237E",
        "white":     "#FFFFFF",
        "card":      "#BBDEFB",
    },
    "yashil": {
        "primary":   "#2E7D32",
        "secondary": "#66BB6A",
        "accent":    "#FF9800",
        "light":     "#E8F5E9",
        "dark":      "#1B5E20",
        "text":      "#1B5E20",
        "white":     "#FFFFFF",
        "card":      "#C8E6C9",
    },
    "qizil": {
        "primary":   "#C62828",
        "secondary": "#EF5350",
        "accent":    "#FFC107",
        "light":     "#FFEBEE",
        "dark":      "#B71C1C",
        "text":      "#B71C1C",
        "white":     "#FFFFFF",
        "card":      "#FFCDD2",
    },
    "binafsha": {
        "primary":   "#6A1B9A",
        "secondary": "#AB47BC",
        "accent":    "#FF9800",
        "light":     "#F3E5F5",
        "dark":      "#4A148C",
        "text":      "#4A148C",
        "white":     "#FFFFFF",
        "card":      "#E1BEE7",
    },
    "to'q sariq": {
        "primary":   "#E65100",
        "secondary": "#FFA726",
        "accent":    "#1565C0",
        "light":     "#FFF3E0",
        "dark":      "#BF360C",
        "text":      "#BF360C",
        "white":     "#FFFFFF",
        "card":      "#FFE0B2",
    },
}

# ─── GPT dan ma'lumot olish ────────────────────────────────────────────────────
def _get_infografika_data(topic: str, ig_type: str, language: str) -> dict:
    """GPT dan infografika uchun strukturali ma'lumot oladi."""
    lang_map = {
        "O'zbek tili": "O'zbek tilida",
        "Ingliz tili": "English",
        "Rus tili":    "На русском языке",
        "Nemis tili":  "Auf Deutsch",
    }
    lang_instruction = lang_map.get(language, "O'zbek tilida")

    if ig_type == "statistik":
        prompt = f"""
{lang_instruction} "{topic}" mavzusida statistik infografika uchun ma'lumot ber.
JSON formatida qaytargin (boshqa hech narsa yozma):
{{
  "title": "Katta sarlavha (4-7 so'z, BOSH HARFLAR)",
  "subtitle": "Kichik tavsif (10-15 so'z)",
  "sections": [
    {{
      "title": "Bo'lim sarlavhasi (2-4 so'z)",
      "icon": "emoji",
      "items": ["qisqa fakt 1", "qisqa fakt 2", "qisqa fakt 3"]
    }},
    {{
      "title": "Bo'lim sarlavhasi",
      "icon": "emoji",
      "chart_data": {{
        "labels": ["A", "B", "C", "D"],
        "values": [35, 25, 25, 15],
        "center_text": "Asosiy"
      }}
    }},
    {{
      "title": "Bo'lim sarlavhasi",
      "icon": "emoji",
      "stats": [
        {{"value": "85%", "label": "qisqa tavsif"}},
        {{"value": "3x", "label": "qisqa tavsif"}},
        {{"value": "500+", "label": "qisqa tavsif"}}
      ]
    }},
    {{
      "title": "Bo'lim sarlavhasi",
      "icon": "emoji",
      "items": ["fakt 1", "fakt 2", "fakt 3"]
    }}
  ],
  "footer": "Manba: qisqa manba nomi"
}}
"""
    elif ig_type == "jarayon":
        prompt = f"""
{lang_instruction} "{topic}" mavzusida jarayon/qadamlar infografika uchun ma'lumot ber.
JSON formatida qaytargin:
{{
  "title": "Katta sarlavha (4-7 so'z, BOSH HARFLAR)",
  "subtitle": "Kichik tavsif (10-15 so'z)",
  "steps": [
    {{"number": "01", "title": "Qadam sarlavhasi", "icon": "emoji", "description": "20-25 so'zlik tavsif"}},
    {{"number": "02", "title": "Qadam sarlavhasi", "icon": "emoji", "description": "20-25 so'zlik tavsif"}},
    {{"number": "03", "title": "Qadam sarlavhasi", "icon": "emoji", "description": "20-25 so'zlik tavsif"}},
    {{"number": "04", "title": "Qadam sarlavhasi", "icon": "emoji", "description": "20-25 so'zlik tavsif"}},
    {{"number": "05", "title": "Qadam sarlavhasi", "icon": "emoji", "description": "20-25 so'zlik tavsif"}},
    {{"number": "06", "title": "Qadam sarlavhasi", "icon": "emoji", "description": "20-25 so'zlik tavsif"}}
  ],
  "key_stats": [
    {{"value": "raqam", "label": "tavsif"}},
    {{"value": "raqam", "label": "tavsif"}},
    {{"value": "raqam", "label": "tavsif"}}
  ],
  "footer": "Manba: qisqa manba nomi"
}}
"""
    elif ig_type == "taqqoslash":
        prompt = f"""
{lang_instruction} "{topic}" mavzusida taqqoslash infografika uchun ma'lumot ber.
JSON formatida qaytargin:
{{
  "title": "Katta sarlavha (4-7 so'z, BOSH HARFLAR)",
  "subtitle": "Kichik tavsif (10-15 so'z)",
  "left": {{
    "name": "1-tomonning nomi",
    "icon": "emoji",
    "color_hint": "ijobiy/salbiy",
    "points": [
      {{"label": "mezon", "value": "qiymat"}},
      {{"label": "mezon", "value": "qiymat"}},
      {{"label": "mezon", "value": "qiymat"}},
      {{"label": "mezon", "value": "qiymat"}}
    ]
  }},
  "right": {{
    "name": "2-tomonning nomi",
    "icon": "emoji",
    "color_hint": "ijobiy/salbiy",
    "points": [
      {{"label": "mezon", "value": "qiymat"}},
      {{"label": "mezon", "value": "qiymat"}},
      {{"label": "mezon", "value": "qiymat"}},
      {{"label": "mezon", "value": "qiymat"}}
    ]
  }},
  "chart_data": {{
    "labels": ["Mezon 1", "Mezon 2", "Mezon 3", "Mezon 4"],
    "left_values": [80, 60, 90, 70],
    "right_values": [60, 85, 50, 80]
  }},
  "verdict": "Qisqa xulosa (15-20 so'z)",
  "footer": "Manba: qisqa manba nomi"
}}
"""
    else:  # umumiy
        prompt = f"""
{lang_instruction} "{topic}" mavzusida umumiy infografika uchun ma'lumot ber.
JSON formatida qaytargin:
{{
  "title": "Katta sarlavha (4-7 so'z, BOSH HARFLAR)",
  "subtitle": "Kichik tavsif (10-15 so'z)",
  "intro": "Kirish matni (25-30 so'z)",
  "sections": [
    {{
      "title": "Bo'lim sarlavhasi",
      "icon": "emoji",
      "content": "20-25 so'zlik matn"
    }},
    {{
      "title": "Bo'lim sarlavhasi",
      "icon": "emoji",
      "content": "20-25 so'zlik matn"
    }},
    {{
      "title": "Bo'lim sarlavhasi",
      "icon": "emoji",
      "content": "20-25 so'zlik matn"
    }},
    {{
      "title": "Bo'lim sarlavhasi",
      "icon": "emoji",
      "content": "20-25 so'zlik matn"
    }}
  ],
  "key_facts": [
    {{"value": "raqam/fakt", "label": "qisqa tavsif"}},
    {{"value": "raqam/fakt", "label": "qisqa tavsif"}},
    {{"value": "raqam/fakt", "label": "qisqa tavsif"}}
  ],
  "conclusion": "Xulosa matni (20-25 so'z)",
  "footer": "Manba: qisqa manba nomi"
}}
"""

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=1200,
        )
        raw = resp.choices[0].message.content.strip()
        # JSON ni tozalash
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        return json.loads(raw)
    except Exception as e:
        logger.error(f"GPT xatosi: {e}")
        return {}


# ─── PIL yordamida gradient fon ───────────────────────────────────────────────
def _make_gradient_bg(width: int, height: int, color1: str, color2: str) -> Image.Image:
    """Yuqoridan pastga gradient fon yaratadi."""
    img = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(img)
    r1, g1, b1 = int(color1[1:3], 16), int(color1[3:5], 16), int(color1[5:7], 16)
    r2, g2, b2 = int(color2[1:3], 16), int(color2[3:5], 16), int(color2[5:7], 16)
    for y in range(height):
        t = y / height
        r = int(r1 + (r2 - r1) * t)
        g = int(g1 + (g2 - g1) * t)
        b = int(b1 + (b2 - b1) * t)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return img


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))


def _hex_to_rgb_int(hex_color: str) -> tuple:
    h = hex_color.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


# ─── Matnni o'rashga yordam ───────────────────────────────────────────────────
def _wrap(text: str, width: int = 35) -> str:
    return '\n'.join(textwrap.wrap(str(text), width=width))


# ─── STATISTIK infografika ────────────────────────────────────────────────────
def _draw_statistik(data: dict, colors: dict, out_path: str) -> str:
    W, H = 1400, 900
    fig = plt.figure(figsize=(W/100, H/100), dpi=100, facecolor=colors["light"])

    # Header
    ax_header = fig.add_axes([0, 0.85, 1, 0.15])
    ax_header.set_facecolor(colors["primary"])
    ax_header.set_xlim(0, 1); ax_header.set_ylim(0, 1)
    ax_header.axis('off')
    title = data.get("title", "INFOGRAFIKA")
    subtitle = data.get("subtitle", "")
    ax_header.text(0.5, 0.65, title, ha='center', va='center',
                   fontsize=28, fontweight='bold', color=colors["white"],
                   fontfamily='DejaVu Sans')
    ax_header.text(0.5, 0.25, subtitle, ha='center', va='center',
                   fontsize=13, color=colors["card"],
                   fontfamily='DejaVu Sans')

    sections = data.get("sections", [])
    n = len(sections)
    col_w = 1.0 / max(n, 1)

    for i, sec in enumerate(sections[:4]):
        x0 = i * col_w + 0.01
        ax = fig.add_axes([x0, 0.06, col_w - 0.02, 0.77])
        ax.set_facecolor(colors["white"])
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.axis('off')

        # Card border
        rect = FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                               boxstyle="round,pad=0.02",
                               facecolor=colors["white"],
                               edgecolor=colors["secondary"], linewidth=2)
        ax.add_patch(rect)

        # Section header
        hdr = FancyBboxPatch((0.02, 0.82), 0.96, 0.16,
                              boxstyle="round,pad=0.01",
                              facecolor=colors["primary"],
                              edgecolor='none')
        ax.add_patch(hdr)

        icon = sec.get("icon", "📌")
        stitle = sec.get("title", f"Bo'lim {i+1}")
        ax.text(0.5, 0.905, f"{icon}  {stitle}",
                ha='center', va='center',
                fontsize=12, fontweight='bold', color=colors["white"])

        # Content
        if "chart_data" in sec:
            cd = sec["chart_data"]
            labels = cd.get("labels", [])
            values = cd.get("values", [])
            center_text = cd.get("center_text", "")
            if labels and values:
                ax_donut = fig.add_axes([x0 + 0.02, 0.12, col_w - 0.06, 0.65])
                ax_donut.set_aspect('equal')
                pie_colors = [colors["primary"], colors["secondary"],
                               colors["accent"], colors["card"]]
                wedges, texts, autotexts = ax_donut.pie(
                    values, labels=None, autopct='%1.0f%%',
                    colors=pie_colors[:len(values)],
                    wedgeprops=dict(width=0.5, edgecolor='white', linewidth=2),
                    pctdistance=0.75, startangle=90
                )
                for at in autotexts:
                    at.set_fontsize(9)
                    at.set_color('white')
                    at.set_fontweight('bold')
                ax_donut.text(0, 0, center_text, ha='center', va='center',
                              fontsize=11, fontweight='bold',
                              color=colors["text"])
                # Legend
                for j, (lbl, val) in enumerate(zip(labels, values)):
                    ax_donut.text(-1.6, 0.6 - j * 0.35,
                                  f"■ {lbl}: {val}%",
                                  fontsize=8, color=colors["text"],
                                  fontfamily='DejaVu Sans')
                ax_donut.axis('off')

        elif "stats" in sec:
            stats = sec["stats"]
            for j, st in enumerate(stats[:3]):
                y_pos = 0.72 - j * 0.22
                bg = FancyBboxPatch((0.08, y_pos - 0.08), 0.84, 0.18,
                                    boxstyle="round,pad=0.01",
                                    facecolor=colors["card"],
                                    edgecolor='none')
                ax.add_patch(bg)
                ax.text(0.5, y_pos + 0.02, st.get("value", ""),
                        ha='center', va='center',
                        fontsize=20, fontweight='bold', color=colors["primary"])
                ax.text(0.5, y_pos - 0.05, _wrap(st.get("label", ""), 25),
                        ha='center', va='center',
                        fontsize=9, color=colors["text"])

        elif "items" in sec:
            items = sec.get("items", [])
            for j, item in enumerate(items[:5]):
                y_pos = 0.73 - j * 0.15
                ax.text(0.08, y_pos, "▶", fontsize=11, color=colors["accent"],
                        va='center')
                ax.text(0.18, y_pos, _wrap(item, 28),
                        fontsize=10, color=colors["text"], va='center',
                        fontfamily='DejaVu Sans')

    # Footer
    ax_footer = fig.add_axes([0, 0, 1, 0.06])
    ax_footer.set_facecolor(colors["dark"])
    ax_footer.axis('off')
    ax_footer.text(0.5, 0.5, data.get("footer", ""),
                   ha='center', va='center',
                   fontsize=11, color=colors["card"])

    plt.savefig(out_path, dpi=100, bbox_inches='tight',
                facecolor=colors["light"], edgecolor='none')
    plt.close(fig)
    return out_path


# ─── JARAYON infografika ──────────────────────────────────────────────────────
def _draw_jarayon(data: dict, colors: dict, out_path: str) -> str:
    W, H = 1400, 950
    fig = plt.figure(figsize=(W/100, H/100), dpi=100, facecolor=colors["light"])

    # Header
    ax_h = fig.add_axes([0, 0.88, 1, 0.12])
    ax_h.set_facecolor(colors["primary"])
    ax_h.axis('off')
    ax_h.set_xlim(0, 1); ax_h.set_ylim(0, 1)
    ax_h.text(0.5, 0.65, data.get("title", "JARAYON"),
              ha='center', va='center', fontsize=26, fontweight='bold',
              color=colors["white"])
    ax_h.text(0.5, 0.25, data.get("subtitle", ""),
              ha='center', va='center', fontsize=12, color=colors["card"])

    steps = data.get("steps", [])
    n = len(steps)
    cols = 3
    rows = math.ceil(n / cols)
    step_w = 1.0 / cols
    step_h = 0.82 / rows

    for idx, step in enumerate(steps[:6]):
        col = idx % cols
        row = idx // cols
        x0 = col * step_w + 0.01
        y0 = 0.06 + (rows - 1 - row) * step_h + 0.01

        ax = fig.add_axes([x0, y0, step_w - 0.02, step_h - 0.02])
        ax.set_facecolor(colors["white"])
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.axis('off')

        # Card
        rect = FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                               boxstyle="round,pad=0.02",
                               facecolor=colors["white"],
                               edgecolor=colors["secondary"], linewidth=2)
        ax.add_patch(rect)

        # Number circle
        circle = Circle((0.15, 0.82), 0.12,
                         facecolor=colors["primary"], edgecolor='none',
                         transform=ax.transData)
        ax.add_patch(circle)
        ax.text(0.15, 0.82, step.get("number", str(idx+1)),
                ha='center', va='center',
                fontsize=14, fontweight='bold', color=colors["white"])

        # Icon + Title
        icon = step.get("icon", "📌")
        stitle = step.get("title", "")
        ax.text(0.35, 0.85, f"{icon}", fontsize=18, va='center')
        ax.text(0.55, 0.82, _wrap(stitle, 18),
                ha='center', va='center',
                fontsize=11, fontweight='bold', color=colors["text"])

        # Divider
        ax.axhline(y=0.68, xmin=0.05, xmax=0.95,
                   color=colors["card"], linewidth=1.5)

        # Description
        desc = step.get("description", "")
        ax.text(0.5, 0.38, _wrap(desc, 32),
                ha='center', va='center',
                fontsize=9.5, color=colors["text"],
                linespacing=1.5)

    # Key stats bar
    key_stats = data.get("key_stats", [])
    if key_stats:
        ax_stats = fig.add_axes([0, 0, 1, 0.06])
        ax_stats.set_facecolor(colors["dark"])
        ax_stats.axis('off')
        ax_stats.set_xlim(0, 1); ax_stats.set_ylim(0, 1)
        n_stats = len(key_stats[:3])
        for j, ks in enumerate(key_stats[:3]):
            x = (j + 0.5) / n_stats
            ax_stats.text(x, 0.65, ks.get("value", ""),
                          ha='center', va='center',
                          fontsize=16, fontweight='bold', color=colors["accent"])
            ax_stats.text(x, 0.25, ks.get("label", ""),
                          ha='center', va='center',
                          fontsize=9, color=colors["card"])
    else:
        ax_f = fig.add_axes([0, 0, 1, 0.06])
        ax_f.set_facecolor(colors["dark"])
        ax_f.axis('off')
        ax_f.text(0.5, 0.5, data.get("footer", ""),
                  ha='center', va='center', fontsize=11, color=colors["card"])

    plt.savefig(out_path, dpi=100, bbox_inches='tight',
                facecolor=colors["light"], edgecolor='none')
    plt.close(fig)
    return out_path


# ─── TAQQOSLASH infografika ───────────────────────────────────────────────────
def _draw_taqqoslash(data: dict, colors: dict, out_path: str) -> str:
    W, H = 1400, 900
    fig = plt.figure(figsize=(W/100, H/100), dpi=100, facecolor=colors["light"])

    # Header
    ax_h = fig.add_axes([0, 0.88, 1, 0.12])
    ax_h.set_facecolor(colors["primary"])
    ax_h.axis('off')
    ax_h.set_xlim(0, 1); ax_h.set_ylim(0, 1)
    ax_h.text(0.5, 0.65, data.get("title", "TAQQOSLASH"),
              ha='center', va='center', fontsize=26, fontweight='bold',
              color=colors["white"])
    ax_h.text(0.5, 0.25, data.get("subtitle", ""),
              ha='center', va='center', fontsize=12, color=colors["card"])

    left = data.get("left", {})
    right = data.get("right", {})
    chart_data = data.get("chart_data", {})

    # Left panel
    ax_l = fig.add_axes([0.01, 0.08, 0.32, 0.78])
    ax_l.set_facecolor(colors["white"])
    ax_l.set_xlim(0, 1); ax_l.set_ylim(0, 1)
    ax_l.axis('off')
    rect_l = FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                             boxstyle="round,pad=0.02",
                             facecolor=colors["white"],
                             edgecolor=colors["primary"], linewidth=3)
    ax_l.add_patch(rect_l)

    hdr_l = FancyBboxPatch((0.02, 0.84), 0.96, 0.14,
                            boxstyle="round,pad=0.01",
                            facecolor=colors["primary"], edgecolor='none')
    ax_l.add_patch(hdr_l)
    ax_l.text(0.5, 0.915, f"{left.get('icon','🔵')}  {left.get('name','')}",
              ha='center', va='center',
              fontsize=13, fontweight='bold', color=colors["white"])

    for j, pt in enumerate(left.get("points", [])[:5]):
        y = 0.72 - j * 0.16
        bg = FancyBboxPatch((0.05, y - 0.06), 0.90, 0.12,
                             boxstyle="round,pad=0.01",
                             facecolor=colors["light"], edgecolor='none')
        ax_l.add_patch(bg)
        ax_l.text(0.12, y, "✓", fontsize=12, color=colors["primary"], va='center')
        ax_l.text(0.22, y + 0.025, pt.get("label", ""),
                  fontsize=9, color=colors["text"], fontweight='bold')
        ax_l.text(0.22, y - 0.025, pt.get("value", ""),
                  fontsize=10, color=colors["primary"], fontweight='bold')

    # Right panel
    ax_r = fig.add_axes([0.67, 0.08, 0.32, 0.78])
    ax_r.set_facecolor(colors["white"])
    ax_r.set_xlim(0, 1); ax_r.set_ylim(0, 1)
    ax_r.axis('off')
    rect_r = FancyBboxPatch((0.02, 0.02), 0.96, 0.96,
                             boxstyle="round,pad=0.02",
                             facecolor=colors["white"],
                             edgecolor=colors["secondary"], linewidth=3)
    ax_r.add_patch(rect_r)

    hdr_r = FancyBboxPatch((0.02, 0.84), 0.96, 0.14,
                            boxstyle="round,pad=0.01",
                            facecolor=colors["secondary"], edgecolor='none')
    ax_r.add_patch(hdr_r)
    ax_r.text(0.5, 0.915, f"{right.get('icon','🟢')}  {right.get('name','')}",
              ha='center', va='center',
              fontsize=13, fontweight='bold', color=colors["white"])

    for j, pt in enumerate(right.get("points", [])[:5]):
        y = 0.72 - j * 0.16
        bg = FancyBboxPatch((0.05, y - 0.06), 0.90, 0.12,
                             boxstyle="round,pad=0.01",
                             facecolor=colors["light"], edgecolor='none')
        ax_r.add_patch(bg)
        ax_r.text(0.12, y, "✓", fontsize=12, color=colors["secondary"], va='center')
        ax_r.text(0.22, y + 0.025, pt.get("label", ""),
                  fontsize=9, color=colors["text"], fontweight='bold')
        ax_r.text(0.22, y - 0.025, pt.get("value", ""),
                  fontsize=10, color=colors["secondary"], fontweight='bold')

    # Center chart
    ax_c = fig.add_axes([0.34, 0.12, 0.32, 0.72])
    ax_c.set_facecolor(colors["light"])
    ax_c.set_xlim(0, 1); ax_c.set_ylim(0, 1)
    ax_c.axis('off')

    if chart_data:
        labels = chart_data.get("labels", [])
        lv = chart_data.get("left_values", [])
        rv = chart_data.get("right_values", [])
        n_bars = len(labels)
        bar_h = 0.65 / max(n_bars, 1)

        for j, (lbl, lval, rval) in enumerate(zip(labels, lv, rv)):
            y = 0.85 - j * bar_h
            ax_c.text(0.5, y, lbl, ha='center', va='center',
                      fontsize=9, fontweight='bold', color=colors["text"])
            # Left bar
            bar_len_l = lval / 100 * 0.45
            ax_c.barh(y - 0.04, bar_len_l, height=0.04,
                      left=0.5 - bar_len_l,
                      color=colors["primary"], alpha=0.8)
            ax_c.text(0.5 - bar_len_l - 0.02, y - 0.04, f"{lval}%",
                      ha='right', va='center', fontsize=8,
                      color=colors["primary"], fontweight='bold')
            # Right bar
            bar_len_r = rval / 100 * 0.45
            ax_c.barh(y - 0.04, bar_len_r, height=0.04,
                      left=0.5,
                      color=colors["secondary"], alpha=0.8)
            ax_c.text(0.5 + bar_len_r + 0.02, y - 0.04, f"{rval}%",
                      ha='left', va='center', fontsize=8,
                      color=colors["secondary"], fontweight='bold')

    # VS badge
    circle_vs = Circle((0.5, 0.5), 0.12,
                        facecolor=colors["accent"], edgecolor='white',
                        linewidth=3, zorder=5)
    ax_c.add_patch(circle_vs)
    ax_c.text(0.5, 0.5, "VS", ha='center', va='center',
              fontsize=16, fontweight='bold', color='white', zorder=6)

    # Verdict
    verdict = data.get("verdict", "")
    if verdict:
        ax_v = fig.add_axes([0.01, 0.01, 0.98, 0.07])
        ax_v.set_facecolor(colors["dark"])
        ax_v.axis('off')
        ax_v.text(0.5, 0.5, f"💡 {verdict}",
                  ha='center', va='center',
                  fontsize=11, color=colors["white"])

    plt.savefig(out_path, dpi=100, bbox_inches='tight',
                facecolor=colors["light"], edgecolor='none')
    plt.close(fig)
    return out_path


# ─── UMUMIY infografika ───────────────────────────────────────────────────────
def _draw_umumiy(data: dict, colors: dict, out_path: str) -> str:
    W, H = 1400, 950
    fig = plt.figure(figsize=(W/100, H/100), dpi=100, facecolor=colors["light"])

    # Header
    ax_h = fig.add_axes([0, 0.88, 1, 0.12])
    ax_h.set_facecolor(colors["primary"])
    ax_h.axis('off')
    ax_h.set_xlim(0, 1); ax_h.set_ylim(0, 1)
    ax_h.text(0.5, 0.65, data.get("title", "INFOGRAFIKA"),
              ha='center', va='center', fontsize=26, fontweight='bold',
              color=colors["white"])
    ax_h.text(0.5, 0.25, data.get("subtitle", ""),
              ha='center', va='center', fontsize=12, color=colors["card"])

    # Intro box
    intro = data.get("intro", "")
    if intro:
        ax_intro = fig.add_axes([0.02, 0.77, 0.96, 0.10])
        ax_intro.set_facecolor(colors["card"])
        ax_intro.set_xlim(0, 1); ax_intro.set_ylim(0, 1)
        ax_intro.axis('off')
        rect_i = FancyBboxPatch((0.01, 0.05), 0.98, 0.90,
                                 boxstyle="round,pad=0.02",
                                 facecolor=colors["card"],
                                 edgecolor=colors["secondary"], linewidth=2)
        ax_intro.add_patch(rect_i)
        ax_intro.text(0.5, 0.5, _wrap(intro, 90),
                      ha='center', va='center',
                      fontsize=11, color=colors["text"],
                      linespacing=1.5)

    # 4 sections (2x2 grid)
    sections = data.get("sections", [])
    positions = [
        [0.02, 0.40, 0.47, 0.35],
        [0.51, 0.40, 0.47, 0.35],
        [0.02, 0.03, 0.47, 0.35],
        [0.51, 0.03, 0.47, 0.35],
    ]
    for i, (sec, pos) in enumerate(zip(sections[:4], positions)):
        ax = fig.add_axes(pos)
        ax.set_facecolor(colors["white"])
        ax.set_xlim(0, 1); ax.set_ylim(0, 1)
        ax.axis('off')

        rect = FancyBboxPatch((0.01, 0.01), 0.98, 0.98,
                               boxstyle="round,pad=0.02",
                               facecolor=colors["white"],
                               edgecolor=colors["secondary"], linewidth=2)
        ax.add_patch(rect)

        # Icon circle
        icon_circle = Circle((0.10, 0.82), 0.09,
                              facecolor=colors["primary"], edgecolor='none')
        ax.add_patch(icon_circle)
        ax.text(0.10, 0.82, sec.get("icon", "📌"),
                ha='center', va='center', fontsize=16)

        # Title
        ax.text(0.25, 0.85, _wrap(sec.get("title", ""), 30),
                ha='left', va='center',
                fontsize=12, fontweight='bold', color=colors["primary"])

        # Divider
        ax.axhline(y=0.70, xmin=0.03, xmax=0.97,
                   color=colors["card"], linewidth=2)

        # Content
        content = sec.get("content", "")
        ax.text(0.5, 0.38, _wrap(content, 45),
                ha='center', va='center',
                fontsize=10, color=colors["text"],
                linespacing=1.6)

    # Key facts bar
    key_facts = data.get("key_facts", [])
    if key_facts:
        # Replace bottom sections with key facts if sections < 4
        pass

    # Conclusion
    conclusion = data.get("conclusion", "")
    if conclusion and len(sections) < 4:
        ax_con = fig.add_axes([0.02, 0.03, 0.96, 0.35])
        ax_con.set_facecolor(colors["white"])
        ax_con.set_xlim(0, 1); ax_con.set_ylim(0, 1)
        ax_con.axis('off')
        rect_c = FancyBboxPatch((0.01, 0.01), 0.98, 0.98,
                                 boxstyle="round,pad=0.02",
                                 facecolor=colors["white"],
                                 edgecolor=colors["primary"], linewidth=2)
        ax_con.add_patch(rect_c)
        ax_con.text(0.5, 0.65, "📝 Xulosa",
                    ha='center', va='center',
                    fontsize=13, fontweight='bold', color=colors["primary"])
        ax_con.text(0.5, 0.35, _wrap(conclusion, 80),
                    ha='center', va='center',
                    fontsize=10, color=colors["text"], linespacing=1.5)

    # Footer with key facts
    ax_f = fig.add_axes([0, 0, 1, 0.03])
    ax_f.set_facecolor(colors["dark"])
    ax_f.axis('off')
    footer_text = data.get("footer", "")
    if key_facts:
        facts_str = "   |   ".join([f"{kf.get('value','')} — {kf.get('label','')}" for kf in key_facts[:3]])
        footer_text = f"📊 {facts_str}   |   {footer_text}"
    ax_f.text(0.5, 0.5, footer_text,
              ha='center', va='center',
              fontsize=9, color=colors["card"])

    plt.savefig(out_path, dpi=100, bbox_inches='tight',
                facecolor=colors["light"], edgecolor='none')
    plt.close(fig)
    return out_path


# ─── Asosiy funksiya ──────────────────────────────────────────────────────────
def generate_infografika(
    topic: str,
    ig_type: str,
    language: str,
    color_scheme: str,
    out_path: str = None,
) -> str:
    """
    Professional infografika yaratadi.
    ig_type: statistik | jarayon | taqqoslash | umumiy
    color_scheme: ko'k | yashil | qizil | binafsha | to'q sariq
    """
    if out_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        out_path = tmp.name
        tmp.close()

    colors = COLOR_SCHEMES.get(color_scheme, COLOR_SCHEMES["ko'k"])

    logger.info(f"Infografika yaratilmoqda: {topic} | {ig_type} | {language} | {color_scheme}")
    data = _get_infografika_data(topic, ig_type, language)

    if not data:
        # Fallback
        data = {
            "title": topic.upper(),
            "subtitle": f"{topic} haqida umumiy ma'lumot",
            "sections": [
                {"title": "Ma'lumot", "icon": "📌",
                 "content": f"{topic} bo'yicha ma'lumot tayyorlanmoqda."}
            ],
            "footer": "Ma'lumot tayyorlanmoqda"
        }

    if ig_type == "statistik":
        return _draw_statistik(data, colors, out_path)
    elif ig_type == "jarayon":
        return _draw_jarayon(data, colors, out_path)
    elif ig_type == "taqqoslash":
        return _draw_taqqoslash(data, colors, out_path)
    else:
        return _draw_umumiy(data, colors, out_path)


# ─────────────────────────────────────────────
# HD Infografika — DALL-E 3 bilan
# ─────────────────────────────────────────────

def generate_infografika_hd(
    topic: str,
    ig_type: str,
    language: str,
    color_scheme: str,
    out_path: str = None,
) -> str:
    """
    HD infografika yaratadi (DALL-E 3 orqali).
    Avval GPT mavzu bo'yicha tarkib tayyorlaydi,
    keyin DALL-E 3 professional infografika rasmi yaratadi.
    """
    import requests as req_lib
    from openai import OpenAI as _OpenAI

    # DALL-E 3 uchun alohida client (to'g'ridan-to'g'ri OpenAI API)
    dalle_client = _OpenAI(
        api_key=os.environ.get("OPENAI_API_KEY"),
        base_url="https://api.openai.com/v1",
    )

    if out_path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        out_path = tmp.name
        tmp.close()

    # Tur nomlarini tarjima qilish
    type_names_en = {
        "statistik":  "statistical (with numbers, percentages, charts)",
        "jarayon":    "process/steps (step-by-step guide)",
        "taqqoslash": "comparison (comparing two things side by side)",
        "umumiy":     "general informational",
    }
    type_desc = type_names_en.get(ig_type, "general informational")

    # Rang sxemasi
    color_map = {
        "ko'k":       "blue and white color scheme",
        "yashil":     "green and white color scheme",
        "qizil":      "red and white color scheme",
        "binafsha":   "purple and white color scheme",
        "to'q sariq": "orange and yellow color scheme",
    }
    color_desc = color_map.get(color_scheme, "blue and white color scheme")

    # Til
    lang_map = {
        "O'zbek tili": "Uzbek",
        "Ingliz tili": "English",
        "Rus tili":    "Russian",
        "Nemis tili":  "German",
    }
    lang_en = lang_map.get(language, "Uzbek")

    # GPT orqali infografika uchun asosiy ma'lumotlarni tayyorlash
    try:
        content_resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": (
                    f"You are an infographic content expert. "
                    f"Create concise, factual content for a {type_desc} infographic "
                    f"about the given topic in {lang_en} language. "
                    f"Return ONLY a JSON with: "
                    f"title (short, max 8 words, in {lang_en}), "
                    f"subtitle (max 12 words, in {lang_en}), "
                    f"key_facts (list of 4-5 short facts, each max 10 words, in {lang_en}), "
                    f"statistics (list of 3-4 items with 'label' and 'value' keys, in {lang_en}). "
                )},
                {"role": "user", "content": f"Topic: {topic}"}
            ],
            response_format={"type": "json_object"},
            max_tokens=500,
            temperature=0.7,
        )
        content_data = json.loads(content_resp.choices[0].message.content)
    except Exception as e:
        logger.warning(f"GPT content generation failed: {e}")
        content_data = {
            "title": topic,
            "subtitle": f"Key information about {topic}",
            "key_facts": [f"Important fact about {topic}"],
            "statistics": [{"label": "Data", "value": "100%"}],
        }

    title = content_data.get("title", topic)
    subtitle = content_data.get("subtitle", "")
    key_facts = content_data.get("key_facts", [])
    statistics = content_data.get("statistics", [])

    # DALL-E 3 uchun prompt yaratish
    facts_text = " | ".join(key_facts[:4]) if key_facts else ""
    stats_text = ", ".join([f"{s.get('value','')} {s.get('label','')}" for s in statistics[:3]])

    dalle_prompt = (
        f"Create a professional, modern {type_desc} infographic poster about '{topic}'. "
        f"Language for all text: {lang_en}. Color scheme: {color_desc}. "
        f"Title text: '{title}'. Subtitle: '{subtitle}'. "
        f"Include these key facts as text elements in the infographic: {facts_text}. "
        f"Include these statistics visually: {stats_text}. "
        f"Style: clean, corporate, data-driven, high contrast, "
        f"with icons, charts, and visual elements. "
        f"Layout: wide horizontal format (landscape), multiple columns, "
        f"professional typography, no watermarks, no borders around the whole image. "
        f"Make it look like a real professional infographic with "
        f"clear sections, visual hierarchy, and beautiful design. "
        f"All text in the infographic must be in {lang_en} language only."
    )

    logger.info(f"DALL-E 3 HD infografika yaratilmoqda: {topic}")

    # DALL-E 3 bilan rasm yaratish
    img_resp = dalle_client.images.generate(
        model="dall-e-3",
        prompt=dalle_prompt,
        size="1792x1024",
        quality="standard",
        n=1,
    )

    image_url = img_resp.data[0].url

    # Rasmni yuklab olish
    response = req_lib.get(image_url, timeout=60)
    response.raise_for_status()

    with open(out_path, "wb") as f:
        f.write(response.content)

    logger.info(f"HD infografika yaratildi: {out_path}")
    return out_path
