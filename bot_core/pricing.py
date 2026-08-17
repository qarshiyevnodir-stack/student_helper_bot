"""Bot xizmatlari uchun markazlashgan narx sozlamalari."""

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
    "maqola": 3000,
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
