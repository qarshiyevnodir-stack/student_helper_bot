"""
5 ta shablon preview rasmidan bitta collage yaratadi.
2+2+1 formatida joylashtiriladi.
"""
from PIL import Image, ImageDraw, ImageFont
import os

PREVIEWS_DIR = os.path.join(os.path.dirname(__file__), "templates", "previews")
OUTPUT_PATH  = os.path.join(PREVIEWS_DIR, "collage.png")

# Har bir thumbnail o'lchami
THUMB_W = 480
THUMB_H = 270
GAP     = 8
BG_COLOR = (30, 30, 30)

# 5 ta rasm yuklash va resize qilish
thumbs = []
for i in range(1, 6):
    path = os.path.join(PREVIEWS_DIR, f"{i}.png")
    img = Image.open(path).convert("RGB")
    img = img.resize((THUMB_W, THUMB_H), Image.LANCZOS)
    thumbs.append(img)

# Collage o'lchami: 2 ustun, 3 qator (oxirgisi 1 ta markazda)
cols = 2
total_w = cols * THUMB_W + (cols + 1) * GAP
row1_y = GAP
row2_y = GAP + THUMB_H + GAP
row3_y = GAP + 2 * (THUMB_H + GAP)
total_h = row3_y + THUMB_H + GAP

collage = Image.new("RGB", (total_w, total_h), BG_COLOR)

# 1-qator: shablon 1, 2
collage.paste(thumbs[0], (GAP, row1_y))
collage.paste(thumbs[1], (GAP + THUMB_W + GAP, row1_y))

# 2-qator: shablon 3, 4
collage.paste(thumbs[2], (GAP, row2_y))
collage.paste(thumbs[3], (GAP + THUMB_W + GAP, row2_y))

# 3-qator: shablon 5 (markazda)
center_x = (total_w - THUMB_W) // 2
collage.paste(thumbs[4], (center_x, row3_y))

# Raqam belgilari qo'shish
try:
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 28)
except:
    font = ImageFont.load_default()

draw = ImageDraw.Draw(collage)
positions = [
    (GAP + 8, row1_y + 8),
    (GAP + THUMB_W + GAP + 8, row1_y + 8),
    (GAP + 8, row2_y + 8),
    (GAP + THUMB_W + GAP + 8, row2_y + 8),
    (center_x + 8, row3_y + 8),
]
labels = ["1", "2", "3", "4", "5"]
for pos, label in zip(positions, labels):
    # Qora soya
    draw.text((pos[0]+2, pos[1]+2), label, font=font, fill=(0, 0, 0, 200))
    # Oq matn
    draw.text(pos, label, font=font, fill=(255, 255, 255))

collage.save(OUTPUT_PATH, "PNG", quality=95)
print(f"✅ Collage yaratildi: {OUTPUT_PATH}")
print(f"   O'lcham: {total_w}x{total_h}")
