"""Foreign places written in English, read by their Vietnamese names: Moscow -> Mát cơ va.

The spoken forms follow the transliteration style of the normalizer: syllables separated by spaces and
no "x" before a consonant ("Mát-xcơ-va" -> Mát cơ va). Only names whose Vietnamese form is the usual one
in Vietnamese news are listed; other foreign names are left for the TTS model. Chinese cities written in
pinyin get their Sino-Vietnamese names.
"""

EXONYMS = {
    # Capitals and large cities
    "Moscow": "Mát cơ va", "Kyiv": "Ki ép", "Kiev": "Ki ép", "Washington": "Oa sinh tơn",
    "London": "Luân Đôn", "Paris": "Pa ri", "Berlin": "Béc lin", "Rome": "Rô ma", "Vienna": "Viên",
    "Geneva": "Giơ ne vơ", "Brussels": "Brúc xen", "Warsaw": "Vác sa va", "Prague": "Pra ha",
    "Athens": "A ten", "Cairo": "Cai rô", "Tehran": "Tê hê ran", "Ottawa": "Ốt ta oa", "Canberra": "Can bê ra",
    "Tokyo": "Tô ky ô", "Seoul": "Xơ un", "Pyongyang": "Bình Nhưỡng", "Bangkok": "Băng Cốc",
    "Singapore": "Xin ga po", "Jakarta": "Gia các ta", "Manila": "Ma ni la", "Vientiane": "Viêng Chăn",
    # Chinese cities in pinyin
    "Beijing": "Bắc Kinh", "Shanghai": "Thượng Hải", "Taipei": "Đài Bắc", "Shenzhen": "Thâm Quyến",
    "Guangzhou": "Quảng Châu", "Hangzhou": "Hàng Châu", "Changzhou": "Thường Châu", "Wuhan": "Vũ Hán",
    "Chongqing": "Trùng Khánh", "Tianjin": "Thiên Tân", "Nanjing": "Nam Kinh", "Chengdu": "Thành Đô",
    "Xiamen": "Hạ Môn",
}
