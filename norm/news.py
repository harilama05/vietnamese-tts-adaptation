"""News grammar and explicit terminology; no document-topic or factual inference."""

from dataclasses import replace
from decimal import Decimal
import re

from .lexicon import UNITS, spell_letters
from .numbers import parse_number, quantity_config, read_integer, read_number
from .units import CURRENCY, VI_CURRENCY, currency_identity, read_unit, unit_pattern

# Meaning is selected by the enabled news domain, never by capitalization alone
# outside it. Caller abbreviation overrides retain priority.
ABBREVIATIONS = {
    "GDP": "tổng sản phẩm trong nước", "CPI": "chỉ số giá tiêu dùng",
    "PPI": "chỉ số giá sản xuất", "FDI": "đầu tư trực tiếp nước ngoài",
    "ODA": "hỗ trợ phát triển chính thức", "FTA": "hiệp định thương mại tự do",
    "IMF": "Quỹ Tiền tệ Quốc tế", "WHO": "Tổ chức Y tế Thế giới",
    "EU": "Liên minh châu Âu", "ASEAN": "Hiệp hội các quốc gia Đông Nam Á",
    "NATO": "Tổ chức Hiệp ước Bắc Đại Tây Dương",
    "OPEC": "Tổ chức các nước xuất khẩu dầu mỏ",
    "IAEA": "Cơ quan Năng lượng Nguyên tử Quốc tế",
    "UNICEF": "Quỹ Nhi đồng Liên Hợp Quốc",
    "UNESCO": "Tổ chức Giáo dục, Khoa học và Văn hóa Liên Hợp Quốc",
    "ECB": "Ngân hàng Trung ương châu Âu", "WTI": "vê kép tê i",
}
COUNT_UNITS = {
    word: word for word in (
        "người", "hộ", "ca", "liều", "phiếu", "lượt", "chuyến", "điểm",
        "thùng", "bao", "kiện", "chai", "hộp", "gói", "vé", "chiếc",
        "bệnh nhân", "cử tri", "hộ dân", "doanh nghiệp", "cổ phiếu", "trái phiếu", "binh sĩ",
    )
}
_H = r"[ \t]*"
_N = r"[+−-]?(?:[0-9]{1,3}(?: [0-9]{3})+(?:[.,]+[0-9]+)?|[0-9]+(?:[.,]+[0-9]+)*|\.[0-9]+(?:[.,]+[0-9]+)*)"
# "tỷ số"/"tỉ số" (score, ratio) is a word of its own, not the scale "tỷ".
_SCALE = r"(?:nghìn|ngàn|triệu|tỷ(?![ \t]+số\b)|tỉ(?![ \t]+số\b))"
_CURRENCY = "(?:" + "|".join(re.escape(k) for k in sorted(CURRENCY, key=len, reverse=True)) + ")"
_UNIT = unit_pattern(tuple({**UNITS, **COUNT_UNITS}))
_COUNT = "(?:" + "|".join(re.escape(k).replace(r"\ ", r"[ \t]+") for k in sorted(COUNT_UNITS, key=len, reverse=True)) + ")"
_VALUE = rf"{_N}(?:[ \t]+{_SCALE})?"
_COMMA_GROUPS = r"[1-9][0-9]{0,2}(?:,[0-9]{3})+"
_COMMA_THOUSANDS = rf"{_COMMA_GROUPS}(?:[ \t]*[–-][ \t]*{_COMMA_GROUPS})?"
_AMOUNT = rf"{_VALUE}(?:{_H}[–-]{_H}{_VALUE})?"
_SCALED = rf"(?:{_N}[ \t]+{_SCALE}(?:{_H}[–-]{_H}{_VALUE})?|{_N}{_H}[–-]{_H}{_N}[ \t]+{_SCALE})"
# Unknown denominator atoms are consumed too, then rejected as a whole.
_RATE_ATOM = r"(?:[^\W\d_]|[°%‰$€£Ω])+(?:[ \t]*\^[ \t]*[+−-]?[0-9]+|[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+|[0-9]+)?"
_RATE = rf"(?:{_H}/{_H}(?:[0-9]+{_H})?{_RATE_ATOM}){{0,3}}"
_PREFIX_AMOUNT = rf"{_VALUE}(?:{_H}[–-]{_H}(?:{_CURRENCY}{_H})?{_VALUE})?"
CURRENCY_PREFIX_PATTERN = rf"{_CURRENCY}{_H}{_PREFIX_AMOUNT}{_RATE}"

# (name, explicit cue or empty, body). Every body is validated by its reader.
SPECS = (
    ("news_scaled_quantity", "", rf"{_SCALED}[ \t]+{_UNIT}"),
    ("news_currency_prefix", "", CURRENCY_PREFIX_PATTERN),
    ("news_basis_points", r"lãi suất(?: (?:tăng|giảm|hạ|nâng|đổi|tăng thêm|giảm thêm))?", rf"{_AMOUNT}[ \t]*(?:bps|bp)"),
    ("news_percentage_points", "", rf"{_AMOUNT}[ \t]+điểm[ \t]*%"),
    ("news_count_range", "", rf"{_N}{_H}[–-]{_H}{_N}[ \t]+{_COUNT}"),
    ("news_count_quantity", "", rf"{_N}[ \t]+{_COUNT}"),
    ("news_month_range", r"tháng", r"[0-9]+[ \t]*[–-][ \t]*[0-9]+[ \t]*/[ \t]*[0-9]+"),
    ("news_quarter_range", r"quý", r"(?:[IVXLCDM]+|[0-9]+)[ \t]*[–-][ \t]*(?:[IVXLCDM]+|[0-9]+)[ \t]*/[ \t]*[0-9]+"),
    ("news_year_range", r"nhiệm kỳ|giai đoạn|niên độ", r"[0-9]+[ \t]*[–-][ \t]*[0-9]+"),
    ("news_wind_range", r"gió cấp|giật cấp|cấp gió", r"[0-9]+[ \t]*[–-][ \t]*[0-9]+"),
    ("news_group", r"nhóm nước|nhóm|các nước|khối|hội nghị thượng đỉnh|hội nghị", r"(?:COP|G|E)[0-9]+"),
    ("news_particle", "", r"PM[0-9]+(?:[.,][0-9]+)*"),
    ("news_pathogen", "", r"(?:COVID-[0-9]+|H[0-9]+N[0-9]+)"),
    ("news_stock_index", "", r"(?:(?:VN|HNX|UPCoM)-Index|(?:VN|HNX)(?:30|100))"),
)
_AMOUNT_RE = re.compile(rf"({_N})(?:[ \t]+({_SCALE}))?(?:{_H}[–-]{_H}({_N})(?:[ \t]+({_SCALE}))?)?")
_SCALES = {"nghìn": 3, "ngàn": 3, "triệu": 6, "tỷ": 9, "tỉ": 9, "": 0}


def _value(value, scale, config):
    if len(value) > 32:
        return None
    parsed = parse_number(value, config.number_locale, config.ambiguous_number)
    if parsed is None:
        return None
    sign, integer, fraction = parsed
    decimal = Decimal(("-" if sign in ("-", "−") else "") + integer + ("." + fraction if fraction else ""))
    s, digits, exponent = decimal.as_tuple()
    return Decimal((s, digits, exponent + _SCALES[scale or ""]))


def _amount(raw, config, *, quantity=False):
    match = _AMOUNT_RE.fullmatch(raw.strip())
    if match is None:
        return None
    left, left_scale, right, right_scale = match.groups()
    if right:
        left_scale = left_scale or right_scale
        # A trailing scale is not inferred from the first endpoint: 1 tỷ–2
        # does not unambiguously specify the magnitude of the second value.
        if left_scale and not right_scale:
            return None
    left_config = quantity_config(left, config) if quantity else config
    right_config = quantity_config(right, config) if quantity and right else config
    a = _value(left, left_scale, left_config)
    b = _value(right, right_scale, right_config) if right else a
    if a is None or b is None or a > b:
        return None
    def scale_word(scale):
        return config.thousand if scale in ("nghìn", "ngàn") else "tỷ" if scale in ("tỷ", "tỉ") else scale or ""
    first = read_number(left, left_config)
    ls, rs = scale_word(left_scale), scale_word(right_scale)
    if not right:
        return first + (" " + ls if ls else "")
    second = read_number(right, right_config)
    if ls == rs:
        return first + " đến " + second + (" " + rs if rs else "")
    return first + (" " + ls if ls else "") + " đến " + second + (" " + rs if rs else "")


def _quantity(amount, unit, config, units):
    table = {**{re.sub(r"\s+", "", k): v for k, v in COUNT_UNITS.items()}, **units}
    spoken_unit = read_unit(unit, table, config)
    if spoken_unit is None:
        return None
    if config.number_locale == "auto" and unit.split("/")[0].strip() in VI_CURRENCY:
        config = replace(config, number_locale="vi")
    elif (config.number_locale == "auto" and re.sub(r"\s+", " ", unit.strip()) in COUNT_UNITS
          and re.fullmatch(_COMMA_THOUSANDS, amount.strip())):
        # A count has no three-digit fraction, so the commas group thousands: 1,850 điểm -> 1850.
        config = replace(config, number_locale="en")
    spoken = _amount(amount, config, quantity=unit.split("/")[0].strip() not in CURRENCY)
    return spoken + " " + spoken_unit if spoken else None


def read_news(name, cue, body, config, units):
    if name in ("news_scaled_quantity", "news_count_range", "news_count_quantity"):
        suffix = re.search(rf"({_UNIT if name == 'news_scaled_quantity' else _COUNT})$", body)
        if suffix is None:
            return None
        result = _quantity(body[:suffix.start()], suffix.group(), config, units)
        return cue + result if result else None
    if name == "news_currency_prefix":
        match = re.fullmatch(rf"({_CURRENCY}){_H}({_PREFIX_AMOUNT})({_RATE})", body)
        if match is None:
            return None
        amount = match[2]
        repeated = re.fullmatch(rf"({_VALUE}){_H}[–-]{_H}({_CURRENCY}){_H}({_VALUE})", amount)
        if repeated:
            if currency_identity(match[1]) != currency_identity(repeated[2]):
                return None
            amount = repeated[1] + "–" + repeated[3]
        return _quantity(amount, match[1] + match[3], config, units)
    if name in ("news_basis_points", "news_percentage_points"):
        value = re.sub(r"[ \t]*(?:bps|bp|điểm[ \t]*%)$", "", body)
        spoken = _amount(value, config)
        suffix = " điểm cơ bản" if name == "news_basis_points" else " điểm phần trăm"
        return cue + spoken + suffix if spoken else None
    if name in ("news_month_range", "news_quarter_range"):
        left, right, year = re.split(r"[ \t]*[–/-][ \t]*", body)
        if not re.fullmatch(r"[1-9][0-9]{3}", year):
            return None
        roman = {"I": 1, "II": 2, "III": 3, "IV": 4}
        def ordinal(token):
            return int(token) if re.fullmatch(r"[0-9]{1,2}", token) else roman.get(token, 0)
        a, b = ordinal(left), ordinal(right)
        if not 1 <= a <= b <= (12 if name == "news_month_range" else 4):
            return None
        def speak(value):
            return "tư" if value == 4 and name == "news_month_range" else read_integer(str(value), config)
        # Repeat the period word: "quý một đến quý hai", "tháng sáu đến tháng bảy".
        period = "quý " if name == "news_quarter_range" else "tháng "
        return cue + speak(a) + " đến " + period + speak(b) + " năm " + read_integer(year, config)
    if name in ("news_year_range", "news_wind_range"):
        left, right = re.split(r"[ \t]*[–-][ \t]*", body)
        pattern = r"[1-9][0-9]{3}" if name == "news_year_range" else r"[0-9]{1,2}"
        if not all(re.fullmatch(pattern, value) for value in (left, right)) or int(left) > int(right):
            return None
        return cue + read_integer(left, config) + " đến " + read_integer(right, config)
    if name == "news_group":
        match = re.fullmatch(r"(COP|G|E)([0-9]{1,3})", body)
        if match is None:
            return None
        prefix, number = match.groups()
        if prefix != "COP" and body not in ("G7", "G8", "G20", "E3", "E4"):
            return None
        if number.startswith("0"):
            return None
        reading = config.abbreviation_overrides.get(body)
        return cue + (reading or spell_letters(prefix) + " " + read_integer(number, config))
    if name == "news_particle":
        if body not in ("PM1", "PM2.5", "PM10"):
            return None
        return config.abbreviation_overrides.get(body) or "pê mờ " + " chấm ".join(read_integer(p, config) for p in body[2:].split("."))
    if name == "news_pathogen":
        if body.startswith("COVID-"):
            if body != "COVID-19":
                return None
            return config.abbreviation_overrides.get(body) or "cô vít mười chín"
        match = re.fullmatch(r"H([1-9][0-9]?)N([1-9][0-9]?)", body)
        if match is None:
            return None
        return config.abbreviation_overrides.get(body) or "hắt " + read_integer(match[1], config) + " nờ " + read_integer(match[2], config)
    if name == "news_stock_index":
        if body in config.abbreviation_overrides:
            return config.abbreviation_overrides[body]
        if body.endswith("-Index"):
            prefix = {"VN": "vê nờ", "HNX": "hắt nờ ích", "UPCoM": "úp com"}[body[:-6]]
            return prefix + " in đếch"
        match = re.fullmatch(r"(VN|HNX)(30|100)", body)
        return spell_letters(match[1]) + " " + read_integer(match[2], config) if match else None
    return None
