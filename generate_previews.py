"""
PPTX shablonlaridan preview rasm yaratadi.
Birinchi slaydni PNG ga aylantiradi.
"""
import subprocess
import os
import shutil

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates", "shablonlar")
PREVIEWS_DIR = os.path.join(os.path.dirname(__file__), "templates", "previews")

os.makedirs(PREVIEWS_DIR, exist_ok=True)

for i in range(1, 6):
    pptx_path = os.path.join(TEMPLATES_DIR, f"{i}.pptx")
    if not os.path.exists(pptx_path):
        print(f"PPTX topilmadi: {pptx_path}")
        continue

    # LibreOffice orqali PDF ga aylantirish
    pdf_path = os.path.join(PREVIEWS_DIR, f"{i}.pdf")
    result = subprocess.run(
        ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", PREVIEWS_DIR, pptx_path],
        capture_output=True, text=True, timeout=60
    )
    if result.returncode != 0:
        print(f"LibreOffice xatosi {i}: {result.stderr}")
        continue

    # PDF dan birinchi sahifani PNG ga aylantirish
    from pdf2image import convert_from_path
    try:
        images = convert_from_path(pdf_path, first_page=1, last_page=1, dpi=150)
        if images:
            out_path = os.path.join(PREVIEWS_DIR, f"{i}.png")
            images[0].save(out_path, "PNG")
            print(f"✅ Shablon {i} preview yaratildi: {out_path}")
        else:
            print(f"❌ Shablon {i}: rasm yaratilmadi")
    except Exception as e:
        print(f"❌ Shablon {i} xatosi: {e}")
    finally:
        # PDF ni o'chirish
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

print("Tugadi!")
