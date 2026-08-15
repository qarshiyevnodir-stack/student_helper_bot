# Rezyume / CV xizmatini yangilash rejasi

## Maqsad

Rezyume yaratish jarayonini aniq, professional va foydalanuvchi nazoratida qilish. Tizim foydalanuvchi bermagan ish tajribasi, sertifikat, ta'lim yoki yutuqlarni o'ylab topmaydi.

## Yangi foydalanuvchi oqimi

| Qadam | Kiritiladigan ma'lumot | Izoh |
|---:|---|---|
| 1 | Til | 10 ta qo'llab-quvvatlanadigan til |
| 2 | To'liq F.I.Sh. | Majburiy |
| 3 | Aloqa ma'lumotlari | Email, telefon, joylashuv, havolalar |
| 4 | Maqsadli lavozim | Majburiy |
| 5 | Professional xulosa | Ixtiyoriy, AI faqat tahrirlaydi |
| 6 | Ish tajribasi | Foydalanuvchi bergan ma'lumotni formatlaydi, to'qimaydi |
| 7 | Loyihalar | Ixtiyoriy |
| 8 | Ta'lim | Ixtiyoriy |
| 9 | Sertifikatlar | Ixtiyoriy |
| 10 | Ko'nikmalar | Vergul bilan kiritiladi |
| 11 | Uslub | Minimal, Professional, Creative |
| 12 | Uzunlik | 1 yoki 2 sahifa |
| 13 | Preview | Ma'lumotlarni tekshirish va tahrirlash |
| 14 | Profil rasmi | Oxirgi qadam; rasm yoki o'tkazib yuborish |
| 15 | Format | PDF yoki DOCX |

## Dizaynlar

| Kalit | Nomi | Vizual tavsif |
|---|---|---|
| `minimal` | Minimal | Oqartirilgan, ATS-ga mos, foto ixtiyoriy |
| `professional` | Professional | To'q ko'k header, ikki ustunli, rasm bilan |
| `creative` | Creative | Binafsha aksent, loyiha va ko'nikmalarni ajratib ko'rsatadi |

## Sifat qoidalari

1. AI faqat kiritilgan ma'lumotlarni imlo, uslub va qisqa bullet formatida tahrirlaydi.
2. Bo'sh yoki `-` yuborilgan bo'limlar hujjatda chiqmaydi.
3. 1 sahifalik CV asosiy bo'limlarni ixcham ko'rsatadi; 2 sahifalik CV hamma bo'limlarni chiqara oladi.
4. Preview ekrani foydalanuvchiga tanlangan dizayn, uzunlik va qisqacha ma'lumotlarni ko'rsatadi.
5. Profil rasmi preview tasdiqlangandan keyin, format tanlashdan oldin so'raladi.
6. PDF hamda tahrir qilinadigan DOCX formatlaridan bittasi tanlanadi.

## Texnik yechim

- `hujjat_utils.py`: qat'iy JSON normalizatori, HTML/PDF render va DOCX render.
- `resume_template.html`: professional dizayn sifatida saqlanadi; minimal va creative uchun alohida HTML shablonlar yaratiladi.
- `main.py`: CV oqimiga dizayn, preview, rasm va format state/handlerlari qo'shiladi.
- Rasm JPEG sifatida saqlanib, PDF va DOCX headeriga proporsiya saqlangan holda joylashtiriladi.

## Test ssenariylari

1. Tajribasiz talaba: ta'lim, loyiha va ko'nikmalar bilan 1 sahifalik minimal CV.
2. Tajribali mutaxassis: 2 sahifalik professional CV, ish tajribasi va profil rasmi bilan.
3. Bo'sh sertifikat/loyiha bo'limlari: hujjatda bo'limlar ko'rinmasligi.
4. PDF va DOCX chiqishi: foto, bo'limlar hamda aloqa ma'lumotlari to'g'ri joylashishi.
5. AI normalizatsiyasi: kiritilmagan ish joyi, sana, yutuq yoki sertifikat paydo bo'lmasligi.
