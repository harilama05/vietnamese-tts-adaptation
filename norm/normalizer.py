"""One scanner over source spans, with typed readers and conservative fallbacks.

Architecture and abbreviation data build on ZeroTTS/soe-vinorm; units and
explicit spelling build on OmniVoice's scripts/text_normalize.py. Readers do
not feed generated text back through the scanner. See data/NOTICE.md.
"""

import calendar
import copy
import re
import unicodedata
from dataclasses import dataclass, replace
from datetime import datetime
from functools import lru_cache
from typing import Optional

from ._version import __version__
from .boundaries import consume_unit_group
from .config import DEFAULT_CONFIG, NormalizerConfig
from .domains import domain_scanner, read_domain
from .lexicon import UNITS, WORD_UNITS, _abbreviations, latin_letters, spell_letters
from .expressions import read_expression
from .acronyms import (COMMON as COMMON_ABBREVIATIONS, LEGACY_SAY, SAY as SAY_ABBREVIATIONS, classify_acronym,
                       is_spell_candidate, is_vietnamese_caps_word)
from .news import ABBREVIATIONS as NEWS_ABBREVIATIONS, CURRENCY_PREFIX_PATTERN, read_news
from . import vi_abbreviations as vi
from . import places, web
from .numbers import NUMBER_PATTERN, infer_ambiguous_number, parse_number, quantity_config, read_digits, read_integer, read_number
from .quantities import parse_expression_quantity, read_grouped_quantity
from .units import CURRENCY, RATE_WORDS, VI_CURRENCY, VI_FORMAT_CURRENCY, exchange_rate, read_unit, unit_pattern

_WORD = r"[^\W\d_]+"
_NUM = NUMBER_PATTERN
_SIGNED = rf"[+−-]?{_NUM}"
_DATE_CUE = r"ngày|mùng|mồng|hôm|sáng|trưa|chiều|tối|đêm"
_RANGE_DATE = r"[0-9]{1,2}[ \t]*/[ \t]*[0-9]{1,2}(?:[ \t]*/[ \t]*[0-9]{1,4})?"
_DATE_SPACE = r"[ \t]*(?:\r?\n[ \t]*)?"  # also accept a single editorial line wrap
_DATE_GAP = r"(?:[ \t]+(?:\r?\n[ \t]*)?|\r?\n[ \t]*)"
_FULL_DATE = rf"(?:[0-9]{{4}}{_DATE_SPACE}-{_DATE_SPACE}[0-9]{{1,2}}{_DATE_SPACE}-{_DATE_SPACE}[0-9]{{1,2}}|[0-9]{{1,2}}{_DATE_SPACE}[/.-]{_DATE_SPACE}[0-9]{{1,2}}{_DATE_SPACE}[/.-]{_DATE_SPACE}[0-9]{{1,4}})"
_FULL_DATE_RANGE = rf"{_FULL_DATE}{_DATE_SPACE}[–—-]{_DATE_SPACE}{_FULL_DATE}"
_MATH_WORDS = r"tính|chia|biểu thức|phép tính|phép chia"
_MATH_CUE = re.compile(rf"\b(?:{_MATH_WORDS})[ \t]*:?[ \t]*$", re.I)
_WORD_DATE_RANGE = rf"([0-9]+){_DATE_SPACE}[–—-]{_DATE_SPACE}([0-9]+){_DATE_GAP}tháng{_DATE_GAP}([0-9]+)(?:{_DATE_GAP}năm{_DATE_GAP}([0-9]+))?"
_ID_CUE = r"số điện thoại|điện thoại|sđt|hotline|tổng đài|số tài khoản|tài khoản|stk|cccd|cmnd|otp|mã pin|mã bưu chính|mã số thuế|mst"
_CLOCK_CUE = re.compile(r"(?:\b(?:lúc|hẹn|hẹn vào|giờ hẹn))[ \t]*:?[ \t]*$", re.I)
UNIT_WORDS_CASEFOLD = frozenset(word.casefold() for word in (*WORD_UNITS, *RATE_WORDS))
# A month, quarter, day or ordinal after its word: "tháng 4" -> tháng tư, "thứ 05" -> thứ năm.
# "mỗi tháng 4 buổi" counts per month instead.
_PERIOD_CUE = re.compile(r"(?i:\b(thứ|tháng|quý|ngày))[ \t]+\Z")
_PER_PERIOD = re.compile(r"(?i:\b(?:mỗi|hằng|hàng|từng|một|vài|mấy|các|những|nửa)[ \t]+(?:tháng|quý|ngày)[ \t]+\Z)")
# Vietnamese number words. Administrative text writes a number twice: "05 (năm) ngày".
_NUMBER_WORD = r"(?:không|một|mốt|hai|ba|bốn|tư|năm|lăm|sáu|bảy|tám|chín|mười|mươi|trăm|nghìn|ngàn|triệu|tỷ|tỉ|lẻ|linh|chục|phẩy)(?![^\W\d_])"
_NUMBER_WORDS = rf"(?i:{_NUMBER_WORD}(?:[ \t]+{_NUMBER_WORD})*)"
_NUMBER_VARIANTS = {"ngàn": "nghìn", "linh": "lẻ", "mốt": "một", "tư": "bốn", "lăm": "năm", "tỉ": "tỷ"}
# English words that make the number after them a code or an address (context_code, identifier, ip, version).
_NUMBER_CUES = frozenset(("id", "ip", "otp", "stk", "mst", "cccd", "cmnd", "hotline", "version"))


def _number_words(text: str) -> str:
    """Compare number readings across variants: hai mươi tư = hai mươi bốn, một trăm linh năm = lẻ năm."""
    return " ".join(_NUMBER_VARIANTS.get(word, word) for word in text.casefold().split())


# After a number, T is tesla only beside a magnetic field ("MRI 3T", "nam châm 1,5T") and tấn beside a
# truck ("xe tải 5T"); otherwise a letter, as "800G": "mô-đun 1,6T" -> một phẩy sáu tê (1.6 terabit).
_TESLA_CUE = re.compile(r"(?i:từ trường|cảm ứng từ|nam châm|cộng hưởng từ|từ thông|tesla|\bMRI\b|\bM R I\b)")
_TON_CUE = re.compile(r"(?i:\bxe[ \t]+(?:tải|ben|cẩu)|cần[ \t]+cẩu|trọng[ \t]+tải|tải[ \t]+trọng)")
# A unit symbol after "mỗi" (per) without a number: "$1.100 mỗi kl" -> mỗi ki lô lít.
_PER_UNIT = re.compile(r"(?i:(?<![^\W\d_])mỗi)[ \t]+\Z")
_WEEKDAY_CUE = re.compile(r"(?i:\b(?:thứ[ \t]+(?:0?[2-7]|hai|ba|tư|năm|sáu|bảy)|chủ[ \t]+nhật|dịp|lễ|rạng[ \t]+sáng|khuya))[ \t]*\(?[ \t]*$")
_FRACTION_CUE = re.compile(r"(?i:\b(?:gấp|bằng|chiếm|khoảng|gần|hơn|còn|tới|lên|xuống))[ \t]*$")
_DATE_LIST_ITEM = r"[0-9]{1,2}[ \t]*/[ \t]*[0-9]{1,2}"
_PREV_CAPS_WORD = re.compile(r"(?<![\w.,])([^\W\d_]+)[ \t]+$")
_NEXT_CAPS_WORD = re.compile(r"[ \t]+([^\W\d_]+)(?![\w.,]*[0-9])")


def _in_caps_headline(before: str, after: str) -> bool:
    """A space-adjacent all-caps Vietnamese word marks a capitalized phrase.

    Unit words are excluded: '5 ĐỒNG' is rewritten on the first pass and must
    not change how a neighbouring acronym is read on the second pass.
    """
    for match in (_PREV_CAPS_WORD.search(before), _NEXT_CAPS_WORD.match(after)):
        word = match[1] if match else ""
        if word.isupper() and is_vietnamese_caps_word(word) and word.casefold() not in UNIT_WORDS_CASEFOLD:
            return True
    return False


_ROMAN_VALID = re.compile(r"M{0,3}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})$")
# Words after which a Roman numeral is a number (quý II, cấp III, Phụ lục IV).
# Only I/V/X are accepted: "loại C", "phần D" are letter labels, not 100/500.
_ROMAN_CUES = (r"quý|thứ|khóa|kỳ|đợt|loại|chương|phần|thế kỷ|đại hội|thế chiến|chiến tranh thế giới|"
               r"cấp|mục|tập|giai đoạn|hạng|nhóm|bậc|phụ lục|vùng|hồi|khu vực|điều|TK|ĐH")
# Abbreviated cues are read in full: TK XX -> thế kỷ hai mươi, ĐH XIII -> Đại hội mười ba.
_ROMAN_CUE_WORDS = {"tk": "thế kỷ", "đh": "Đại hội"}
_ROMAN_JOIN = r"(?:[ \t]*,[ \t]*|[ \t]+(?:và|hoặc|đến|tới)[ \t]+|[ \t]*[–-][ \t]*)"
# Regnal numbers: Nữ hoàng Elizabeth II, Giáo hoàng Leo XIV.
_REGNAL_TITLES = (r"vua|nhà vua|quốc vương|nữ hoàng|hoàng đế|sa hoàng|giáo hoàng|thánh cha|hoàng tử|công chúa|"
                  r"thái tử|pope|king|queen|prince|princess|emperor")
_SINO_ORDINAL = {1: "nhất", 2: "nhị", 3: "tam", 4: "tứ", 5: "ngũ", 6: "lục", 7: "thất", 8: "bát", 9: "cửu", 10: "thập"}
# Numeral characters: Ⅱ, ①, ⑴, ⒈, ❶, ➊, ㉑ (read by their Unicode numeric value).
_NUMERAL_CHARS = "\u2160-\u2188\u2460-\u24ff\u2776-\u2793\u3251-\u325f\u32b1-\u32bf"
_UPPER_VI = "A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"
_LOWER_VI = "a-zđàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ"
# A regnal name word is capitalized and has lower-case letters (Elizabeth, Gioan): not "XIV", not "TOEIC".
_NAME_WORD = rf"[{_UPPER_VI}](?=[^\W\d_]*[{_LOWER_VI}])[^\W\d_]*"
# Vietnamese document symbols: 02/NQ-CP, 57-NQ/TW, 15/2020/NĐ-CP, 15/QĐ-TTg, 36/2024/QH15.
_DOC_SYMBOL = re.compile(r"([0-9]{1,5})(?:/([0-9]{4}))?[/-]([A-ZĐ][A-ZĐa-zđ]{0,9}[0-9]{0,3}"
                         r"(?:[/-][A-ZĐ][A-ZĐa-zđ]{0,9}[0-9]{0,3}){0,4})")
# Technical designators: AN/APX-127(V)1, AN/TPY-2, F/A-18E/F.
_DESIGNATOR = re.compile(r"[A-Z]{1,6}(?:/[A-Z]{1,6})+(?:-[0-9]{1,6}[A-Z]{0,2}(?:/[A-Z]{1,2})?)?(?:\([A-Z0-9]{1,3}\)[0-9]{0,3})?")
# Hyphen-joined acronym groups (NĐ-CP, QĐ-TTg, WTO-IMF, EU-ASEAN) and M&A, AT&T.
_CODE_GROUP = re.compile(r"[A-ZĐ]{2,}[a-zđ]?(?:-[A-ZĐ]+[a-zđ]?)+")
_AMP_ACRONYM = re.compile(r"([A-Z]{1,4})&([A-Z]{1,4})")
# Reader result for a dropped gloss: "Thông tấn xã Việt Nam (TTXVN)" reads the name once.
_GLOSS = "\x00gloss\x00"
# Abbreviation clusters joined by "&" (comma and hyphen inside): GD&ĐT, GD & ĐT, VH,TT&DL, LĐ-TB&XH.
_AMP_CLUSTER = r"[A-ZĐƯ]{1,8}(?:[-,][A-ZĐƯ]{1,8})*(?:[ \t]*&[ \t]*[A-ZĐƯ]{1,8}(?:[-,][A-ZĐƯ]{1,8})*)+(?![\w&])"
# Vietnamese document references: "Nghị định 100/2019", "Quyết định số 15/2020" (number and year).
_DOC_NUMBER_CUE = re.compile(r"(?<![^\W\d_])(?:Nghị định|nghị định|Quyết định|quyết định|Thông tư|thông tư|Nghị quyết|"
                             r"nghị quyết|Chỉ thị|chỉ thị|Công văn|công văn|Luật|luật|Pháp lệnh|pháp lệnh|Kết luận|"
                             r"Quy định|quy định|NĐ|QĐ|NQ|TT|CT|CV|số)[ \t]+(?:số[ \t]+)?\Z")
# Transliterated syllables (Mát-xcơ-va, Ô-xtrây-li-a, Mátxcơva): the x of an x+consonant onset is dropped.
_X_CLUSTER = re.compile(r"[xX](?=[bcdđghklmnpqrstvBCDĐGHKLMNPQRSTV])")
_VI_MARKED = re.compile("[ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]", re.I)
_VOWEL_RUN = re.compile("[aăâeêioôơuưyàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ]+", re.I)
_CODAS = frozenset(("", "c", "ch", "m", "n", "ng", "nh", "p", "t"))
_ONSETS = frozenset("b c ch d đ g gh gi h k kh l m n ng ngh nh p ph q qu r s t th tr v x".split())


def _transliteration(word: str) -> str:
    """Mát-xcơ-va -> Mát cơ va, Mátxcơva -> Mát cơ va, Xtốc-khôm -> Tốc khôm.

    Vietnamese has no consonant cluster at the start of a syllable; a transliteration
    keeps the cluster after "x" (Moskva, Stockholm), which the TTS model cannot read.
    Only words with Vietnamese letters are touched: English words (Xbox, next) never are.
    """
    if not _X_CLUSTER.search(word) or not _VI_MARKED.search(word):
        return word
    runs = list(_VOWEL_RUN.finditer(word))
    if not runs:
        return word
    syllables, start = [], 0
    for run, following in zip(runs, runs[1:]):
        cluster = word[run.end():following.start()]
        for size in range(len(cluster)):  # shortest valid coda first
            coda, onset = cluster[:size].lower(), cluster[size:].lower()
            if coda in _CODAS and (onset in _ONSETS or (onset[0] == "x" and onset[1:] in _ONSETS)):
                break
        else:
            return word
        syllables.append(word[start:run.end() + size])
        start = run.end() + size
    syllables.append(word[start:])
    for index, syllable in enumerate(syllables):
        if _X_CLUSTER.match(syllable):
            rest = syllable[1:]
            syllables[index] = rest[0].upper() + rest[1:] if syllable[0] == "X" else rest
    return " ".join(syllables)


# "từ" is not added when the range already follows a framing word.
# Framing words: approximators/prepositions, time periods, and labels such as
# "cấp 6-7", "Điều 4-6", "tầng 3-5" (a label is not read "cấp từ sáu đến bảy").
_RANGE_FRAME = re.compile(r"(?i:\b(từ|khoảng|quanh|xấp xỉ|tầm|chừng|cỡ|gần|hơn|trên|dưới|ngoài|trong|giữa|giai đoạn|thời kỳ|"
                          r"nhiệm kỳ|niên khóa|niên độ|năm học|mùa giải|khóa|mùa|vụ|năm|ngày|đêm|tháng|quý|tuần|thứ|"
                          r"hạng|top|tốp|số|lúc|vào|đến|tới|mỗi|từng|chỉ|còn|lên|xuống|cấp|mục|điều|khoản|điểm|"
                          r"chương|phần|bài|trang|câu|tập|tầng|lớp|phòng|hàng|dòng|cột|bảng|hình|lô|khu|tuyến|làn))"
                          r"[ \t]*[(\[“\"'‘]*[ \t]*\Z")
_NUMBER_WORD_BEFORE_NAM = re.compile(r"(?i:\b(?:không|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|mươi|mốt|lăm|tư|"
                                      r"linh|lẻ|trăm|nghìn|ngàn|triệu|tỷ)[ \t]+năm[ \t]*[(\[“\"'‘]*[ \t]*\Z)")


def _framed(before: str) -> bool:
    """A framing word ends `before`; "năm" after a number word is the number five
    (a generated reading such as "QH một năm"), not the word "year"."""
    match = _RANGE_FRAME.search(before)
    return bool(match) and not (match[1].casefold() == "năm" and _NUMBER_WORD_BEFORE_NAM.search(before))


_RANGE_SOURCE = re.compile(r"[0-9][^0-9\s]{0,6}\s*[–—-]\s*(?:[^0-9\s]{1,3}\s*)?[0-9]")
_NUMBER_START = re.compile(r"(?:không|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|âm)\b")
# A dash between small integers is a range unless the sentence reports a match score.
_SCORE_CONTEXT = re.compile(r"(?i:\b(?:tỷ số|tỉ số|thua|thất bại|bàn thắng|ghi bàn|trận đấu|chung kết|bán kết|"
                            r"tứ kết|vòng bảng|set|hiệp)\b)")
_ROMAN_VALUE = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
_LINK = (
    r"(?:https?|ftp)://[^\s<>]+|www\.[^\s<>]+|"
    r"(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+|"
    r"(?<![\w.-])[\w-]+(?:\.[\w-]+)*\.(?:com|net|org|vn|io|edu|gov|info|dev|ai)\b(?:/[^\s<>]*)?"
)


@lru_cache(maxsize=2)
def _protected_regex(profile):
    common = rf"(?i:{_LINK})|```[\s\S]*?```|`[^`\n]*`|<[A-Za-z/!?][^<>\n]*>"
    if profile == "omnivoice":
        common += r"|\[[^\[\]\n]*\]"
    return re.compile(common)


_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")
_FULLWIDTH_SYMBOLS = str.maketrans("．，＋－：／％", ".,+-:/%")


def _prepare_source(text: str, fullwidth: bool, profile: str = "omnivoice") -> str:
    text = unicodedata.normalize("NFC", text)

    def ordinary(segment):
        segment = segment.replace("\u00a0", " ").replace("\u202f", " ")
        segment = segment.replace("\u200b", " ").replace("\ufeff", "")
        if fullwidth:
            segment = segment.translate(_FULLWIDTH_DIGITS)
            segment = re.sub(r"(?<=[0-9])[．，：／％]|[＋－](?=[0-9])",
                             lambda m: m.group().translate(_FULLWIDTH_SYMBOLS), segment)
        return segment

    out, end = [], 0
    for match in _protected_regex(profile).finditer(text):
        out.extend((ordinary(text[end:match.start()]), match.group()))
        end = match.end()
    out.append(ordinary(text[end:]))
    return "".join(out)


@dataclass(frozen=True)
class NormalizationSpan:
    start: int
    end: int
    kind: str
    source: str
    spoken: str
    status: str  # expanded | preserved
    reason: Optional[str] = None
    rule_id: str = ""
    rule_version: str = __version__


@dataclass(frozen=True)
class NormalizationResult:
    text: str
    source: str  # NFC source; span offsets refer to this string
    spans: tuple[NormalizationSpan, ...]


_BRACKET_KINDS = ("unit_group", "expression_quantity", "parenthesized_math")


def _number_before_bracket(raw: str) -> Optional[int]:
    """End of the number in "1 (300 MW", "5 (khoản 2)", "2 (2026-2030)", "4 (b)": a bracket of its own.

    The bracket must hold a number or a single letter. "2(3+4)" without a space, arithmetic
    ("1 (2 + 3) kg") and a unit group such as "5 (kgm/s)" stay whole.
    """
    head = re.match(rf"{_SIGNED}(?=[ \t]+\()", raw)
    if head is None:
        return None
    inside = raw[head.end():].lstrip(" \t")[1:]
    if not re.search(r"[0-9]", inside) and not re.fullmatch(r"[ \t]*[^\W\d_][ \t]*\)?", inside):
        return None
    if re.search(r"[0-9)][ \t]*[+*×÷^=<>≤≥≠±][ \t]*[0-9(]", inside):
        return None
    return head.end()


def _bracket_before_list(raw: str) -> int:
    """Length of a leading bracket closed before a list comma: "(2026-2030), 26.000 VND/1 USD" -> 11; else 0."""
    depth = 0
    for index, char in enumerate(raw):
        depth += {"(": 1, ")": -1}.get(char, 0)
        if depth <= 0:
            return index + 1 if index > 0 and re.match(r",[ \t]", raw[index + 1:]) else 0
    return 0


def _camel_parts(token: str, code: bool = True) -> list[str]:
    cuts = []
    # Code-style words are English words written together: localStorage, getElementById. A brand
    # keeps its spelling (YouTube, MacBook, iPhone, eBay); so do units such as kWh, mAh, mmHg.
    words = re.match(r"[a-z]{2,}(?=[A-Z][a-z])", token) if code else None
    code = words is not None and re.search(r"[aeiouy]", words.group()) is not None
    for i in range(1, len(token)):
        prev, char = token[i - 1], token[i]
        nxt = token[i + 1:i + 2]
        if char.isupper() and prev.islower() and nxt.isupper():
            if i >= 2 and token[i - 2].islower():
                cuts.append(i)
        elif char.isupper() and prev.isupper() and nxt.islower():
            # Require >=2 capitals in the preceding acronym; keep iPhone/MacBook.
            if i >= 2 and token[i - 2].isupper():
                cuts.append(i)
        elif code and char.isupper() and prev.islower() and nxt.islower():
            cuts.append(i)
    return [token[a:b] for a, b in zip([0] + cuts, cuts + [len(token)])]


@lru_cache(maxsize=32)
def _scanner(unit_keys: tuple[str, ...], max_token_chars: int, max_expression_chars: int, duration_format: str, numeric: bool = True, content_profile: str = "omnivoice") -> re.Pattern:
    units = unit_pattern(unit_keys)
    unit_end = r"(?!\w|[ \t]*[/^·*⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺])"
    # "20%-30%": the first endpoint belongs to the range reader, not to a quantity.
    range_end = r"(?![ \t]*[–-][ \t]*[0-9])"
    expression = r"[+−-]?(?:[0-9]|[.(])[0-9.,+−*/×÷^=<>≤≥≠±!() \t-]*[0-9)]"
    math_chars = r"[0-9.,+−*/×÷^=<>≤≥≠±!() \t-]"
    # Broad shapes intentionally consume invalid forms as a whole. Each reader
    # validates before expanding; an invalid date is never handed to numbers.
    unit_atom = r"(?:[^\W\d_]|[°%‰$€£])+(?:\^[+−-]?[0-9]+|[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+)?"
    grouped_value = rf"(?:{_SIGNED}[ \t]*[–-][ \t]*{_SIGNED}|{expression}|{_SIGNED})"
    prose_group = r"\([ \t]*[^\W\d_]{2,}[ \t]+[^\W\d_]{2,}"
    grouped_head = rf"(?:{unit_atom}(?:[ \t]*[/·*][ \t]*{unit_atom})*[ \t]*[/·*][ \t]*\(|(?!{prose_group})\((?=[ \t(]*(?:[^\W\d_]|[°%‰$€£])))"
    explicit_expression = expression.replace(r" \t", r" \t\r\n")
    explicit_math_chars = math_chars.replace(r" \t", r" \t\r\n")
    explicit_tail = rf"(?:[ \t]*{grouped_head}|(?:[ \t]*(?:{units}))?{unit_end})"
    shapes = [
        ("protected", _protected_regex(content_profile).pattern),
        ("long_token", rf"(?<!\S)\S{{{max_token_chars + 1},}}"),
        ("long_expression", rf"(?<!\w)(?={math_chars}{{{max_expression_chars + 1}}})[+−-]?[0-9(]{math_chars}*(?:{units})?"),
        ("context_math", rf"(?i:\b(?:{_MATH_WORDS}))(?:[ \t]+|[ \t]*:[ \t]*){explicit_expression}{explicit_tail}"),
        ("calendar_range", rf"(?<![\w/])(?:\(+[ \t]*)?{_FULL_DATE_RANGE}(?:[ \t]*\)+)?(?!\w|(?:[ \t]*\))*[ \t]*[/+*^=<>÷×-]|[ \t]*[–—][ \t]*[0-9])"),
        ("wrapped_date", rf"(?<!\w)\(+{_DATE_SPACE}{_FULL_DATE}{_DATE_SPACE}\)+(?!\w|(?:[ \t]*\))*[ \t]*[/+*^=<>÷×-])"),
        ("unit_group", rf"(?<!\w)(?:{_NUM}[ \t]*\((?=[ \t]*{_NUMBER_WORDS}[ \t]*\))|{grouped_value}[ \t]*{grouped_head})"),
        ("relation_math", rf"(?<!\w)(?={explicit_math_chars}*(?:[=<>≤≥≠]|!=)){explicit_expression}{explicit_tail}"),
        ("phone_extension", r"(?:(?i:\b(?:số điện thoại|điện thoại|sđt|hotline|tổng đài))[ \t]*:?[ \t]*)?(?<!\w)[+(]*[0-9][0-9 .()+-]*[0-9)][ \t]+(?i:máy lẻ|ext(?:ension)?\.?)[ \t]*:?[ \t]*[0-9]+(?!\w|[.-][0-9])"),
        ("identifier", rf"(?i:\b(?:{_ID_CUE}))\s*:?\s*[+(]?[0-9](?:[0-9 .()\-]*[0-9)])?(?![^\W\d_])"),
        ("iso_datetime", r"(?<!\w)[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:[.,][0-9]+)?)?(?:[Zz]|[+−-][0-9:]+)?(?![\w:+−-]|[.,][0-9])"),
        ("context_code", r"(?i:\b(?:mã đơn hàng|mã đơn|mã hồ sơ|mã sản phẩm|mã vận đơn|mã giao dịch|mã đặt chỗ|ID))\s*:?\s*(?=[A-Za-z0-9._/-]*[0-9])[A-Za-z0-9]+(?:[._/-][A-Za-z0-9]+)*(?!\w)"),
        ("parenthesized_phone", r"(?<!\w)(?:\+[1-9][0-9]{0,2}[ \t]*\([0-9]{1,4}\)[ \t]*[0-9]{3,4}[ .-]?[0-9]{3,4}|\(0[0-9]{2,3}\)[ \t]*[0-9]{3,4}[ .-]?[0-9]{3,4}|\(\+[1-9][0-9]{0,2}\)[ \t]*[0-9](?:[ .-]?[0-9]){6,11})(?!\w|[ .-]?[0-9])"),
        ("legal", r"(?<!\w)[0-9]+/[0-9]{4}/[A-ZĐ][A-ZĐa-zđ]*[0-9]{0,3}(?:[-/][A-ZĐ][A-ZĐa-zđ]*[0-9]{0,3})*(?!\w)"),
        ("plate", r"(?<!\w)[0-9]{2}[A-ZĐ][0-9]?-[0-9]{3}\.[0-9]{2}(?!\w)"),
        ("address", r"(?i:\b(?:số nhà|địa chỉ|nhà số))[ \t]*:?[ \t]*[0-9]+[A-Za-zĐđ]*(?:/[0-9]+[A-Za-zĐđ]*)+(?!\w|/[A-Za-z0-9])"),
        ("extended_version", r"(?:(?i:\b(?:phiên bản|version))[ \t]+[vV]?|\b[vV])[0-9]+(?:\.[0-9]+)+[+-][A-Za-z0-9][A-Za-z0-9.+-]*"),
        ("version_context", r"(?i:\b(?:phiên bản|version))\s+[vV]?[0-9]+(?:\.[0-9]+)+(?!\w|\.[0-9])"),
        ("quarter_year", r"(?i:\bquý)\s+(?:[0-9]+|[IVXLCDM]+)[/\-][0-9]{4}(?!\w|[/\-][0-9])"),
        ("word_date_range", rf"(?:(?i:\b(?:{_DATE_CUE})){_DATE_GAP})?(?<!\w)(?i:{_WORD_DATE_RANGE})(?!\w|[ \t]*[/.-][ \t]*[0-9])"),
        ("date_range", rf"(?i:\b(?:từ ngày|ngày))[ \t]+{_RANGE_DATE}(?:[ \t]+(?i:đến|tới)[ \t]+|[ \t]*[–-][ \t]*)(?:(?i:ngày)[ \t]+)?{_RANGE_DATE}(?!\w|[ \t]*/[ \t]*[0-9])"),
        ("shared_date_range", rf"(?:(?i:\bngày)[ \t]+[0-9]{{1,2}}[ \t]*[–—-][ \t]*{_RANGE_DATE}|(?<!\w)[0-9]{{1,2}}[ \t]*[–—-][ \t]*[0-9]{{1,2}}[ \t]*/[ \t]*[0-9]{{1,2}}[ \t]*/[ \t]*[0-9]{{1,4}})(?!\w|[ \t]*/[ \t]*[0-9])"),
        ("spaced_date", rf"(?:(?i:\b(?:{_DATE_CUE})){_DATE_GAP}(?=[0-9/. \t\r\n-]*(?:\s[/.-]|[/.-]\s))[0-9]{{1,4}}(?:{_DATE_SPACE}[/.-]{_DATE_SPACE}[0-9]{{1,4}}){{1,2}}|(?<!\w)(?=[0-9/. \t\r\n-]*(?:\s[/.-]|[/.-]\s)){_FULL_DATE})(?!\w|{_DATE_SPACE}[/.-]{_DATE_SPACE}[0-9])"),
        ("date", rf"(?:(?i:\b(?:{_DATE_CUE}))\s+)?(?<!\w)(?:[0-9]{{4}}-[0-9]{{1,2}}-[0-9]{{1,2}}|[0-9]{{1,2}}[/.-][0-9]{{1,2}}[/.-][0-9]{{4}})(?!\w|[/.\-][0-9])"),
        ("month_year", r"(?:(?i:\btháng)\s+)?(?<!\w)[0-9]{1,2}[/\-][0-9]{4}(?!\w|[/\-][0-9A-ZĐ])"),
        ("day_month", rf"(?i:\b(?:{_DATE_CUE}))\s+[0-9]{{1,2}}[/.\-][0-9]{{1,2}}(?!\w|[/.,\-][0-9]|[ \t]*[%‰])"),
        ("ratio", rf"(?i:\b(?:tỷ số|tỉ số|tỷ lệ|tỉ lệ|thắng|thua|hòa|màn[ \t]+hình|trận[ \t]+đấu[ \t]+kết[ \t]+thúc|kết[ \t]+quả[ \t]+trận[ \t]+đấu))[ \t]+{_NUM}[ \t]*[:/−–-][ \t]*{_NUM}(?!\w)"),
        ("full_time_range", r"(?<!\w)[0-9]+(?:h(?:[0-9]{1,2})?|:[0-9]{2}(?::[0-9]{2})?)[ \t]*[–-][ \t]*[0-9]+(?:h(?:[0-9]{1,2})?|:[0-9]{2}(?::[0-9]{2})?)(?:[ \t]*(?i:AM|PM))?(?!\w|:[0-9])"),
        ("spaced_duration", r"(?<!\w)[0-9]+h[ \t]+[0-9]+[mp](?:[ \t]+[0-9]+s)?(?!\w)"),
        ("time_range", r"(?<!\w)[0-9]{1,2}(?::[0-9]{2})?\s*[–-]\s*[0-9]{1,2}(?::[0-9]{2})?\s*(?:h|giờ)(?!\w)"),
        ("time_meridiem", r"(?<!\w)[0-9]{1,2}(?::[0-9]{2}(?::[0-9]{2})?)?[ \t]*(?i:AM|PM)\b"),
        ("duration", r"(?i:\b(?:thời lượng|kéo dài|trong|mất))\s+[0-9]+h(?:[0-9]{1,2}(?:[mp][0-9]{1,2}s?|[mp])?)?(?!\w)"),
        ("time", r"(?<!\w)[0-9]{1,2}(?::[0-9]{2}(?::[0-9]{2})?|[hg][0-9]{1,2}(?:[mp][0-9]{1,2}s?|[mp])?|h)(?!\w|:[0-9])"),
        ("dimensions", rf"(?i:\b(?:kích thước|khổ))[ \t]*:?[ \t]+{_SIGNED}(?:[ \t]*[x×][ \t]*{_SIGNED}){{1,3}}[ \t]*(?:{units}){unit_end}"),
        ("expression_quantity", rf"(?<!\w)(?=[0-9.,+−*/×÷^=<>≤≥≠±!() \t-]*[+*×÷^=<>≤≥≠±(]){expression}[ \t]*(?:{units}){unit_end}{range_end}"),
        ("malformed_leading_decimal", rf"(?<!\w)[+−-]?[.,]{{2,}}[0-9]+(?:[.,][0-9]+)*(?:[ \t]*(?:{units}))?{unit_end}"),
        ("quantity", rf"(?<!\w){_SIGNED}\s*(?:{units}){unit_end}{range_end}"),
        # Phone numbers first: "0912345678 KM/H" is a number and a speed, not one structured quantity.
        ("international_phone", r"(?<!\w)\+[1-9][0-9]{0,2}[ \t-]?(?:\([0-9]{1,4}\)|[0-9]{1,4})(?:[ .-][0-9]{2,4}){2,4}(?!\w|[ .-]?[0-9])"),
        ("phone", r"(?<!\w)(?:\+84(?:[ .-]?[0-9]){9,10}|0[35789][0-9](?:[ .-]?[0-9]){7}|0[2][0-9]{2}(?:[ .-]?[0-9]){7}|1[89]00(?:[ .-]?[0-9]){4,6})(?!\w|[ .-]?[0-9])"),
        ("structured_quantity", rf"(?<!\w){_SIGNED}[ \t]*(?:[^\W\d_]|[°%‰$€£])+(?:[ \t]*[·*/^⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺][ \t]*[^\s,;!?()]+)+"),
        ("ip", r"(?i:\b(?:IP|IPv4))\s*:?\s*[0-9]+(?:\.[0-9]+){3}(?!\w|\.[0-9])"),
        ("version", r"(?<!\w)[vV][0-9]+(?:\.[0-9]+)+(?!\w|\.[0-9])"),
        ("height", r"(?i:\b(?:cao|chiều cao))\s+[0-9]m[0-9]{1,2}(?!\w)"),
        ("weight", r"(?i:\b(?:nặng|cân nặng))\s+[0-9]+kg[0-9](?!\w)"),
        ("range", rf"(?<!\w){_SIGNED}(?:\s*(?:{units}))?\s*[–-]\s*{_SIGNED}\s*(?:{units}){unit_end}"),
        ("scientific", rf"(?<!\w){_SIGNED}[eE][+−-]*[0-9]+(?:[.,+−-]+[0-9]+)*(?:[ \t]*(?:{units}))?{unit_end}"),
        ("power", rf"(?<!\w){_NUM}[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+(?:[ \t]*(?:{units}))?(?!\w)"),
        ("currency_prefix", rf"(?<!\w){CURRENCY_PREFIX_PATTERN}(?!\w|[ \t]*[/^·*⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]|[.,][0-9])"),
        ("vulgar_fraction", rf"(?<!\w)[+−-]?[0-9]*[¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞](?:[ \t]*(?:{units}))?(?!\w)"),
        ("fraction_quantity", rf"(?<!\w)[0-9]+\s*/\s*[0-9]+\s*(?:{units}){unit_end}"),
        ("parenthesized_math", r"(?<!\w)(?=[0-9.,+−*/×÷^=<>≤≥≠±!() \t-]*\()(?=[0-9.,+−*/×÷^=<>≤≥≠±!() \t-]*[+−*/×÷^=<>≤≥≠±-])[+−-]?(?:[0-9]|\()(?:[0-9.+−*/×÷^=<>≤≥≠±!() \t-]|,(?![ \t]))*[0-9)](?!\w)"),
        ("equation", rf"(?<!\w)(?=[0-9., +*×÷^/−–=<>≤≥≠±!-]*(?:=|<|>|≤|≥|≠|[+*×÷^])){_SIGNED}(?:\s*(?:<=|>=|!=|[+*×÷^/=<>≤≥≠±−-])\s*{_SIGNED})+(?!\w|[.,][0-9])"),
        ("arithmetic", rf"(?<!\w){_SIGNED}(?:\s*(?:<=|>=|!=|[+*×÷^=<>≤≥≠±]|\s[−/-]\s)\s*{_SIGNED})+(?!\w|[.,][0-9])"),
        ("street_address", r"(?<!\w)[0-9]+(?:/[0-9]+)+(?:[A-Z])?(?=\s+(?:đường|phố|Nguyễn|Trần|Lê|Phạm|Hoàng|Huỳnh|Võ|Đặng|Bùi|Đỗ|Hồ|Ngô|Dương|Lý|Điện Biên|Cách Mạng)\b)"),
        ("fraction", r"(?<!\w)[0-9]+\s*/\s*[0-9]+(?!\w|/[0-9])"),
        ("roman", rf"[{_NUMERAL_CHARS}]|(?<![\w)])\((?:[ivx]{{1,5}}|[IVX]{{1,5}})\)(?=[ \t])|(?m:^)[ \t]*[IVX]{{1,6}}\.(?=[ \t])|"
                  rf"(?i:\b(?:{_REGNAL_TITLES}))[ \t]+(?:{_NAME_WORD}[ \t]+){{1,3}}[IVX]{{1,6}}\b|"
                  rf"(?i:\b(?:{_ROMAN_CUES}))[ \t]+[IVX]{{1,6}}(?:{_ROMAN_JOIN}[IVX]{{1,6}})*\b"),
        ("prefix", r"\b(?:PGS\.TS\.|GS\.TS\.|ThS\.|TS\.|BS\.|TP\.|Tp\.|TX\.|TT\.|Q\.|P\.|H\.)(?=\s|[0-9]|[A-ZĐ])"
                   r"|\b(?:PGS\.TS|GS\.TS)(?=\s|[0-9])"),
        ("standalone_unit", rf"(?<!\w){unit_pattern(unit_keys, compound_only=True)}(?!\w|[ \t]*[/^·*⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺])"),
        ("acronym_pair", rf"(?<!\w)(?:{unit_atom}(?:[ \t]*[/·*][ \t]*[^\s,;!?()]+)+(?:(?<=[0-9A-Z])\([A-Z0-9]{{1,3}}\)[0-9]{{0,3}}(?!\w))?"
                         rf"|{_AMP_CLUSTER}|[A-ZĐ]{{2,}}[a-zđ]?(?:-[A-ZĐ]+[a-zđ]?)+(?![\w-]))"),
        # A fallback consumes unsupported structured forms intact, including
        # invalid dates/times, chemistry, products and arbitrary identifiers.
        ("standalone_symbol", r"(?<=[ \t])[+&](?=[ \t])"),
        ("chemistry", r"\b(?:[A-Z][a-z]?[₀₁₂₃₄₅₆₇₈₉]*)*[A-Z][a-z]?[₀₁₂₃₄₅₆₇₈₉]+(?:[A-Z][a-z]?[₀₁₂₃₄₅₆₇₈₉]*)*\b"),
        ("numeric_structure", r"(?<!\w)[+−-]?[0-9]+(?:[.,:/−–-]+[0-9]+)+(?!\w)"),
        ("compound", r"(?<!\w)(?=[\w.,/:+−–-]*[0-9])[\w]+(?:[.,/:+−–-]+[\w]+)+|\b(?=\w*[0-9])(?=\w*[^\W\d_])\w+\b"),
        ("number", rf"(?<!\w){_SIGNED}(?!\w|[.,][0-9])"),
        ("word", rf"{_WORD}(?:\.{_WORD})*"),
        ("at", r"@"),
    ]
    if not numeric:
        word_kinds = {"protected", "long_token", "roman", "prefix", "standalone_unit", "acronym_pair", "word", "at", "standalone_symbol"}
        shapes = [(kind, pattern) for kind, pattern in shapes if kind in word_kinds]
    if numeric and duration_format != "clock":
        index = next(i for i, (kind, _) in enumerate(shapes) if kind == "time")
        shapes.insert(index, ("profile_time", r"(?<!\w)[0-9]+:[0-9:]+(?:[.,][0-9]+)?(?!\w|[.:][0-9])"))
    return re.compile("|".join(f"(?P<{kind}>{pattern})" for kind, pattern in shapes))


class Normalizer:
    def __init__(self, config: NormalizerConfig = DEFAULT_CONFIG):
        self.config = config
        self.units = {re.sub(r"\s+", "", key): value for key, value in
                      {**UNITS, "$": config.dollar_name, **config.unit_overrides}.items()}
        self.scanner = _scanner(tuple(sorted(self.units)), config.max_token_chars, config.max_expression_chars, config.duration_format, content_profile=config.content_profile)
        self._text_scanner = _scanner(tuple(sorted(self.units)), config.max_token_chars, config.max_expression_chars, config.duration_format, numeric=False, content_profile=config.content_profile)
        self._domain_scanner = domain_scanner(config.enabled_domains)
        self._unit_pattern = re.compile(unit_pattern(tuple(self.units)) + "$")
        self._range_pattern = re.compile(rf"({_SIGNED})\s*({unit_pattern(tuple(self.units))})?\s*([–-])\s*({_SIGNED})")

    def normalize(self, text: str) -> str:
        return self._normalize(text, trace=False).text

    def normalize_many(self, texts, *, with_trace: bool = False):
        """Yield one result per input with bounded per-item memory, in order."""
        if isinstance(texts, (str, bytes, dict)):
            raise TypeError("texts must be an iterable of strings, not a single string or mapping")
        if not isinstance(with_trace, bool):
            raise TypeError("with_trace must be a boolean")
        for text in texts:
            yield self.normalize_with_trace(text) if with_trace else self.normalize(text)

    def normalize_with_trace(self, text: str) -> NormalizationResult:
        return self._normalize(text, trace=True)

    def _normalize(self, text: str, *, trace: bool) -> NormalizationResult:
        if not isinstance(text, str):
            raise TypeError("text must be a string")
        source = _prepare_source(text, self.config.normalize_fullwidth_numbers, self.config.content_profile)
        if self.config.number_locale == "auto" and self.config.ambiguous_number == "infer":
            view = copy.copy(self)
            view.config = replace(self.config, ambiguous_number=infer_ambiguous_number(source))
            return view._scan(source, trace=trace)
        return self._scan(source, trace=trace)

    def _scan(self, source: str, *, trace: bool) -> NormalizationResult:
        numeric = any(char.isnumeric() for char in source)
        scanner = self.scanner if numeric else self._text_scanner
        # Acronyms use the word reader; index names are the news grammar
        # exception without digits. Avoid a full domain scan of ordinary prose.
        news_index = "news" in self.config.enabled_domains and "-Index" in source
        domains = self._domain_scanner if numeric or "CN" in source or news_index else None
        domain_match = domains.search(source) if domains else None
        out, spans, end = [], [], 0
        previous, joined, close_gloss = (None, ""), False, False
        bounds = vi.sentence_bounds(source)  # field cues are read within the sentence
        while end < len(source):
            match = scanner.search(source, end)
            # Cache the next domain candidate. Re-search only after a consumed
            # span passes it; rescanning the entire suffix per word is quadratic.
            if domain_match is not None and domain_match.start() < end:
                domain_match = domains.search(source, end)
            if domain_match is not None:
                if (match is None or domain_match.start() < match.start() or
                        (domain_match.start() == match.start() and match.lastgroup not in
                         ("protected", "long_token", "long_expression"))):
                    match = domain_match
            if match is None:
                break
            raw, kind = match.group(), match.lastgroup
            gap = source[end:match.start()]
            math_group = kind in ("context_math", "relation_math") and raw.endswith("(")
            match_end = consume_unit_group(source, match.end()) if kind == "unit_group" or math_group else match.end()
            if math_group:
                raw = source[match.start():match_end]
            if kind in ("unit_group", "long_expression"):
                raw = source[match.start():match_end].rstrip(" \t")
                match_end = match.start() + len(raw)
            before = source[max(0, match.start() - 256):match.start()]
            group_reason = None
            if kind.startswith("domain_"):
                spoken, group_reason = read_domain(kind, raw, self.config, self.units)
            elif kind == "unit_group":
                spoken = self._number_gloss(raw)
                if spoken is None:
                    spoken, group_reason = read_grouped_quantity(raw, self.config, self.units)
            else:
                sentence = (vi.sentence_around(source, bounds, match.start(), match_end)
                            if kind in ("word", "acronym_pair") and raw[1:2].isupper() else None)
                spoken = self._read(kind, raw, before, source[match_end:match_end + 256], sentence)
            if spoken == raw and kind in _BRACKET_KINDS and not _MATH_CUE.search(before):
                # "giai đoạn 1 (300 MW)", "Điều 5 (khoản 2)": no reading covers the whole span, so the
                # number is read alone and the bracket after it is scanned like the rest of the text.
                head = _number_before_bracket(raw)
                number = self._read("number", raw[:head], before, source[match.start() + head:match.start() + head + 256]) if head else None
                if number and number != raw[:head]:
                    match_end, raw, kind, spoken, group_reason = match.start() + head, raw[:head], "number", number, None
                elif _bracket_before_list(raw):
                    # "(2026-2030), 26.000 VND/1 USD": the bracket is read on its own ("(20-30)" as a range),
                    # or only "(" is taken and the scan goes on inside it; the amount after the comma follows.
                    bracket = raw[:_bracket_before_list(raw)]
                    inner = self._read("parenthesized_math", bracket, before,
                                       source[match.start() + len(bracket):match.start() + len(bracket) + 256])
                    if inner == bracket:
                        bracket, inner = "(", "("
                    match_end, raw, kind, spoken, group_reason = match.start() + len(bracket), bracket, "bracket", inner, None
            spoken = self._range_prefix(raw, spoken, before)
            gap_kind = "transliteration_hyphen"
            if close_gloss:  # the ")" of the gloss dropped on the previous token
                gap, close_gloss, gap_kind = re.sub(r"^[ \t]*\)", "", gap, count=1), False, "abbreviation_gloss"
            if spoken is _GLOSS:  # the "(" and the space before it go with the gloss
                gap, spoken, close_gloss, gap_kind = re.sub(r"[ \t]*\([ \t]*\Z", "", gap), "", True, "abbreviation_gloss"
            # Transliterated names: "Xê-út", "Bô-li-vi-a", "Jae-myung" -> spaces. A chain
            # starts at a capitalized syllable; "quốc phòng-an ninh", "drop-in" and
            # relations such as "Hàn-Mỹ" keep their hyphen. A relation whose right side
            # is rewritten in lower case ("Mỹ-NATO" -> "Mỹ - na tô") gets a spaced
            # dash, so a second pass cannot mistake it for a transliteration.
            prev_kind, prev_raw = previous
            chain = gap == "-" and prev_kind == "word" and (
                joined or (prev_raw[:1].isupper() and (len(prev_raw) == 1 or not prev_raw.isupper())))
            joined = False
            if chain and kind == "word" and raw[:1].islower():
                gap, joined = " ", True
            elif chain and spoken != raw and spoken[:1].islower():
                gap = " - "
            if trace and gap != source[end:match.start()]:  # source gaps + spans rebuild the text
                spans.append(NormalizationSpan(end, match.start(), gap_kind, source[end:match.start()], gap,
                                               "expanded", None, "vi." + gap_kind))
            out.append(self._style(gap))
            # Preserve protected spans byte-for-byte after NFC, even when a
            # model profile lowercases ordinary text or changes punctuation.
            if kind not in ("protected", "long_token", "long_expression", "unit_group") or (kind == "unit_group" and spoken != raw):
                spoken = self._style(spoken)
            out.append(spoken)
            if trace and (kind != "word" or spoken != raw):
                spans.append(NormalizationSpan(match.start(), match_end, kind, raw, spoken,
                                               "expanded" if spoken != raw else "preserved",
                                               {"long_token": "resource_limit" if spoken == raw else "long_integer_digits", "extended_version": "unsupported_version_suffix",
                                                "structured_quantity": "unsupported_or_invalid_unit", "long_expression": "resource_limit",
                                                "unit_group": group_reason, "profile_time": "invalid_time" if spoken == raw else ("explicit_clock_context" if _CLOCK_CUE.search(before) else "configured_duration")}.get(kind, group_reason), "vi." + kind))
            end = match_end
            previous = (kind, raw)
        tail = source[end:]
        if close_gloss:
            tail = re.sub(r"^[ \t]*\)", "", tail, count=1)
            if trace and tail != source[end:]:
                spans.append(NormalizationSpan(end, len(source), "abbreviation_gloss", source[end:], tail,
                                               "expanded", None, "vi.abbreviation_gloss"))
        out.append(self._style(tail))
        return NormalizationResult("".join(out), source, tuple(spans))

    def _style(self, text: str) -> str:
        if not self.config.preserve_case:
            text = text.lower()
        if not self.config.preserve_punctuation:
            text = text.replace("?", ".").replace("!", ",")
        return text

    def _int(self, value: str) -> str:
        return read_integer(value, self.config)

    def _num(self, value: str) -> Optional[str]:
        return read_number(value.strip(), self.config)

    def _month(self, value: str) -> str:
        return "tư" if int(value) == 4 else self._int(value)

    def _ordinal(self, value: str) -> str:
        """After "thứ": 1 -> nhất, 4 -> tư, otherwise the cardinal."""
        return {"1": "nhất", "4": "tư"}.get(value.lstrip("0") or "0", self._int(value))

    def _letters(self, run: str) -> str:
        """Every letter of a run separately, in the configured style."""
        if self.config.acronym_mode == "latin":
            return latin_letters(run)
        if self.config.acronym_mode == "spell":
            return spell_letters(run)
        return run

    def _code_number(self, digits: str) -> str:
        """Digits inside a code: 16 -> mười sáu, 400 -> bốn trăm, 127 -> một hai bảy, 05 -> không năm."""
        if len(digits) > 1 and digits.startswith("0"):
            return read_digits(digits)
        if len(digits) <= 2 or (len(digits) <= 4 and re.fullmatch(r"[1-9][0-9]?00+", digits)):
            return self._int(digits)
        return read_digits(digits)

    def _range_prefix(self, raw: str, spoken: str, before: str) -> str:
        """A dash range means "từ A đến B" unless a framing word already precedes it."""
        if (not self.config.range_prefix or spoken == raw or " đến " not in spoken
                or not _RANGE_SOURCE.search(raw) or _framed(before)):
            return spoken
        # Readers may keep a cue or parenthesis in front: "giá 20k-30k", "(20 - 30%".
        common = 0
        while common < min(len(raw), len(spoken)) and raw[common] == spoken[common]:
            common += 1
        cut = max(spoken.rfind(" ", 0, common), spoken.rfind("(", 0, common), spoken.rfind("\t", 0, common)) + 1
        lead, body = spoken[:cut], spoken[cut:]
        if not _NUMBER_START.match(body) or _framed(before + lead):
            return spoken
        return lead + self.config.range_prefix + " " + body

    def _doc_symbol(self, match: re.Match) -> str:
        """02/NQ-CP -> không hai N Q C P; 15/2020/NĐ-CP -> mười lăm năm hai nghìn không trăm hai mươi N Đ C P."""
        number, year, code = match.groups()
        out = [read_digits(number) if len(number) > 1 and number.startswith("0") else self._int(number)]
        if year:
            out.append("năm " + self._int(year))
        for run in re.findall(r"[A-ZĐa-zđ]+|[0-9]+", code):
            out.append(self._code_number(run) if run.isdigit() else self._letters(run))
        return " ".join(out)

    def _designator(self, raw: str) -> str:
        """AN/APX-127(V)1 -> A N A P X một hai bảy V một."""
        return " ".join(self._code_number(t) if t.isdigit() else self._letters(t)
                        for t in re.findall(r"[A-Z]+|[0-9]+", raw))

    def _code_group(self, raw: str) -> str:
        """NĐ-CP -> N Đ C P (document codes); EU-ASEAN -> EU-a xê an (each acronym by its own policy)."""
        segments = raw.split("-")
        word_like = any(s in COMMON_ABBREVIATIONS or s in self.config.abbreviation_overrides
                        or (len(s) >= 4 and s.isupper() and classify_acronym(s) == "keep") for s in segments)
        if self.config.acronym_mode != "latin" or word_like:
            # A capitalized word before a lower-case reading gets a spaced dash
            # ("Hồ Chí Minh - thành phố"), so a second pass cannot join them as a name.
            out = self._abbreviation(segments[0])
            for segment in segments[1:]:
                reading, last = self._abbreviation(segment), out.rsplit(" ", 1)[-1]
                out += (" - " if last[:1].isupper() and not last.isupper() and reading[:1].islower() else "-") + reading
            return out
        return " ".join(latin_letters(s) for s in segments)

    def _roman_value(self, numeral: str) -> Optional[int]:
        if not numeral or not _ROMAN_VALID.fullmatch(numeral):
            return None
        values = [_ROMAN_VALUE[c] for c in numeral]
        return sum(-v if i + 1 < len(values) and v < values[i + 1] else v for i, v in enumerate(values))

    def _roman(self, raw: str, before: str, after: str) -> str:
        list_comma = "," if after[:1] in (" ", "\t") else ""
        if len(raw) == 1:
            # Ⅱ -> hai; ① ❶ ⑴ -> một, (list markers); ⒈ -> một.
            try:
                value = unicodedata.numeric(raw)
            except (TypeError, ValueError):
                return raw
            if value != int(value) or value < 0:
                return raw
            spoken = self._int(str(int(value)))
            name = unicodedata.name(raw, "")
            if "FULL STOP" in name:
                return spoken + "."
            return spoken if "ROMAN NUMERAL" in name else spoken + list_comma
        if raw.startswith("("):
            # (i) (ii) (iv); uppercase (I) (II) only in list position.
            numeral = raw[1:-1]
            # Lower-case output cannot keep "(I)" apart from "(i)" on a second pass.
            if numeral.isupper() and self.config.preserve_case and not re.search(r"(?:^|\n|[:;])[ \t]*$", before):
                return raw
            value = self._roman_value(numeral.upper())
            return self._int(str(value)) + list_comma if value and value <= 20 else raw
        heading = re.fullmatch(r"([ \t]*)([IVX]+)\.", raw)
        if heading:
            # "II. Nội dung"; a single letter only before an all-caps heading
            # ("I. MỞ ĐẦU"), since "V. Putin" is a personal initial.
            value = self._roman_value(heading[2])
            if value is None or (len(heading[2]) == 1 and not re.match(rf"[ \t]+[{_UPPER_VI}]{{2,}}\b", after)):
                return raw
            return heading[1] + self._int(str(value)) + "."
        regnal = re.fullmatch(rf"((?i:{_REGNAL_TITLES})[ \t]+(?:{_NAME_WORD}[ \t]+){{1,3}})([IVX]+)", raw)
        if regnal:
            value = self._roman_value(regnal[2])
            if value is None:
                return raw
            return regnal[1] + ("đệ " + _SINO_ORDINAL[value] if value <= 10 else self._int(str(value)))
        cue = re.match(rf"(?i:{_ROMAN_CUES})", raw)
        rest = raw[cue.end():]
        parts = re.findall(rf"{_ROMAN_JOIN}|[ \t]+|[IVX]+", rest)
        numerals = [p for p in parts if re.fullmatch(r"[IVX]+", p)]
        values = [self._roman_value(n) for n in numerals]
        if any(v is None for v in values) or (cue.group().casefold() == "quý" and not all(1 <= v <= 4 for v in values)):
            return raw
        # A single capital after a cue may start a spelled acronym ("nhóm X A I").
        if len(numerals) == 1 and len(numerals[0]) == 1 and re.match(rf"[ \t]+[{_UPPER_VI}](?:[ \t]|$)", after):
            return raw
        speak = self._ordinal if cue.group().casefold() == "thứ" else self._int
        word = _ROMAN_CUE_WORDS.get(cue.group().casefold(), cue.group())
        out, index, repeat = [word], 0, word.lower()
        for part in parts:
            if re.fullmatch(r"[IVX]+", part):
                out.append((" " + repeat + " " if index else "") + speak(str(values[index])))
                index += 1
            elif "," in part:
                out.append(",")
            elif re.fullmatch(r"[ \t]*[–-][ \t]*", part):
                out.append(" đến")
            elif part.strip():
                out.append(" " + part.strip())
            else:
                out.append(" ")
        return "".join(out)

    def _plural_acronym(self, raw: str) -> Optional[str]:
        """CEOs, NGOs, ATMs: Vietnamese does not inflect the plural."""
        match = re.fullmatch(r"([A-ZĐ]{2,})s", raw)
        return match[1] if match and self.config.acronym_mode != "preserve" else None

    def _code(self, raw: str, *, spell: bool = False) -> str:
        parts = re.findall(r"[^\W\d_]+|[0-9]+|[^\w\s]", raw)
        # Rule L1: codes whose letters are all single (30A-123.45) keep Vietnamese letter names.
        latin = self.config.acronym_mode == "latin" and any(len(p) > 1 for p in parts if p.isalpha())
        out = []
        for part in parts:
            if part.isascii() and part.isdigit():
                out.append(read_digits(part))
            elif part.isalpha():
                if spell or self.config.acronym_mode != "preserve":
                    out.append(latin_letters(part) if latin else spell_letters(part))
                else:
                    out.append(part)
            else:
                out.append({"/": "xuyệt", "-": "gạch ngang", ".": "chấm", "+": "cộng"}.get(part, part))
        return " ".join(out)

    def _plain_word(self, raw: str, before: str, after: str) -> str:
        """Lower-case and capitalized words: v.v., Cty, Tp HCM, transliterated x-clusters, Moscow."""
        if self.config.abbreviation_policy == "common":
            reading = vi.SPECIAL.get(raw) or places.EXONYMS.get(raw) or vi.contextual(raw, before, after)
            if reading:
                return reading
        return _transliteration(raw) if "x" in raw or "X" in raw else raw

    def _vi_word(self, raw: str, before: str, after: str, sentence: Optional[str] = None) -> Optional[str]:
        """A Vietnamese abbreviation read by meaning (abbreviation_policy "common"), or None."""
        if self.config.abbreviation_policy != "common":
            return None
        if raw in vi.SPECIAL:
            return vi.SPECIAL[raw]  # CTy, V.v
        if vi.HEAD.matches(before, after) and raw in vi.SECTOR_KEYS:
            return vi.SECTOR_KEYS[raw]  # Bộ TC, Sở TP
        # The context and the field decide first: CT is a scan in "chụp CT 64 lát cắt",
        # PV a solar panel in "tấm pin PV"; without a matching context the default applies.
        reading = vi.contextual(raw, before, after, sentence)
        if reading == vi.KEEP:
            return self._unexpanded(raw)
        reading = reading or vi.lookup(raw)
        if reading is None and "." in raw:
            # Dotted title chains: GS.TSKH, ThS.BS, BS.CKII.
            readings = [vi.TITLES.get(part) or vi.lookup(part) for part in raw.split(".")]
            if all(readings):
                reading = " ".join(readings)
        return reading

    def _unexpanded(self, token: str) -> str:
        """The acronym policy alone, without any expansion."""
        if self.config.acronym_mode == "latin":
            return latin_letters(token) if classify_acronym(token) == "spell" else token
        if self.config.acronym_mode == "spell" and is_spell_candidate(token):
            return spell_letters(token)
        return token

    def _vi_cluster(self, raw: str, before: str, after: str) -> Optional[str]:
        """VH-TT-DL, VH,TT&DL, GD & ĐT, Bộ LĐ-TB&XH, KT-XH-QP-AN; Đ/c, v/v."""
        if self.config.abbreviation_policy != "common":
            return None
        special = vi.SPECIAL_PAIRS.get(raw)
        if special or not (re.fullmatch(_AMP_CLUSTER, raw) or _CODE_GROUP.fullmatch(raw)):
            return special
        key = vi.cluster_key(raw)
        if vi.HEAD.matches(before, after) and key in vi.SECTOR_KEYS:
            return vi.SECTOR_KEYS[key]
        return vi.lookup(raw) or vi.components(raw)

    def _gloss(self, raw: str, reading: str, before: str, after: str) -> str:
        """'Thông tấn xã Việt Nam (TTXVN)': a gloss right after its own name adds nothing
        when read aloud, so it is dropped with its parentheses (preserve mode keeps it)."""
        if (reading != raw and re.search(r"\([ \t]*\Z", before) and re.match(r"[ \t]*\)", after)
                and reading.casefold() in before.casefold()):
            return raw if self.config.acronym_mode == "preserve" else _GLOSS
        return reading

    def _amp_cluster(self, raw: str) -> str:
        """Unlisted "&" clusters, each part by its own policy: AT & T -> A T và T."""
        parts = re.split(r"([ \t]*&[ \t]*|[-,])", raw)
        joins = {"&": " và ", "-": " - ", ",": ", "}
        return "".join(joins[part.strip()] if index % 2 else self._abbreviation(part)
                       for index, part in enumerate(parts))

    def _abbreviation(self, token: str, seen: tuple[str, ...] = ()) -> str:
        if token in seen:
            return token
        override = self.config.abbreviation_overrides.get(token)
        policy = self.config.abbreviation_policy
        expansion = override
        if not expansion and policy == "common":
            expansion = (COMMON_ABBREVIATIONS.get(token) or COMMON_ABBREVIATIONS.get(token.replace(".", ""))
                         or vi.lookup(token))
            if not expansion and self.config.acronym_mode == "spell":
                expansion = LEGACY_SAY.get(token)
        elif not expansion and policy == "extended":
            keys = (token, token.replace(".", "").replace("-", ""))
            readings = next((_abbreviations()[k] for k in keys if k in _abbreviations()), ())
            news_reading = NEWS_ABBREVIATIONS.get(token) if "news" in self.config.enabled_domains else None
            expansion = news_reading or (readings[0] if token.isupper() and len(readings) == 1 and len(token) >= 2 else None)
        if expansion:
            # Resolve uppercase dictionary references without rescanning numbers
            # or punctuation; cap cycles and user-defined self references.
            if len(seen) >= 8:
                return token
            return re.sub(_WORD, lambda m: self._abbreviation(m.group(), seen + (token,))
                          if m.group().isupper() and m.group() != token else m.group(), expansion)
        if self.config.acronym_mode == "spell" and is_spell_candidate(token):
            return spell_letters(token.replace(".", ""))
        if self.config.acronym_mode == "latin" and classify_acronym(token) == "spell":
            return latin_letters(token)
        return token

    def _date(self, raw: str) -> str:
        start = re.search(r"[0-9]", raw)
        if start is None:
            return raw
        numeric, prefix = raw[start.start():], raw[:start.start()]
        groups = re.split(r"[/.-]", numeric)
        separators = re.findall(r"[/.-]", numeric)
        if len(groups) not in (2, 3) or len(set(separators)) != 1 or any(not re.fullmatch(r"[0-9]{1,4}", g) for g in groups):
            return raw
        if len(groups) == 3:
            if len(groups[0]) == 4:
                y, m, d = groups
            else:
                d, m, y = groups
            year = int(y)
            if not 1 <= year <= 9999:
                return raw
        else:
            d, m = groups
            y, year = None, 2000  # permit Feb 29 when the year is unspecified
        if not 1 <= int(m) <= 12 or not 1 <= int(d) <= calendar.monthrange(year, int(m))[1]:
            return raw
        out = prefix + self._int(d) + " tháng " + self._month(m)
        return out + (" năm " + self._int(y) if y else "")

    def _date_range(self, raw: str, *, shared: bool) -> str:
        if shared:
            match = re.search(r"([0-9]{1,2})[ \t]*[–—-][ \t]*([0-9]{1,2})[ \t]*/[ \t]*([0-9]{1,2})(?:[ \t]*/[ \t]*([0-9]{1,4}))?$", raw)
            first, last, month, year = match.groups()
            if year is not None and len(year) != 4:
                return raw
            dates = [f"{day}/{month}" + (f"/{year}" if year else "") for day in (first, last)]
            if int(first) > int(last) or any(self._date(d) == d for d in dates):
                return raw
            return raw[:match.start()] + self._int(first) + " đến " + self._date(dates[1])
        dates = list(re.finditer(_RANGE_DATE, raw))
        first, last = (re.sub(r"[ \t]+", "", m.group()) for m in dates)
        if any(len(d.split("/")) == 3 and len(d.split("/")[2]) != 4 for d in (first, last)):
            return raw
        years = [d.split("/")[2] for d in (first, last) if len(d.split("/")) == 3]
        validation = [d + "/" + years[0] if years and len(d.split("/")) == 2 else d for d in (first, last)]
        if any(self._date(d) == d for d in validation):
            return raw
        if years:
            order = [tuple(int(x) for x in d.split("/")[::-1]) for d in validation]
            if order[0] > order[1]:
                return raw
        return (raw[:dates[0].start()] + self._date(first)
                + re.sub(r"[ \t]*[–-][ \t]*", " đến ", raw[dates[0].end():dates[1].start()]) + self._date(last))

    def _calendar_range(self, raw: str) -> str:
        core = raw.strip("() \t")
        if raw.count("(") != raw.count(")"):
            return raw
        dates = list(re.finditer(_FULL_DATE, core))
        if len(dates) != 2:
            return raw
        spoken, order = [], []
        for match in dates:
            date = re.sub(r"\s+", "", match.group())
            parts = re.split(r"[/.-]", date)
            if len(parts[0]) != 4 and len(parts[-1]) != 4:
                return raw
            reading = self._date(date)
            if reading == date:
                return raw
            spoken.append(reading)
            order.append(tuple(map(int, parts if len(parts[0]) == 4 else parts[::-1])))
        if order[0] > order[1]:
            return raw
        # Parentheses here are editorial punctuation, not arithmetic grouping.
        start = raw.index(core)
        return raw[:start] + " đến ".join(spoken) + raw[start + len(core):]

    def _word_date_range(self, raw: str) -> str:
        match = re.search(_WORD_DATE_RANGE + "$", raw, re.I)
        first, last, month, year = match.groups()
        if any(len(v) > 2 for v in (first, last, month)) or (year is not None and len(year) != 4):
            return raw
        dates = [f"{day}/{month}" + (f"/{year}" if year else "") for day in (first, last)]
        if int(first) > int(last) or any(self._date(d) == d for d in dates):
            return raw
        return raw[:match.start()] + self._int(first) + " đến " + self._date(dates[1])

    def _iso_datetime(self, raw: str) -> str:
        canonical = raw.replace("t", "T").replace("z", "Z").replace("−", "-")
        canonical = re.sub(r"([+-])([0-9]{2})([0-9]{2})$", r"\1\2:\3", canonical)
        try:
            datetime.fromisoformat(canonical.replace("Z", "+00:00").replace(",", "."))
        except ValueError:
            return raw
        match = re.fullmatch(r"([0-9-]+)T([0-9]{2}):([0-9]{2})(?::([0-9]{2}(?:[.,][0-9]+)?))?(Z|[+-][0-9]{2}:[0-9]{2})?", canonical)
        if match is None:
            return raw
        date, hour, minute, second, zone = match.groups()
        clock = self._int(hour) + " giờ"
        if int(minute) or second is not None:
            clock += " " + self._int(minute) + " phút"
        if second is not None:
            clock += " " + read_number(second.replace(",", "."), replace(self.config, number_locale="en")) + " giây"
        spoken = self._date(date) + " lúc " + clock
        if zone:
            spoken += ", giờ quốc tế"
            if zone != "Z":
                hours, minutes = zone[1:].split(":")
                if int(hours) > 23 or int(minutes) > 59:
                    return raw
                spoken += (" cộng " if zone[0] == "+" else " trừ ") + self._int(hours) + " giờ"
                if int(minutes):
                    spoken += " " + self._int(minutes) + " phút"
        return spoken

    def _time(self, raw: str, *, duration: bool = False) -> Optional[str]:
        values = re.findall(r"[0-9]+", raw)
        if any(len(value) > 6 for value in values):
            return None
        h = int(values[0])
        if (h > 23 and not duration) or any(int(v) > 59 for v in values[1:]):
            return None
        out = self._int(values[0]) + " giờ"
        if len(values) > 1 and (int(values[1]) or len(values) == 3):
            out += " " + self._int(values[1]) + " phút"
        if len(values) == 3:
            out += " " + self._int(values[2]) + " giây"
        return out

    def _colon_time(self, raw: str, before: str) -> Optional[str]:
        # Explicit clock cues take priority over a duration source profile.
        clock_cue = _CLOCK_CUE.search(before)
        if self.config.duration_format == "clock" or clock_cue:
            return self._time(raw)
        parts = raw.split(":")
        if len(parts) != 2 or any(not p.isascii() or not p.isdigit() or len(p) > 6 for p in parts):
            return None
        first, second = parts
        if len(second) != 2 or int(second) > 59:
            return None
        if self.config.duration_format == "hh:mm":
            return self._time(raw, duration=True)
        out = []
        if int(first):
            out.append(self._int(first) + " phút")
        if int(second) or not out:
            out.append(self._int(second) + " giây")
        return " ".join(out)

    def _read(self, kind: str, raw: str, before: str, after: str, sentence: Optional[str] = None) -> str:
        if (kind == "word" and len(raw) > 1 and raw not in self.config.abbreviation_overrides
                and self.units.get(raw, raw) != raw and _PER_UNIT.search(before)):
            return self.units[raw]  # mỗi kl -> mỗi ki lô lít, mỗi kg -> mỗi ki lô gam
        if kind == "word" and raw not in self.config.abbreviation_overrides:
            if raw.islower() or (raw.istitle() and not raw.isupper()):
                return self._plain_word(raw, before, after)
        if kind == "protected":
            if self.config.link_mode == "speak" and re.fullmatch(_LINK, raw, re.IGNORECASE):
                return self._link(raw)
            if self.config.link_mode == "domain":
                return web.read_domain(raw) or raw  # chinhphu.vn/TG -> chính phủ chấm vi en
            return raw
        if kind == "long_token" and raw.isascii() and raw.isdigit():
            return read_digits(raw)
        if kind == "structured_quantity":
            pair = self._code_pair(raw)  # 5G/6G looks like a number and a rate unit
            if pair:
                return pair
        if kind in ("long_token", "long_expression", "unit_group", "extended_version", "structured_quantity", "malformed_leading_decimal"):
            return raw
        if kind == "calendar_range":
            return (read_expression(raw, self.config) or raw) if _MATH_CUE.search(before) else self._calendar_range(raw)
        if kind == "wrapped_date":
            if _MATH_CUE.search(before):
                return read_expression(raw, self.config) or raw
            if raw.count("(") != raw.count(")"):
                return raw
            core = re.sub(r"\s+", "", raw.strip("() \t\r\n"))
            parts = re.split(r"[/.-]", core)
            if len(parts[0]) != 4 and len(parts[-1]) != 4:
                return raw
            spoken = self._date(core)
            return "(" * raw.count("(") + spoken + ")" * raw.count(")") if spoken != core else raw
        if kind in ("context_math", "relation_math"):
            if len(raw) > self.config.max_expression_chars:
                return raw
            start = re.search(r"[+−-]?[0-9]|[.(]", raw).start() if kind == "context_math" else 0
            body = raw[start:]
            candidate = parse_expression_quantity(body, self._unit_pattern)
            if re.search(r"[^\W\d_]|[°%‰$€£]", body) and "(" in body and candidate is None:
                spoken, _ = read_grouped_quantity(body, self.config, self.units)
            else:
                spoken = candidate.speak(self.config, self.units) if candidate else read_expression(body, self.config)
            return raw[:start] + spoken if spoken else raw
        if kind == "word_date_range":
            return self._word_date_range(raw)
        if kind == "standalone_symbol":
            return "cộng" if raw == "+" else "và"
        if kind in ("spaced_date", "date", "month_year", "shared_date_range") and _MATH_CUE.search(before):
            return read_expression(raw, self.config) or raw
        if kind == "spaced_date":
            start = re.search(r"[0-9]", raw).start()
            numeric = re.sub(r"\s+", "", raw[start:])
            parts = re.split(r"[/.-]", numeric)
            if len(parts) == 3 and not (len(parts[0]) == 4 or len(parts[2]) == 4):
                return raw
            canonical = raw[:start] + numeric
            spoken = self._date(canonical)
            if spoken == canonical:
                return (self._day_range(raw) if start else None) or raw
            return spoken
        if kind == "expression_quantity" and raw.startswith("(") and raw.count("(") > raw.count(")"):
            opened = len(raw) - len(raw.lstrip("( \t"))
            core = raw[opened:]
            inner = "range" if self._range_pattern.match(core) else "quantity"
            spoken = self._read(inner, core, before + raw[:opened], after) if self._unit_pattern.search(core) else None
            return raw[:opened] + spoken if spoken and spoken != core else raw
        if kind in ("expression_quantity", "dimensions"):
            start = re.search(r"[+−-]?[0-9]|[.(]", raw).start() if kind == "dimensions" else 0
            candidate = parse_expression_quantity(raw[start:], self._unit_pattern, dimensions=kind == "dimensions")
            if candidate is None:
                return raw
            spoken = candidate.speak(self.config, self.units)
            return raw[:start] + spoken if spoken else raw
        if kind == "phone_extension":
            extension = re.search(r"(?i: máy lẻ| ext(?:ension)?\.?)[ \t]*:?[ \t]*([0-9]+)$", raw.replace("\t", " "))
            if extension is None:
                return raw
            head = raw[:extension.start()].rstrip()
            first = re.search(r"[+(]*[0-9]", head)
            phone = head[first.start():]
            digits = re.sub(r"[^0-9]", "", phone)
            if not 7 <= len(digits) <= 15 or len(extension[1]) > 8 or phone.count("(") != phone.count(")"):
                return raw
            prefix = re.sub(_WORD, lambda m: self._abbreviation(m.group()), head[:first.start()])
            return prefix + ("cộng " if "+" in phone else "") + read_digits(digits) + " máy lẻ " + read_digits(extension[1])
        if kind == "identifier":
            m = re.search(r"[+(]?[0-9]", raw)
            numeric = raw[m.start():]
            if numeric.count("(") != numeric.count(")"):
                return raw
            prefix = re.sub(_WORD, lambda m: self._abbreviation(m.group()), raw[:m.start()])
            return prefix + ("cộng " if numeric.startswith("+") else "") + read_digits(numeric)
        if kind == "context_code":
            match = re.search(r"[A-Za-z0-9]+(?:[._/-][A-Za-z0-9]+)*$", raw)
            prefix = re.sub(_WORD, lambda m: self._abbreviation(m.group()), raw[:match.start()])
            return prefix + self._code(match.group(), spell=True)
        if kind == "legal" and self.config.acronym_mode != "preserve" and _DOC_SYMBOL.fullmatch(raw):
            return self._doc_symbol(_DOC_SYMBOL.fullmatch(raw))
        if kind in ("legal", "plate"):
            # Legal acronyms use their unambiguous institutional expansion;
            # otherwise the next pass would expand them after code separators.
            spoken = self._code(raw)
            if kind == "legal" and self.config.acronym_mode == "preserve":
                spoken = re.sub(_WORD, lambda m: self._abbreviation(m.group()), spoken)
            return spoken
        if kind == "street_address":
            return self._address_number(raw)
        if kind == "address":
            m = re.search(r"[0-9]", raw)
            return raw[:m.start()] + self._address_number(raw[m.start():])
        if kind == "version_context":
            match = re.search(r"[vV]?[0-9]+(?:\.[0-9]+)+$", raw)
            version = match.group()
            prefix = raw[:match.start()]
            if version[0] in "vV":
                prefix += version[0] + " "
                version = version[1:]
            return prefix + " chấm ".join(self._component(p) for p in version.split("."))
        if kind == "quarter_year":
            match = re.search(r"([0-9]+|[IVXLCDM]+)[/\-]([0-9]{4})$", raw)
            quarter, year = match.groups()
            quarter = {"I": "1", "II": "2", "III": "3", "IV": "4"}.get(quarter, quarter)
            if quarter not in ("1", "2", "3", "4") or not year.strip("0"):
                return raw
            return raw[:match.start()] + self._int(quarter) + " năm " + self._int(year)
        if kind == "iso_datetime":
            return self._iso_datetime(raw) if self.config.datetime_mode == "speak" else raw
        if kind in ("date_range", "shared_date_range"):
            return self._date_range(raw, shared=kind == "shared_date_range")
        if kind == "day_month":
            canonical = raw.replace(".", "/")  # "tối 27.9" is a date only with a cue
            spoken = self._date(canonical)
            if spoken != canonical:
                return spoken
            return self._day_range(raw) or raw
        if kind == "date":
            return self._date(raw)
        if kind == "month_year":
            m = re.search(r"([0-9]+)[-/]([0-9]+)$", raw)
            month, year = m.groups()
            if not raw[:m.start()] and "/" in raw and _DOC_NUMBER_CUE.search(before):
                return self._component(month) + " năm " + self._int(year)  # Nghị định 12/2020
            if not 1 <= int(month) <= 12 or not 1 <= int(year) <= 9999:
                return raw
            prefix = raw[:m.start()] or "tháng "
            return prefix + self._month(month) + " năm " + self._int(year)
        if kind == "time_meridiem":
            match = re.fullmatch(r"([0-9]{1,2})(:[0-9]{2}(?::[0-9]{2})?)?[ \t]*(AM|PM)", raw, re.I)
            hour, tail, suffix = match.groups()
            if not 1 <= int(hour) <= 12:
                return raw
            hour = int(hour) % 12 + (12 if suffix.upper() == "PM" else 0)
            return self._time(str(hour) + (tail or "")) or raw
        if kind == "duration":
            match = re.search(r"[0-9].*$", raw)
            spoken = self._time(match.group(), duration=True)
            return raw[:match.start()] + spoken if spoken else raw
        if kind == "profile_time":
            return self._colon_time(raw, before) or raw
        if kind == "time":
            # A preceding ratio/score keyword would have matched its own rule.
            return (self._colon_time(raw, before) if ":" in raw else self._time(raw, duration=bool(re.fullmatch(r"[0-9]+h", raw)))) or raw
        if kind == "spaced_duration":
            return self._time(raw, duration=True) or raw
        if kind == "full_time_range":
            if re.search(r"(?i:AM|PM)$", raw):
                return raw  # a shared meridiem does not identify both endpoints
            left, right = (self._colon_time(value.strip(), before) if ":" in value else self._time(value) for value in re.split(r"[–-]", raw))
            return left + " đến " + right if left and right else raw
        if kind == "time_range":
            a, b = re.split(r"[–-]", re.sub(r"\s*(?:h|giờ)$", "", raw))
            left, right = self._time(a), self._time(b)
            return left + " đến " + right if left and right else raw
        if kind in ("international_phone", "parenthesized_phone"):
            digits = re.sub(r"[^0-9]", "", raw)
            if not 7 <= len(digits) <= 15 or raw.count("(") != raw.count(")"):
                return raw
            return ("cộng " if "+" in raw else "") + read_digits(digits)
        if kind == "phone":
            return ("cộng " if raw.startswith("+") else "") + read_digits(raw)
        if kind == "ip":
            match = re.search(r"[0-9]+(?:\.[0-9]+){3}$", raw)
            parts = match.group().split(".")
            if any(len(p) > 3 or int(p) > 255 for p in parts):
                return raw
            return self._cue_prefix(raw[:match.start()]) + " chấm ".join(self._component(p) for p in parts)
        if kind == "version":
            return raw[0] + " " + " chấm ".join(self._component(p) for p in raw[1:].split("."))
        if kind in ("height", "weight"):
            m = re.search(r"([0-9]+)(m|kg)([0-9]+)", raw)
            a, unit, b = m.groups()
            if unit == "m":
                b = b.ljust(2, "0")
                tail = self._int(b) + " xăng ti mét"
            else:
                tail = self._int(b + "00") + " gam"
            return raw[:m.start()] + self._int(a) + " " + self.units[unit] + " " + tail
        if kind == "fraction_quantity":
            unit = self._unit_pattern.search(raw)
            a, b = re.split(r"\s*/\s*", raw[:unit.start()].strip())
            if not b.strip("0"):
                return raw
            reading = read_unit(unit.group(), self.units, self.config)
            return self._int(a) + " " + self.config.fraction_word + " " + self._int(b) + " " + reading if reading else raw
        if kind in ("quantity", "range", "scientific"):
            # Second pass of "3-5\nTOEIC" -> "3-5\nT O E I C": T is a spelled letter, not tesla.
            if re.search(r"(?<![^\W\d_])[A-ZĐ]$", raw) and re.match(r"[ \t]+[A-ZĐ](?:[ \t]|$)", after):
                return raw
            letter_t = re.fullmatch(rf"({_SIGNED})[ \t]*T", raw) if kind == "quantity" else None
            if letter_t and not _TESLA_CUE.search(before[-80:] + " " + after[:40]):
                number = self._num(letter_t[1])
                if number:
                    return number + (" tấn" if _TON_CUE.search(before[-60:]) else " tê")
            return self._quantity(kind, raw)
        if kind == "currency_prefix":
            return read_news("news_currency_prefix", "", raw, self.config, self.units) or raw
        if kind == "vulgar_fraction":
            match = re.match(r"([+−-]?)([0-9]*)([¼½¾⅐⅑⅒⅓⅔⅕⅖⅗⅘⅙⅚⅛⅜⅝⅞])", raw)
            sign, a, glyph = match.groups()
            numerator, denominator = unicodedata.normalize("NFKD", glyph).split("⁄")
            reading = self._int(numerator) + " " + self.config.fraction_word + " " + self._int(denominator)
            if a:
                reading = self._int(a) + " và " + reading
            reading = {"-": "âm ", "−": "âm ", "+": "cộng "}.get(sign, "") + reading
            unit = raw[match.end():].strip()
            if unit:
                spoken_unit = read_unit(unit, self.units, self.config)
                return reading + " " + spoken_unit if spoken_unit else raw
            return reading
        if kind == "power":
            unit_match = self._unit_pattern.search(raw)
            power = raw[:unit_match.start()].strip() if unit_match else raw
            m = re.fullmatch(rf"({_NUM})([⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+)", power)
            exponent = m[2].translate(str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+"))
            a, b = self._num(m[1]), self._num(exponent)
            spoken_unit = read_unit(unit_match.group(), self.units, self.config) if unit_match else ""
            if unit_match and spoken_unit is None:
                return raw
            unit = " " + spoken_unit if spoken_unit else ""
            return a + " mũ " + b + unit if a and b else raw
        if kind in ("arithmetic", "equation", "parenthesized_math"):
            if kind == "parenthesized_math" and not _MATH_CUE.search(before):
                # Editorial parentheses around a range: "(2024-2033)", "(20-30)".
                ranged = re.fullmatch(r"(\(+)[ \t]*([0-9]+)[ \t]*[–-][ \t]*([0-9]+)[ \t]*(\)+)", raw)
                if ranged and len(ranged[1]) == len(ranged[4]):
                    core = ranged[2] + "-" + ranged[3]
                    spoken = (self._int_range(ranged[2], ranged[3], before + ranged[1], "", editorial=True)
                              or self._compound(core, before + ranged[1], ""))
                    if spoken != core:
                        return ranged[1] + spoken + ranged[4]
            if kind == "parenthesized_math":
                wrapped = re.fullmatch(rf"(\(+)[ \t]*({_FULL_DATE})[ \t]*(\)+)", raw)
                if wrapped and len(wrapped[1]) == len(wrapped[3]):
                    core = re.sub(r"[ \t]+", "", wrapped[2])
                    if not _MATH_CUE.search(before):
                        parts = re.split(r"[/.-]", core)
                        if len(parts[0]) == 4 or len(parts[-1]) == 4:
                            reading = self._date(core)
                            return raw if reading == core else wrapped[1] + reading + wrapped[3]
                        return raw
                wrapped_fraction = re.fullmatch(r"(\(+)([0-9]+\s*/\s*[0-9]+)(\)+)", raw)
                if wrapped_fraction and len(wrapped_fraction[1]) == len(wrapped_fraction[3]) and not _MATH_CUE.search(before):
                    return wrapped_fraction[1] + self._read("fraction", wrapped_fraction[2], before, after) + wrapped_fraction[3]
            if re.fullmatch(r"[0-9]+\s*/\s*[0-9]+", raw) and not _MATH_CUE.search(before):
                return self._read("fraction", raw, before, after)
            return read_expression(raw, self.config) or raw
        if kind == "ratio":
            m = re.search(r"[0-9]", raw)
            cue, numbers = raw[:m.start()], raw[m.start():]
            a, b = re.split(r"\s*[:/−–-]\s*", numbers)
            left, right = self._num(a), self._num(b)
            join = " trên " if re.search(r"(?:tỷ|tỉ) lệ|màn[ \t]+hình", cue, re.I) else " "
            return cue + left + join + right if left and right else raw
        if kind == "fraction":
            if _MATH_CUE.search(before):
                return read_expression(raw, self.config) or raw
            a, b = re.split(r"\s*/\s*", raw)
            if len(b) == 4 and 1945 <= int(b) <= 2100 and _DOC_NUMBER_CUE.search(before):
                return self._component(a) + " năm " + self._int(b)  # Nghị định 100/2019
            # Coordinated dates: "ngày 26 và 27/6". Avoid generic từ/đến cues.
            if re.search(rf"\b(?:{_DATE_CUE})\s+[0-9]+(?:\s*(?:,|và|hoặc)\s*)$", before, re.I):
                return self._date(raw.replace(" ", ""))
            if self._slash_is_date(a, b, before, after):
                spoken = self._date(raw.replace(" ", ""))
                if spoken != raw.replace(" ", ""):
                    return spoken
            # A capitalized street name after a multi-part house number is not
            # sufficient on its own; callers can supply the explicit address cue.
            if not b.strip("0"):
                return raw
            return self._int(a) + " " + self.config.fraction_word + " " + self._int(b)
        if kind == "roman":
            return self._roman(raw, before, after)
        if kind == "prefix":
            expansions = {"PGS.TS": "phó giáo sư tiến sĩ", "GS.TS": "giáo sư tiến sĩ", "ThS": "thạc sĩ",
                          "TS": "tiến sĩ", "BS": "bác sĩ", "TP": "thành phố", "Tp": "thành phố", "TX": "thị xã",
                          "TT": "thị trấn", "Q": "quận", "P": "phường", "H": "huyện"}
            override = self.config.abbreviation_overrides.get(raw) or self.config.abbreviation_overrides.get(raw.rstrip("."))
            following = after.lstrip()
            stem = raw.rstrip(".")
            if not override:
                if stem in ("Q", "P", "H") and (not following or not following[0].isdigit()):
                    return raw
                if stem not in ("Q", "P", "H") and (not following or not following[0].isupper()):
                    return raw
            return (override or expansions[stem]) + (" " if after and not after[0].isspace() else "")
        if kind == "standalone_unit":
            if self.config.abbreviation_policy == "common" and raw in vi.SPECIAL_PAIRS:
                return vi.SPECIAL_PAIRS[raw]  # K/g: kính gửi, not kelvin per gram
            if exchange_rate(re.split(r"[ \t]*([/·*])[ \t]*", raw)):
                return raw
            return read_unit(raw, self.units, self.config) or raw
        if kind == "acronym_pair":
            if raw in self.config.abbreviation_overrides:
                return self._abbreviation(raw)
            reading = self._vi_cluster(raw, before, after)
            if reading:
                return self._gloss(raw, reading, before, after)
            if self.config.acronym_mode == "preserve" and not _CODE_GROUP.fullmatch(raw):
                return raw
            amp = _AMP_ACRONYM.fullmatch(raw)
            if amp:
                return self._letters(amp[1]) + " và " + self._letters(amp[2])
            if "&" in raw and re.fullmatch(_AMP_CLUSTER, raw):
                return self._amp_cluster(raw)
            if _CODE_GROUP.fullmatch(raw):
                return self._code_group(raw)
            # A designator has a model number (AN/APX-127, F/A-18); letter-only
            # pairs (ABC/DEF, KM/H) and unit/currency pairs stay intact.
            if (_DESIGNATOR.fullmatch(raw) and re.search(r"[0-9]", raw) and raw.lower() not in self.units
                    and not all(p in self.units for p in re.split(r"[/-]", raw) if p)):
                return self._designator(raw)
            # Unknown pairs and currency exchange pairs remain intact.
            return raw
        if kind in ("compound", "numeric_structure"):
            return self._compound(raw, before, after)
        if kind == "number":
            period = _PERIOD_CUE.search(before)
            if period and re.fullmatch(r"[0-9]{1,2}", raw) and int(raw) and not _PER_PERIOD.search(before):
                word, value = period[1].casefold(), int(raw)
                if word == "thứ" and (raw in ("1", "4") or raw[0] == "0"):
                    return self._ordinal(raw)  # thứ 4 -> thứ tư, cuộc họp thứ 05 -> thứ năm
                if word == "tháng" and value <= 12:
                    return self._month(raw)  # tháng 4 -> tháng tư, tháng 05 -> tháng năm
                if raw[0] == "0" and value <= {"quý": 4, "ngày": 31}.get(word, 0):
                    return self._int(raw)  # quý 01 -> quý một, ngày 05 -> ngày năm
            if re.fullmatch(r"[0-9]{2}", raw) and re.search(r"(?<![^\W\d_])(?:RON|Ron|ron)[ \t]*\Z", before):
                return self._short_number(raw)  # xăng RON 92 -> ron chín hai
            # Leading-zero digit strings are identifiers, independent of length.
            if re.fullmatch(r"0[0-9]+", raw):
                return read_digits(raw)
            return self._num(raw) or raw
        if kind == "word":
            if raw in self.config.abbreviation_overrides:
                return self._abbreviation(raw)
            # A preserved code prefix followed by spoken digits must not become
            # a country/organization name on a subsequent normalization pass.
            news_term = self.config.abbreviation_policy == "extended" and "news" in self.config.enabled_domains and raw in NEWS_ABBREVIATIONS
            # Vietnamese abbreviations by meaning; read before the code-prefix rule below,
            # so "UBND năm 2020" is not spelled like the code prefix of "QH mười lăm".
            reading = self._vi_word(raw, before, after, sentence)
            if reading is not None:
                return self._gloss(raw, reading, before, after)
            if raw.isupper() and raw not in COMMON_ABBREVIATIONS and _in_caps_headline(before, after):
                return raw  # "TIN NÓNG", "VIỆT NAM": Vietnamese words in capitals
            # A single letter is never a code prefix here: "loại C 5" reads "loại C năm"
            # on the first pass, and the second pass must leave "C năm" alone.
            if not news_term and len(raw) > 1 and raw.isupper() and re.match(r"\s+(?:không|một|hai|ba|bốn|năm|sáu|bảy|tám|chín)\b", after):
                return self._code_letters(raw)
            if news_term:
                reading = self._abbreviation(raw)
                for label in ("chỉ số", "tổ chức", "ngân hàng", "hiệp hội", "liên minh", "quỹ"):
                    if reading.casefold().startswith(label + " ") and re.search(r"\b" + label.replace(" ", r"[ \t]+") + r"[ \t]+$", before, re.I):
                        return reading[len(label):].lstrip()
            singular = self._plural_acronym(raw)
            if singular:
                return self._read("word", singular, before, after)
            parts = _camel_parts(raw) if self.config.split_camel_case else [raw]
            if len(parts) > 1 and parts[-1].casefold() in _NUMBER_CUES:
                parts = _camel_parts(raw, code=False)  # getElementById: "Id 25" would read as a code
            # Preserve a gloss after its own expansion: "... (WTO)".
            if len(parts) == 1:
                expansion = self._abbreviation(raw)
                if before.rstrip().endswith("(") and expansion.casefold() in before.casefold():
                    if self.config.acronym_mode == "latin":
                        return latin_letters(raw) if classify_acronym(raw) == "spell" else raw
                    return raw if self.config.acronym_mode == "preserve" else spell_letters(raw)
                return expansion
            return " ".join(self._abbreviation(part) for part in parts)
        if kind == "at":
            return "a còng " if after and not after[0].isspace() else "a còng"
        return raw

    def _day_range(self, raw: str) -> Optional[str]:
        """'ngày 24-25' when the pair cannot be day-month: read as a day range."""
        m = re.search(r"([0-9]{1,2})[ \t]*[–-][ \t]*([0-9]{1,2})$", raw)
        if m and 1 <= int(m[1]) < int(m[2]) <= 31:
            return raw[:m.start()] + self._int(m[1]) + " đến " + self._int(m[2])
        return None

    def _slash_is_date(self, a: str, b: str, before: str, after: str) -> bool:
        day, month = int(a), int(b)
        if not (1 <= month <= 12 and 1 <= day <= 31):
            return False
        if _WEEKDAY_CUE.search(before):
            return True
        if _FRACTION_CUE.search(before) or re.match(r"[ \t]*(?:lần|phần|số)\b", after):
            return False
        if day > month:
            return True
        # list propagation: "25/9, 16/10 và 10/11"
        prev = re.search(rf"({_DATE_LIST_ITEM})[ \t]*(?:,|và|hoặc)[ \t]*$", before)
        nxt = re.match(rf"[ \t]*(?:,|và|hoặc)[ \t]*({_DATE_LIST_ITEM})(?![0-9/])", after)
        for m in (prev, nxt):
            if m:
                x, y = (int(v) for v in re.split(r"[ \t]*/[ \t]*", m[1]))
                if 1 <= y <= 12 and x > y:
                    return True
        return False

    def _quantity(self, kind: str, raw: str) -> str:
        if kind == "quantity" and re.fullmatch(r"(?:1|2|4|5|6|8|10|12|16)K", raw):
            return self._int(raw[:-1]) + " ca"  # display resolution; spaced "300 K" stays kelvin
        # Compact digit/letter pairs also spell unlabelled house addresses.
        # A space or a multi-letter unit disambiguates counted denominators.
        if re.fullmatch(r"[0-9]+[A-Za-zĐđ](?:/[0-9]+[A-Za-zĐđ])+", raw):
            return raw
        match = self._unit_pattern.search(raw)
        unit = re.sub(r"\s+", "", match.group()) if match else ""
        number = raw[:match.start()].strip() if match else raw
        if kind == "range":
            match_range = self._range_pattern.fullmatch(number)
            if match_range is None:
                return raw
            first, left_unit, dash, second = match_range.groups()
            cfg = self.config
            if cfg.number_locale == "auto" and unit.split("/")[0] in VI_FORMAT_CURRENCY:
                cfg = replace(cfg, number_locale="vi")
            left, right = (read_number(v, cfg if unit.split("/")[0] in CURRENCY else quantity_config(v, cfg))
                           for v in (first, second))
            if left_unit and left and right:
                # "20%-30%": both endpoints carry a unit; read it twice, as written.
                left_reading = read_unit(re.sub(r"\s+", "", left_unit), self.units, self.config)
                unit_reading = read_unit(unit, self.units, self.config)
                if left_reading is None or unit_reading is None:
                    return raw
                same = re.sub(r"\s+", "", left_unit) == unit
                ordered = self._ordered(first, second)
                joiner = " đến " if ordered or not same else " " + dash + " "
                return left + " " + left_reading + joiner + right + " " + unit_reading
            spoken = left + " đến " + right if left and right else None
        elif kind == "scientific":
            match_scientific = re.fullmatch(rf"({_SIGNED})[eE]([+−-]?[0-9]+)", number)
            if not match_scientific:
                return raw
            base, exponent = match_scientific.groups()
            left, right = self._num(base), self._num(exponent)
            spoken = left + " nhân mười mũ " + right if left and right else None
        else:
            cfg = self.config
            if cfg.number_locale == "auto" and unit.split("/")[0] in VI_FORMAT_CURRENCY:
                cfg = replace(cfg, number_locale="vi")
            spoken = read_number(number, cfg if unit.split("/")[0] in CURRENCY else quantity_config(number, cfg))
        unit_reading = read_unit(unit, self.units, self.config) if unit else ""
        if not spoken or (unit and unit_reading is None):
            return raw
        return spoken + (" " + unit_reading if unit_reading else "")

    def _number_gloss(self, raw: str) -> Optional[str]:
        """A number followed by number words in brackets.

        "05 (năm) ngày", "15 (mười lăm) ngày": the words repeat the number, so it is read once.
        Other number words stay after the number: "10 (năm)" -> mười (năm).
        """
        match = re.fullmatch(rf"({_NUM})([ \t]*)\([ \t]*({_NUMBER_WORDS})[ \t]*\)", raw)
        if match is None:
            return None
        number = match[1]
        spoken = self._int(number) if number.isdigit() else self._num(number)
        if not spoken or spoken == number:
            return None
        if _number_words(match[3]) == _number_words(spoken):
            return spoken
        return spoken + match[2] + raw[match.end(2):]

    def _ordered(self, first: str, second: str) -> bool:
        values = []
        for value in (first, second):
            parsed = parse_number(value.replace("−", "-"), self.config.number_locale, self.config.ambiguous_number)
            if parsed is None:
                return False
            sign, integer, fraction = parsed
            values.append(float(("-" if sign in ("-", "−") else "") + integer + "." + (fraction or "0")))
        return values[0] < values[1]

    def _address_number(self, raw: str) -> str:
        out = []
        for component in raw.split("/"):
            match = re.fullmatch(r"([0-9]+)([A-Za-zĐđ]?)", component)
            if not match:
                return raw
            letters = spell_letters(match[2]) if self.config.acronym_mode != "preserve" else match[2]
            out.append(self._component(match[1]) + (" " + letters if letters else ""))
        return " xuyệt ".join(out)

    def _component(self, value: str) -> str:
        return read_digits(value) if len(value) > 1 and value.startswith("0") else self._int(value)

    def _compound(self, raw: str, before: str, after: str = "") -> str:
        # Exact caller-provided readings also apply to alphanumeric names.
        # Whole-token matching keeps E4 overrides from changing E40 or E4X.
        if raw in self.config.abbreviation_overrides:
            return self._abbreviation(raw)
        if self.config.abbreviation_policy == "common" and raw in vi.ALWAYS:
            return vi.ALWAYS[raw]  # CK1, CK2
        symbol = _DOC_SYMBOL.fullmatch(raw) if self.config.acronym_mode != "preserve" else None
        # A Roman level is not a document type: RON 95-III, mức 2-II.
        if symbol and len(re.findall(r"[A-ZĐ]", symbol[3])) >= 2 and not re.fullmatch(r"[IVX]+", symbol[3]):
            return self._doc_symbol(symbol)
        # Bare dotted sequences: recognize consistent thousands grouping before
        # versions/IP. Malformed numeric punctuation is preserved whole.
        if re.fullmatch(r"[0-9]+(?:\.[0-9]+){2,}", raw):
            parts = raw.split(".")
            version_cue = re.search(r"(?:phiên bản|version)\s*$", before, re.I)
            if version_cue:
                return " chấm ".join(self._component(p) for p in parts)
            grouped = re.fullmatch(r"[0-9]{1,3}(?:\.[0-9]{3})+", raw)
            if grouped:
                # A padded IPv4 and a grouped quantity share the same spelling.
                if len(parts) == 4 and all(len(p) <= 3 and int(p) <= 255 for p in parts):
                    return raw
                return self._num(raw) or raw
            if any(len(p) > 1 and p.startswith("0") for p in parts):
                return raw
            return " chấm ".join(self._component(p) for p in parts)
        if re.fullmatch(r"[+−-]?[0-9]+(?:[.,][0-9]+)+", raw):
            return self._num(raw) or raw
        # Short uppercase prefix + digits: model/product names require context;
        # a hyphenated identifier is explicit enough on its own.
        years = re.fullmatch(r"(1[89][0-9]{2}|20[0-9]{2}|21[0-9]{2})[–—-]([0-9]{4}|[0-9]{2})", raw)
        if years and not _MATH_CUE.search(before) and not re.match(r"[-–—/.:+]?[0-9A-Za-z]", after):
            left, right = years.groups()
            span = 100
            if len(right) == 2:
                full = int(left[:2] + right)
                right, span = str(full + 100 if full <= int(left) else full), 10
            if int(left) < int(right) <= int(left) + span:
                return self._int(left) + " đến " + self._int(right)
        range_match = re.fullmatch(r"([0-9]+)[–-]([0-9]+)", raw)
        if range_match and not _MATH_CUE.search(before):
            spoken = self._int_range(*range_match.groups(), before, after)
            if spoken:
                return spoken
            if re.search(r"(?:từ|khoảng|tầm|giai đoạn)\s*$", before, re.I):
                return " đến ".join(self._int(v) for v in range_match.groups())
        m = re.fullmatch(r"([A-ZĐ]{1,6})-?([0-9]{1,12})", raw)
        if m and ("-" in raw or re.search(r"(?:mã|chuyến bay|chuyến tàu|tàu|đơn hàng)\s*$", before, re.I)):
            # Preserve letters but never leave digits for another pass to expand.
            news_prefix = self.config.abbreviation_policy == "extended" and "news" in self.config.enabled_domains and m[1] in NEWS_ABBREVIATIONS
            # Spell news acronyms inside explicit codes so later passes cannot
            # reinterpret a code as an organization or an economic indicator.
            if news_prefix or (self.config.acronym_mode == "latin" and len(m[1]) == 1):
                letters = spell_letters(m[1])  # rule L1: F-16 -> ép mười sáu
            elif len(m[1]) == 2 and self.config.acronym_mode == "latin" and m[1] not in self.config.abbreviation_overrides:
                letters = latin_letters(m[1])  # MQ-9: letters of a code, as in TF6000
            else:
                letters = self._code_letters(m[1])
            return letters + " " + (self._code_number(m[2]) if "-" in raw else read_digits(m[2]))
        # A range of grouped numbers: khoảng 14.000–17.000 (feet), 3.000–5.000 đơn vị.
        grouped = re.fullmatch(r"([0-9]{1,3}(?:[.,][0-9]{3})+)[ \t]*[–-][ \t]*([0-9]{1,3}(?:[.,][0-9]{3})+)", raw)
        if grouped and not _MATH_CUE.search(before) and self._ordered(*grouped.groups()):
            left, right = self._num(grouped[1]), self._num(grouped[2])
            if left and right:
                return left + " đến " + right
        pair = self._code_pair(raw)
        if pair:
            return pair
        sulfur = re.fullmatch(r"([0-9]+[.,][0-9]+)S(?:-(I{1,3}|IV|V))?", raw)
        if sulfur and re.search(r"(?i:\b(?:diesel|dầu|DO|FO|mazut))[ \t]+\Z", before):
            # Fuel sulphur grade: dầu DO 0,05S-II -> không phẩy không năm ét hai.
            level = " " + self._int(str(self._roman_value(sulfur[2]))) if sulfur[2] else ""
            return (self._num(sulfur[1]) or sulfur[1]) + " ét" + level
        return self._alnum(raw, before)

    def _code_pair(self, raw: str) -> Optional[str]:
        """Codes joined by a slash, at least one with digits: 5G/6G -> năm gờ, sáu gờ; 4G/LTE -> bốn gờ, L T E.
        Letter-only pairs (USD/VND, KM/H) stay as written."""
        pair = re.fullmatch(r"([0-9]*[A-Z][A-Z0-9]*)/([0-9]*[A-Z][A-Z0-9]*)", raw)
        if not pair or not any(re.search(r"[0-9]", side) for side in pair.groups()):
            return None
        sides = [self._alnum(side) if re.search(r"[0-9]", side) else self._abbreviation(side) for side in pair.groups()]
        if any(re.search(r"[0-9]", spoken) for spoken in sides):
            return None
        return ", ".join(sides)

    def _short_number(self, value: str) -> str:
        """Two digits the short way, as fuel grades are said: 92 -> chín hai, 95 -> chín lăm."""
        if value[0] in "01":
            return self._int(value)
        unit = {"0": "mươi", "1": "mốt", "4": "tư", "5": "lăm"}.get(value[1]) or read_digits(value[1])
        return read_digits(value[0]) + " " + unit

    def _int_range(self, a: str, b: str, before: str, after: str, *, editorial: bool = False) -> Optional[str]:
        """Small integer ranges: "4-5 ngày", "thứ 4-5", "(20-30)". A bare "3-5" stays
        ambiguous (date, score or range); match scores are never ranges."""
        if (not all(len(v) <= 3 and not (len(v) > 1 and v.startswith("0")) for v in (a, b))
                or not 0 < int(a) < int(b) or _SCORE_CONTEXT.search(re.split(r"[.!?\n]", before)[-1])):
            return None
        period = re.search(r"(?i:\b(thứ|tháng|quý))[ \t]*\Z", before)
        if period:
            # Repeat the period word: "thứ tư đến thứ năm", "tháng tư đến tháng năm".
            word = period[1].lower()
            if (word == "tháng" and int(b) > 12) or (word == "quý" and int(b) > 4):
                return None
            speak = {"thứ": self._ordinal, "tháng": self._month, "quý": self._int}[word]
            return speak(a) + " đến " + word + " " + speak(b)
        # A following token ("4-5 ngày", "3-5 5m"), editorial parentheses or a
        # label/approximator before it ("Điều 4-6", "khoảng 4-5") make the pair a range.
        # Any token counts, not only words: digits become words on a second pass.
        if editorial or re.match(r"[ \t]+[^\s.,;:!?)\]}”\"'…–—-]", after) or _framed(before):
            return self._int(a) + " đến " + self._int(b)
        return None

    def _cue_prefix(self, prefix: str) -> str:
        """A kept cue ('IP', 'IPv4', 'OTP') must read the same on a second pass."""
        return re.sub(r"[A-Za-zĐđ0-9]+", lambda m: self._alnum(m.group()) if re.search(r"[0-9]", m.group())
                      else self._abbreviation(m.group()), prefix)

    def _code_letters(self, token: str) -> str:
        """Letters inside a code: overrides and pronunciations apply, expansions do not."""
        override = self.config.abbreviation_overrides.get(token)
        if override:
            return override
        if self.config.abbreviation_policy == "common" and token in SAY_ABBREVIATIONS:
            return COMMON_ABBREVIATIONS[token]
        if self.config.abbreviation_policy == "common" and self.config.acronym_mode == "spell" and token in LEGACY_SAY:
            return LEGACY_SAY[token]
        if self.config.acronym_mode == "latin":
            # Rule L2: a single letter stays as written, longer runs follow classify_acronym.
            # A kept token must read as itself on a second pass ("2PN" must not
            # become "hai PN" -> "hai phụ nữ"), otherwise spell it.
            keep = len(token) == 1 or classify_acronym(token) == "keep"
            return token if keep and self._abbreviation(token) == token else latin_letters(token)
        if self.config.acronym_mode == "spell" and (len(token) == 1 or is_spell_candidate(token)):
            return spell_letters(token)
        # Idempotence: a verbatim token must read as itself on a second pass.
        if len(token) > 1 and self._abbreviation(token) != token:
            return spell_letters(token)
        return token

    def _alnum(self, raw: str, before: str = "") -> str:
        """Letters+digits identifiers: G20, V3, 5G, RAIBO2, CVE-2026-65660, GPT-5.5-Cyber, TEI-TF6000.

        In a code a two-letter run is spelled (TF6000 -> T F sáu nghìn), whole thousands are a
        cardinal (6000 -> sáu nghìn; 4090, 9300 are read digit by digit) and a Roman level after
        digits is a number (RON95-III -> ron chín lăm ba). Fuel grades are said the short way:
        E5RON92 -> e năm ron chín hai, xăng A95 -> xăng a chín lăm.
        """
        # Uppercase evidence required: 20k, 3tsp, 60fps, 10x20cm stay with unit/domain rules.
        if (not re.fullmatch(r"[A-Za-zĐđ0-9]+(?:(?:-|(?<=[0-9])\.(?=[0-9]))[A-Za-zĐđ0-9]+)*", raw)
                or not re.search(r"[0-9]", raw) or not re.search(r"[A-ZĐ]", raw)
                or re.search(r"[0-9][xX×][0-9]", raw)):
            return raw
        if re.search(r"[0-9]\.[0-9]+\.[0-9]", raw):
            return raw  # multi-dot versions stay with the version readers
        say = self.config.abbreviation_policy == "common"
        # Words said as words (RON) do not count as letters: E5RON keeps "e" as a Vietnamese letter.
        caps = [t for t in re.findall(r"[A-Za-zĐđ]+", raw) if t.isupper() and not (say and t in SAY_ABBREVIATIONS)]
        vietnamese_letters = self.config.acronym_mode == "latin" and all(len(t) == 1 for t in caps)
        fuel = re.fullmatch(r"[AE][89][0-9]", raw) and re.search(r"(?i:\bxăng)[ \t]+\Z", before)
        out, previous = [], "RON" if re.search(r"(?<![^\W\d_])RON[ \t]*\Z", before) else ""
        for part in raw.split("-"):
            if re.fullmatch(r"I{1,3}|IV|V", part) and previous[:1].isdigit():
                out.append(self._int(str(self._roman_value(part))))  # RON95-III: level three
                previous = part
                continue
            for token in re.findall(r"[0-9]+(?:\.[0-9]+)?|[A-Za-zĐđ]+", part):
                if token[0].isdigit():
                    if "." in token:
                        out.append(" chấm ".join(self._component(p) for p in token.split(".")))
                    elif len(token) == 2 and (previous == "RON" or fuel):
                        out.append(self._short_number(token))
                    elif ((len(token) <= 3 and not (len(token) > 1 and token[0] == "0"))
                          or re.fullmatch(r"[1-9][0-9]{0,2}000", token)):
                        out.append(self._int(token))
                    else:
                        out.append(read_digits(token))
                elif token.isupper():
                    if say and token in SAY_ABBREVIATIONS and token not in self.config.abbreviation_overrides:
                        out.append(COMMON_ABBREVIATIONS[token])
                    elif vietnamese_letters:
                        out.append(spell_letters(token))
                    elif (len(token) == 2 and self.config.acronym_mode == "latin"
                          and token not in self.config.abbreviation_overrides):
                        out.append(latin_letters(token))  # TF6000: letters of a code, not an acronym
                    else:
                        out.append(self._code_letters(token))
                else:
                    out.append(token)
                previous = token
        spoken = " ".join(out)
        return spoken if re.search(r"[A-Z]{2,}[0-9]|[0-9]", spoken) is None else raw

    def _link(self, raw: str) -> str:
        # Read every meaningful symbol; do not discard scheme/query/plus tags.
        punctuation = raw[len(raw.rstrip(".,;!?")):]
        core = raw[:len(raw) - len(punctuation)] if punctuation else raw
        symbols = {"@": "a còng", ".": "chấm", "/": "xuyệt", ":": "hai chấm",
                   "?": "dấu hỏi", "=": "bằng", "&": "và", "%": "phần trăm",
                   "-": "gạch ngang", "_": "gạch dưới", "+": "cộng", "#": "thăng"}
        out = []
        for part in re.findall(r"[0-9]+|[^\W\d_]+|[^\w\s]|_", core):
            if part.isascii() and part.isdigit():
                out.append(read_digits(part))
            else:
                out.append(symbols.get(part, part.lower()))
        return " ".join(out) + punctuation


_DEFAULT_NORMALIZER = Normalizer()


def normalize_vi_text(text: str, config: Optional[NormalizerConfig] = None) -> str:
    """Normalize text with defaults or explicit reading policies."""
    return (_DEFAULT_NORMALIZER if config is None else Normalizer(config)).normalize(text)
