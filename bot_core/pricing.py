"""Bot xizmatlari uchun markazlashgan narx va foydalanuvchi limitlari."""

SERVICE_PRICES = {
    "slayd": 2500,
    "slayd_gold_10": 2500,
    "slayd_gold_20": 3000,
    "slayd_gold_30": 4000,
    "slayd_plat_10": 3000,
    "slayd_plat_20": 4000,
    "slayd_plat_30": 5000,
    "mustaqil_ish": 3000,
    "referat": 3000,
    "loyiha_ishi": 3000,
    "infografika": 1500,
    "infografika_hd": 3000,
    "maqola": 2000,
    "tezis": 2000,
    "glossary_small": 1000,
    "glossary_medium": 2000,
    "glossary_large": 3000,
    "test_10": 1000,
    "test_20": 2000,
    "test_30": 2000,
    "test_50": 3000,
    "krossvord_10": 1000,
    "krossvord_15": 2000,
    "krossvord_20": 2000,
    "insho_1": 1000,
    "rezyume": 3000,
    "obyektivka": 3000,
    "motivatsion": 2000,
    "jadval": 2000,
    "mindmap": 2000,
    "insho_2": 2000,
    "insho_3": 2000,
    "insho_5": 3000,
    "kurs_ishi": 12000,
    "bmi": 20000,
    "arxivlash": 1000,
    "pdf_convert": 1500,
}

# Foydalanuvchi uchun bepul foydalanish qoidalari shu yerda yagona saqlanadi.
AI_FREE_LIMIT = 3
AI_PRICE_PER_MSG = 200
OBYEKTIVKA_FREE_LIMIT = 2


def format_som(amount: int) -> str:
    """Summani botda bir xil ko'rinishda chiqaradi."""
    return f"{amount:,}".replace(",", " ")


def get_balance_price_lines() -> str:
    """Balans menyusidagi amaldagi narx va limitlarni markaziy sozlamadan tuzadi."""
    return "\n".join((
        f"• Taqdimot: `{format_som(SERVICE_PRICES['slayd_gold_10'])} - {format_som(SERVICE_PRICES['slayd_plat_30'])}` so'm",
        f"• Ma'lumotnoma/Obyektivka: `{format_som(SERVICE_PRICES['obyektivka'])}` so'm _(dastlabki {OBYEKTIVKA_FREE_LIMIT} ta bepul)_",
        f"• Mustaqil ish: `{format_som(SERVICE_PRICES['mustaqil_ish'])}` so'm",
        f"• Kurs ishi: `{format_som(SERVICE_PRICES['kurs_ishi'])}` so'm",
        f"• Infografika: `{format_som(SERVICE_PRICES['infografika'])}` so'm",
        f"• Maqola / Tezis: `{format_som(SERVICE_PRICES['maqola'])}` so'm",
        f"• Test / Krossvord: `{format_som(SERVICE_PRICES['test_10'])}–{format_som(SERVICE_PRICES['test_50'])}` so'm",
        f"• Arxivlash: `{format_som(SERVICE_PRICES['arxivlash'])}` so'm",
        f"• AI yordamchi: (kuniga {AI_FREE_LIMIT} ta bepul; keyin {format_som(AI_PRICE_PER_MSG)} so'm)",
    ))


def get_slayd_price(template_num: int, slide_count: int) -> int:
    """Stil va slayd soniga qarab yagona taqdimot narxini qaytaradi."""
    if template_num in (35, 36):  # Silver
        return SERVICE_PRICES["slayd"]
    if template_num in (37, 38):  # Platinum
        if slide_count <= 10:
            return SERVICE_PRICES["slayd_plat_10"]
        if slide_count <= 20:
            return SERVICE_PRICES["slayd_plat_20"]
        return SERVICE_PRICES["slayd_plat_30"]
    # Gold
    if slide_count <= 10:
        return SERVICE_PRICES["slayd_gold_10"]
    if slide_count <= 20:
        return SERVICE_PRICES["slayd_gold_20"]
    return SERVICE_PRICES["slayd_gold_30"]
