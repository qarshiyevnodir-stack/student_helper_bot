"""Obyektivka hujjatining statik label va sarlavhalari uchun lokalizatsiya qatlami.

Foydalanuvchi kiritgan faktlar tarjima qilinmaydi: ular aynan kiritilganidek
qoladi. Faqat hujjatning doimiy strukturaviy matnlari tanlangan tilga o'tadi.
"""

OBYEKTVKA_LABELS = {
    "uz": {
        "title": "MA’LUMOTNOMA", "information": "MA'LUMOT", "relatives_intro": "yaqin qarindoshlari to‘g‘risida",
        "born_year": "Tug‘ilgan yili:", "born_place": "Tug‘ilgan joyi:", "nationality": "Millati:",
        "party": "Partiyaviyligi:", "education": "Ma’lumoti:", "graduated": "Tamomlagan:",
        "specialty": "Ma’lumoti bo’yicha mutaxassisligi:", "degree": "Ilmiy darajasi:", "academic_title": "Ilmiy unvoni:",
        "languages": "Qaysi chet tillarini biladi:", "military": "Harbiy (maxsus) unvoni:",
        "awards": "Davlat mukofotlari bilan taqdirlanganmi (qanaqa):",
        "elected": "Saylanadigan organlar a’zoligi (to‘liq ko‘rsatilishi lozim):", "employment": "MEHNAT FAOLIYATI",
        "relationship": "Qarindoshligi", "full_name": "Familiyasi, ismi va otasining ismi",
        "birth_details": "Tug‘ilgan\nyili va joyi", "workplace": "Ish joyi va lavozimi", "residence": "Turar joyi",
        "phone": "Tel: ", "passport": "PASPORT: ", "registration": "PROPISKA: ", "additional": "QO'SHIMCHA MA'LUMOT: ",
    },
    "en": {
        "title": "INFORMATION SHEET", "information": "INFORMATION", "relatives_intro": "Information on close relatives of",
        "born_year": "Year of birth:", "born_place": "Place of birth:", "nationality": "Nationality:",
        "party": "Political affiliation:", "education": "Education:", "graduated": "Graduated from:",
        "specialty": "Specialty:", "degree": "Academic degree:", "academic_title": "Academic title:",
        "languages": "Foreign languages:", "military": "Military (special) rank:", "awards": "State awards (if any):",
        "elected": "Elected office or representative body membership:", "employment": "EMPLOYMENT HISTORY",
        "relationship": "Relationship", "full_name": "Surname, given name and patronymic",
        "birth_details": "Year and\nplace of birth", "workplace": "Workplace and position", "residence": "Place of residence",
        "phone": "Phone: ", "passport": "PASSPORT: ", "registration": "REGISTERED ADDRESS: ", "additional": "ADDITIONAL INFORMATION: ",
    },
    "ru": {
        "title": "СПРАВКА", "information": "СВЕДЕНИЯ", "relatives_intro": "Сведения о близких родственниках",
        "born_year": "Год рождения:", "born_place": "Место рождения:", "nationality": "Национальность:",
        "party": "Партийность:", "education": "Образование:", "graduated": "Окончил(а):", "specialty": "Специальность:",
        "degree": "Учёная степень:", "academic_title": "Учёное звание:", "languages": "Иностранные языки:",
        "military": "Воинское (специальное) звание:", "awards": "Государственные награды:",
        "elected": "Членство в выборных органах:", "employment": "ТРУДОВАЯ ДЕЯТЕЛЬНОСТЬ",
        "relationship": "Родство", "full_name": "Фамилия, имя, отчество", "birth_details": "Год и\nместо рождения",
        "workplace": "Место работы и должность", "residence": "Место жительства",
        "phone": "Тел.: ", "passport": "ПАСПОРТ: ", "registration": "ПРОПИСКА: ", "additional": "ДОПОЛНИТЕЛЬНЫЕ СВЕДЕНИЯ: ",
    },
    "ko": {
        "title": "개인 신상 정보서", "information": "정보", "relatives_intro": "의 가까운 친족 정보",
        "born_year": "출생 연도:", "born_place": "출생지:", "nationality": "국적:", "party": "정당 소속:",
        "education": "학력:", "graduated": "졸업 교육기관:", "specialty": "전공:", "degree": "학위:", "academic_title": "학술 직위:",
        "languages": "외국어 능력:", "military": "군(특수) 계급:", "awards": "국가 포상:", "elected": "선출직 또는 대표 기관 활동:",
        "employment": "경력", "relationship": "관계", "full_name": "성명", "birth_details": "출생 연도 및\n장소",
        "workplace": "근무처 및 직위", "residence": "거주지", "phone": "전화: ", "passport": "여권: ",
        "registration": "등록 주소: ", "additional": "추가 정보: ",
    },
    "zh": {
        "title": "个人信息表", "information": "信息", "relatives_intro": "的近亲属信息",
        "born_year": "出生年份:", "born_place": "出生地:", "nationality": "国籍:", "party": "党派:",
        "education": "学历:", "graduated": "毕业院校:", "specialty": "专业:", "degree": "学位:", "academic_title": "学术职称:",
        "languages": "外语能力:", "military": "军衔（特殊职务）:", "awards": "国家奖励:", "elected": "选举机构成员资格:",
        "employment": "工作经历", "relationship": "关系", "full_name": "姓名", "birth_details": "出生年份\n及地点",
        "workplace": "工作单位及职务", "residence": "居住地址", "phone": "电话: ", "passport": "护照: ",
        "registration": "登记地址: ", "additional": "附加信息: ",
    },
    "de": {
        "title": "PERSONALBOGEN", "information": "ANGABEN", "relatives_intro": "Angaben zu nahen Angehörigen von",
        "born_year": "Geburtsjahr:", "born_place": "Geburtsort:", "nationality": "Staatsangehörigkeit:",
        "party": "Parteizugehörigkeit:", "education": "Bildung:", "graduated": "Absolviert:", "specialty": "Fachrichtung:",
        "degree": "Akademischer Grad:", "academic_title": "Akademischer Titel:", "languages": "Fremdsprachen:",
        "military": "Militärischer (Sonder-)Rang:", "awards": "Staatliche Auszeichnungen:", "elected": "Mitgliedschaft in Wahlorganen:",
        "employment": "BERUFLICHER WERDEGANG", "relationship": "Verhältnis", "full_name": "Nachname, Vorname und Vatersname",
        "birth_details": "Geburtsjahr\nund -ort", "workplace": "Arbeitsort und Position", "residence": "Wohnort",
        "phone": "Tel.: ", "passport": "REISEPASS: ", "registration": "MELDEADRESSE: ", "additional": "ZUSÄTZLICHE ANGABEN: ",
    },
    "tr": {
        "title": "BİLGİ FORMU", "information": "BİLGİ", "relatives_intro": "yakın akrabaları hakkında bilgi",
        "born_year": "Doğum yılı:", "born_place": "Doğum yeri:", "nationality": "Milliyeti:", "party": "Siyasi üyeliği:",
        "education": "Eğitimi:", "graduated": "Mezun olduğu kurum:", "specialty": "Uzmanlık alanı:", "degree": "Akademik derecesi:",
        "academic_title": "Akademik unvanı:", "languages": "Yabancı diller:", "military": "Askerî (özel) rütbe:",
        "awards": "Devlet ödülleri:", "elected": "Seçilmiş organ üyeliği:", "employment": "ÇALIŞMA GEÇMİŞİ",
        "relationship": "Yakınlık", "full_name": "Soyadı, adı ve baba adı", "birth_details": "Doğum yılı\nve yeri",
        "workplace": "İşyeri ve görevi", "residence": "İkamet yeri", "phone": "Tel.: ", "passport": "PASAPORT: ",
        "registration": "KAYIT ADRESİ: ", "additional": "EK BİLGİ: ",
    },
    "tg": {
        "title": "МАЪЛУМОТНОМА", "information": "МАЪЛУМОТ", "relatives_intro": "маълумот дар бораи хешовандони наздик",
        "born_year": "Соли таваллуд:", "born_place": "Ҷойи таваллуд:", "nationality": "Миллат:", "party": "Ҳизбият:",
        "education": "Маълумот:", "graduated": "Муассисаи хатмкарда:", "specialty": "Ихтисос:", "degree": "Дараҷаи илмӣ:",
        "academic_title": "Унвони илмӣ:", "languages": "Забонҳои хориҷӣ:", "military": "Унвони ҳарбӣ (махсус):",
        "awards": "Мукофотҳои давлатӣ:", "elected": "Узвият дар мақомоти интихобӣ:", "employment": "ФАЪОЛИЯТИ МЕҲНАТӢ",
        "relationship": "Хешутаборӣ", "full_name": "Насаб, ном ва номи падар", "birth_details": "Сол ва ҷойи\nтаваллуд",
        "workplace": "Ҷойи кор ва вазифа", "residence": "Ҷойи истиқомат", "phone": "Тел.: ", "passport": "ШИНОСНОМА: ",
        "registration": "СУРОҒАИ БАҚАЙДГИРӢ: ", "additional": "МАЪЛУМОТИ ИЛОВАГӢ: ",
    },
    "kaa": {
        "title": "MAǴLUMATNAMA", "information": "MAǴLUMAT", "relatives_intro": "jaqın tuwısqanları haqqında maǵlıwmat",
        "born_year": "Tuwılǵan jılı:", "born_place": "Tuwılǵan jeri:", "nationality": "Mıllatı:", "party": "Partiyalılığı:",
        "education": "Maǵlımatı:", "graduated": "Pitkerгенi:", "specialty": "Qánigeligi:", "degree": "İlimiy dárejesi:",
        "academic_title": "İlimiy ataǵı:", "languages": "Shet tilleri:", "military": "Áskeriy (arnawlı) ataǵı:",
        "awards": "Mámleketlik sıylıqları:", "elected": "Saylanbalı organdardaǵı aǵzalığı:", "employment": "MIYNET FAOLIYATI",
        "relationship": "Tuwısqanlığı", "full_name": "Familiyası, atı hám ákesi atı", "birth_details": "Tuwılǵan jılı\nhám jeri",
        "workplace": "Jumıs ornı hám lawazımı", "residence": "Turar jayı", "phone": "Tel.: ", "passport": "PASPORT: ",
        "registration": "TIRKEW MÁNZILI: ", "additional": "QOSIMSHA MAǴLUMAT: ",
    },
    "kk": {
        "title": "АНЫҚТАМА", "information": "МӘЛІМЕТ", "relatives_intro": "жақын туыстары туралы мәлімет",
        "born_year": "Туған жылы:", "born_place": "Туған жері:", "nationality": "Ұлты:", "party": "Партиялылығы:",
        "education": "Білімі:", "graduated": "Бітірген оқу орны:", "specialty": "Мамандығы:", "degree": "Ғылыми дәрежесі:",
        "academic_title": "Ғылыми атағы:", "languages": "Шет тілдері:", "military": "Әскери (арнайы) атағы:",
        "awards": "Мемлекеттік наградалары:", "elected": "Сайланбалы органдарға мүшелігі:", "employment": "ЕҢБЕК ЖОЛЫ",
        "relationship": "Туыстығы", "full_name": "Тегі, аты және әкесінің аты", "birth_details": "Туған жылы\nмен жері",
        "workplace": "Жұмыс орны мен лауазымы", "residence": "Тұратын жері", "phone": "Тел.: ", "passport": "ТӨЛҚҰЖАТ: ",
        "registration": "ТІРКЕЛГЕН МЕКЕНЖАЙ: ", "additional": "ҚОСЫМША МӘЛІМЕТ: ",
    },
}


def get_obyektivka_labels(lang: str) -> dict:
    """Noma'lum til kodi kelganda original O'zbek hujjat shakliga qaytadi."""
    return OBYEKTVKA_LABELS.get(lang, OBYEKTVKA_LABELS["uz"])
