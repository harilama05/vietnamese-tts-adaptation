"""Curated common abbreviations and the policy for every other initialism.

latin mode (default): a letter-by-letter acronym becomes spaced Latin capitals
(GDP -> "G D P") that the TTS model reads itself; 2-letter acronyms and
acronyms pronounceable as a word (BRICS, JAMSTEC) stay as written.
spell mode: the 0.10.0 policy with Vietnamese letter names (GDP -> "gờ đê pê").
"""

import re

# Forms a Vietnamese listener expects expanded or pronounced as a Vietnamese word.
# Everything else follows classify_acronym. VIETNAMESE is the core of the wider,
# context-aware lexicon in vi_abbreviations.py (clusters, Bộ/Sở sectors, BV Bạch Mai).
VIETNAMESE = {
    "UBND": "Ủy ban nhân dân", "HĐND": "Hội đồng nhân dân", "MTTQ": "Mặt trận Tổ quốc",
    "UBMTTQ": "Ủy ban Mặt trận Tổ quốc", "UBTVQH": "Ủy ban Thường vụ Quốc hội",
    "ĐBQH": "đại biểu Quốc hội", "BCHTW": "Ban Chấp hành Trung ương",
    "TW": "Trung ương", "TƯ": "Trung ương", "XHCN": "xã hội chủ nghĩa",
    "CHXHCN": "Cộng hòa xã hội chủ nghĩa", "LHQ": "Liên Hợp Quốc",
    "ĐBSCL": "Đồng bằng sông Cửu Long", "TP": "thành phố", "TPHCM": "Thành phố Hồ Chí Minh",
    "HCM": "Hồ Chí Minh", "VN": "Việt Nam", "CSGT": "cảnh sát giao thông",
    "CAND": "Công an nhân dân", "QĐND": "Quân đội nhân dân", "VKSND": "Viện kiểm sát nhân dân",
    "TAND": "Tòa án nhân dân", "BHXH": "bảo hiểm xã hội", "BHYT": "bảo hiểm y tế",
    "BHTN": "bảo hiểm thất nghiệp", "THPT": "trung học phổ thông", "THCS": "trung học cơ sở",
    "ĐHQG": "Đại học Quốc gia", "CNTT": "công nghệ thông tin", "KHCN": "khoa học công nghệ",
    "TNHH": "trách nhiệm hữu hạn", "CTCP": "công ty cổ phần", "HĐQT": "hội đồng quản trị",
    "BĐS": "bất động sản", "ATGT": "an toàn giao thông", "ATTP": "an toàn thực phẩm",
    "PCCC": "phòng cháy chữa cháy", "GTVT": "giao thông vận tải", "KCN": "khu công nghiệp",
    "CCCD": "căn cước công dân", "CMND": "chứng minh nhân dân", "GPLX": "giấy phép lái xe",
    "SĐT": "số điện thoại", "CLB": "câu lạc bộ", "HLV": "huấn luyện viên",
    "VĐV": "vận động viên", "CĐV": "cổ động viên", "ĐTQG": "đội tuyển quốc gia",
    "SVĐ": "sân vận động", "NXB": "nhà xuất bản", "PV": "phóng viên",
    "NSND": "nghệ sĩ nhân dân", "NSƯT": "nghệ sĩ ưu tú", "GS": "giáo sư", "PGS": "phó giáo sư",
    "ThS": "thạc sĩ", "MST": "mã số thuế", "STK": "số tài khoản",
}
COMMON = {
    **VIETNAMESE,
    # Acronyms Vietnamese speakers pronounce as a word
    "NATO": "na tô", "ASEAN": "a xê an", "APEC": "a pếch", "OPEC": "ô pếch", "NASA": "na sa",
    "UNESCO": "u nét cô", "UNICEF": "u ni xép", "FIFA": "phi pha", "UEFA": "u ê pha",
    "AIDS": "ết", "SARS": "sát", "COVID": "cô vít", "RON": "ron",
    # Established loanword readings
    "TV": "ti vi", "OK": "ô kê", "VIP": "víp", "SIM": "sim", "USD": "đô la Mỹ", "VND": "Việt Nam đồng",
    # Company titles, spoken with English letter names (the model reads "C E O" as "cê e ô")
    "CEO": "xi i ô", "CFO": "xi ép ô", "CTO": "xi ti ô", "COO": "xi ô ô", "CMO": "xi em ô",
    "VNĐ": "Việt Nam đồng",
}

_VIETNAMESE_VOWEL_MARKS = re.compile("[ÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ]")
_ROMAN_IVX = re.compile(r"(?:X{0,3})(?:IX|IV|V?I{0,3})")
SPELL_MAX_WITH_VOWELS = 4
SPELL_MAX_WITHOUT_VOWELS = 8


def is_vietnamese_caps_word(token: str) -> bool:
    return bool(_VIETNAMESE_VOWEL_MARKS.search(token))


def is_spell_candidate(token: str) -> bool:
    """All-caps initialism that should be read letter by letter."""
    if "." in token:
        return False  # initials and dotted forms: J.R.R., U.S., D.C.
    letters = token
    if not re.fullmatch(r"[A-ZĐ]{2,}", letters) or is_vietnamese_caps_word(letters):
        return False
    if _ROMAN_IVX.fullmatch(letters):
        return False  # II, IV, XIV: numerals are read only with an explicit cue
    has_vowel = any(c in "AEIOUY" for c in letters)
    return len(letters) <= (SPELL_MAX_WITH_VOWELS if has_vowel else SPELL_MAX_WITHOUT_VOWELS)


# Pronunciations (not expansions) are valid inside codes too: COVID-19.
SAY = frozenset(("NATO", "ASEAN", "APEC", "OPEC", "NASA", "UNESCO", "UNICEF", "FIFA", "UEFA", "AIDS",
                 "SARS", "COVID", "RON", "TV", "OK", "VIP", "SIM"))

# English-letter transliterations used by 0.10.0; only acronym_mode="spell" uses them.
LEGACY_SAY = {"AI": "ây ai", "IT": "ai ti", "CEO": "xi i ô", "GPT": "gi pi ti", "ID": "ai đi", "BRICS": "brích"}

_VOWELS = "AEIOUY"
_ONSETS = frozenset("BL BR CH CL CR DR FL FR GL GR KN PH PL PR QU SC SH SK SL SM SN SP ST SW TH TR TW WH WR "
                    "SCR SPR STR SPL SHR THR".split())
_CODAS = frozenset("CK CT FT LD LF LK LM LP LT MP ND NG NK NT PS PT RB RC RD RF RG RK RL RM RN RP RS RT SK SP "
                   "SS ST CS KS TS DS NS MS LS RR LL FF TH SH CH GH LTS NDS NTS RTS RDS RKS".split())
# Exceptions to the phonotactic rule, and English words often written in
# capitals (TOP 10, HOT, NEWS). Keep these lists SHORT.
FORCE_SPELL = frozenset(("IMEI", "ICAO"))
KEEP_WORD = frozenset(("AI", "NVIDIA", "TOP", "HOT", "NEW", "NEWS", "BIG", "WOW", "OFF", "FAN", "MAX", "PRO",
                       "ONE", "BOX", "MIX", "FIT", "POP", "FUN", "YES", "HIT", "CUP", "SEA"))
# Two capitals that spell a Vietnamese syllable (XE, BA, IT, UN) would be read as
# that word, so they are spelled; other 2-letter acronyms (LG, SK, EU) are kept.
_VI_SYLLABLE_2 = re.compile(r"[BCDĐGHKLMNPRSTVX][AEIOUY]|A[CIMNOPTUY]|E[CMNOPT]|I[ACMNPTU]|O[CIMNPT]|U[ACIMNPT]")


def is_pronounceable(token: str) -> bool:
    """English-like syllable shape: BRICS, NASA, JAMSTEC yes; OECD, CSIS, EVFTA no."""
    parts = re.findall(rf"[{_VOWELS}]+|[^{_VOWELS}]+", token)
    if not any(p[0] in _VOWELS for p in parts):
        return False
    for i, part in enumerate(parts):
        if part[0] in _VOWELS:
            # Three vowels, or a doubled I/U/A/Y (XIIB, GII), do not form an English syllable.
            if len(part) > 2 or (len(part) == 2 and part[0] == part[1] and part[0] in "AIUY"):
                return False
        elif len(part) > 1:
            if i == 0 and part not in _ONSETS:
                return False
            if i == len(parts) - 1 and part not in _CODAS:
                return False
            if 0 < i < len(parts) - 1 and len(part) > 2 and not any(
                    (len(part[:k]) == 1 or part[:k] in _CODAS) and (len(part[k:]) == 1 or part[k:] in _ONSETS)
                    for k in range(1, len(part))):
                return False
    return True


def classify_acronym(token: str) -> str:
    """'spell' (read letter by letter) or 'keep' (leave for the TTS model) in latin mode."""
    if ("." in token or not re.fullmatch(r"[A-ZĐ]{2,}", token) or is_vietnamese_caps_word(token)
            or _ROMAN_IVX.fullmatch(token)):
        return "keep"
    if token in FORCE_SPELL or ("Đ" in token and len(token) <= 3):
        return "spell"  # Đ never starts an English acronym: ĐH, CĐ, BCĐ
    if token in KEEP_WORD:
        return "keep"
    if len(token) == 2:
        return "spell" if _VI_SYLLABLE_2.fullmatch(token) else "keep"
    if len(token) == 3:
        return "spell"
    return "keep" if is_pronounceable(token) else "spell"
