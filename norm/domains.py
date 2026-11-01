"""Context-bound domain rules; no guessing a document's topic or units."""

from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
import re
import unicodedata

from .numbers import parse_number, read_digits, read_integer, read_number
from .lexicon import spell_letters
from .units import read_unit
from .news import SPECS as NEWS_SPECS, read_news

_NUMBER = r"[0-9]+(?:[.,]+[0-9]+)*"
_SEP = r"[ \t]*:?[ \t]*"
_END = r"(?!\w|[ \t]*[/^·*⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]|[.,:+–-][0-9])"
_CURRENCY = r"(?i:đồng|VND|VNĐ|USD|EUR|GBP|JPY|CNY|KRW|đ|₫|\$|€|£)"
_PRICE_CUE = r"giá bán|giá thuê|đơn giá|học phí|tiền thuê|giá|phí"
_DAY = r"(?:T[0-9]+|CN)"
_DAYS = rf"{_DAY}(?:[ \t]*(?:[-–,/]+|và)[ \t]*{_DAY})*"
_RATE = r"(?:[ \t]*/[ \t]*[\w²³/]+)?"


@dataclass(frozen=True)
class DomainRule:
    name: str
    domain: str
    cue: str
    body: str

    @property
    def prefix(self):
        if not self.cue:
            return r"(?<![\w./–+-])"
        cue = self.cue.replace(" ", r"[ \t]+")
        separator = r"(?:[ \t]+|[ \t]*:[ \t]*)" if self.name == "model_code" or self.name.startswith("news_") else _SEP
        return rf"(?i:\b(?:{cue})){separator}"

    @property
    def pattern(self):
        return self.prefix + self.body + _END


RULES = (
    DomainRule("price_range", "commerce", _PRICE_CUE,
               rf"{_NUMBER}[ \t]*(?i:tr|k)?[ \t]*[-–][ \t]*{_NUMBER}[ \t]*(?i:tr|k)(?:[ \t]*{_CURRENCY})?{_RATE}"),
    DomainRule("mixed_price", "commerce", _PRICE_CUE,
               rf"{_NUMBER}[ \t]*(?i:tr)[ \t]*{_NUMBER}[ \t]*(?i:k)(?:[ \t]*{_CURRENCY})?{_RATE}"),
    DomainRule("school_days", "education", r"lịch học|học vào",
               _DAYS),
    DomainRule("service_days", "transport", r"lịch chạy|lịch khởi hành|mở cửa",
               _DAYS),
    DomainRule("model_code", "technology", r"SKU|mã model|mã thiết bị|mã linh kiện",
               r"(?=[A-Za-z0-9._/+-]*[0-9])[A-Za-z0-9]+(?:[._/+-]+[A-Za-z0-9]+)*"),
    DomainRule("land_dimensions", "housing", r"mặt tiền|lô đất|khu đất",
               rf"{_NUMBER}(?:[ \t]*[x×][ \t]*{_NUMBER})+[ \t]*[A-Za-z²³0-9]+"),
    DomainRule("section_range", "administration", r"tiểu mục|mục|khoản|điều",
               r"[0-9]+(?:\.+[0-9]+)+[ \t]*[-–][ \t]*[0-9]+(?:\.+[0-9]+)+"),
    DomainRule("recipe_range", "lifestyle", r"thêm|đong|trộn|công thức",
               rf"{_NUMBER}[ \t]*[-–][ \t]*{_NUMBER}[ \t]*(?:tbsp|tsp|cup)"),
    DomainRule("short_price", "commerce", r"giá bán|giá thuê|đơn giá|học phí|tiền thuê|giá|phí",
               rf"{_NUMBER}[ \t]*(?i:tr|k)(?:[ \t]*{_CURRENCY})?{_RATE}"),
    DomainRule("school_year", "education", r"năm học|niên khóa",
               r"[0-9]+(?:[ \t]*[-–/][ \t]*[0-9]+)+"),
    DomainRule("class_label", "education", r"lớp",
               r"[0-9]+[A-Za-z]+[0-9]*"),
    DomainRule("grade", "education", r"điểm số|điểm",
               rf"{_NUMBER}[ \t]*/[ \t]*{_NUMBER}"),
    # Route numbers never start with 0: "ĐT: 0912 345 678" is a phone number.
    DomainRule("road", "transport", r"QL|ĐT",
               r"\.?[ \t]*[1-9][0-9]*[A-Z]*"),
    DomainRule("chainage", "transport", r"lý trình",
               r"[Kk][Mm][ \t]*[0-9]+[ \t]*\+[ \t]*[0-9]+"),
    DomainRule("trip_code", "transport", r"chuyến bay|chuyến tàu|tàu|tuyến xe buýt",
               r"[A-Z]{0,4}[ \t]*[0-9]+(?:[A-Z0-9._/-]*)"),
    DomainRule("resolution", "technology", r"độ phân giải",
               r"[0-9]+(?:[ \t]*[x×][ \t]*[0-9]+)+(?:[ \t]*(?:px|pixel))?"),
    DomainRule("frame_rate", "technology", r"tốc độ khung hình|video|quay",
               rf"{_NUMBER}[ \t]*fps"),
    DomainRule("period_score", "sports", r"tỷ số hiệp|tỉ số hiệp|tỷ số set|tỉ số set",
               r"[0-9]+[ \t]*:[ \t]*[0-9]+[ \t]*[-–:][ \t]*[0-9]+"),
    DomainRule("knockout", "sports", r"vòng",
               r"[0-9]+[ \t]*/[ \t]*[0-9]+"),
    DomainRule("rooms", "housing", r"căn hộ|thiết kế|bố trí",
               r"[0-9]+[A-Za-z]+(?:(?:[ \t]*\+[ \t]*|[ \t]+)[0-9]+[A-Za-z]+)*"),
    DomainRule("section", "administration", r"tiểu mục|mục|khoản|điều",
               r"[0-9]+(?:\.+[0-9]+)+"),
    DomainRule("recipe", "lifestyle", r"thêm|đong|trộn|công thức",
               rf"(?:[0-9]+[ \t]+[0-9]+[ \t]*/[ \t]*[0-9]+|{_NUMBER}(?:[ \t]*/[ \t]*[0-9]+)?|[0-9]*[¼½¾⅓⅔⅛⅜⅝⅞])[ \t]*(?:tbsp|tsp|cup)"),
) + tuple(DomainRule(name, "news", cue, body) for name, cue, body in NEWS_SPECS)
_RULES = {"domain_" + rule.name: rule for rule in RULES}
_PARSERS = {name: re.compile("(" + rule.prefix + ")(" + rule.body + ")" + _END)
            for name, rule in _RULES.items()}


@lru_cache(maxsize=64)
def domain_scanner(enabled):
    shapes = [(name, rule.pattern) for name, rule in _RULES.items() if rule.domain in enabled]
    return re.compile("|".join(f"(?P<{name}>{pattern})" for name, pattern in shapes)) if shapes else None


def _small_integer(value, config, *, maximum=999999, digits=False):
    if not re.fullmatch(r"[0-9]{1,6}", value) or int(value) > maximum:
        return None
    return read_digits(value) if digits or (len(value) > 1 and value[0] == "0") else read_integer(value, config)


def _decimal(value, config):
    parsed = parse_number(value, config.number_locale, config.ambiguous_number)
    if parsed is None or len(value) > 32:
        return None
    sign, integer, fraction = parsed
    return Decimal(("-" if sign in ("-", "−") else "") + integer + ("." + fraction if fraction else ""))


def read_domain(kind, raw, config, units):
    """Return (spoken, reason). All domain readers consume a whole candidate."""
    rule = _RULES[kind]
    if len(raw) > config.max_expression_chars:
        return raw, "resource_limit"
    match = _PARSERS[kind].fullmatch(raw)
    if match is None:
        return raw, "invalid_domain_syntax"
    cue, body = match.groups()
    result = _render(rule.name, cue, body, config, units)
    if result is None:
        return raw, "invalid_or_ambiguous_" + rule.name
    return result, "context_" + rule.domain


def _render(name, cue, body, config, units):
    if name.startswith("news_"):
        return read_news(name, cue, body, config, units)
    integer = lambda value, **kw: _small_integer(value, config, **kw)
    if name in ("short_price", "price_range", "mixed_price"):
        return _price(name, cue, body, config, units)
    if name in ("school_days", "service_days"):
        tokens = re.findall(r"T[0-9]+|CN|[-–,/]+|và", body)
        if len(tokens) > 63 or len(tokens) % 2 == 0:
            return None
        out = []
        for i, token in enumerate(tokens):
            if i % 2:
                join = {"-": " đến ", "–": " đến ", ",": ", ", "/": ", ", "và": " và "}.get(token)
                if join is None:
                    return None
                out.append(join)
            elif token == "CN":
                out.append("chủ nhật")
            elif token in ("T2", "T3", "T4", "T5", "T6", "T7"):
                out.append("thứ " + ("tư" if token == "T4" else integer(token[1:])))
            else:
                return None
        return cue + "".join(out)
    if name == "model_code":
        if not re.fullmatch(r"[A-Za-z0-9]+(?:[._/-][A-Za-z0-9]+)*", body):
            return None
        words = []
        for token in re.findall(r"[A-Za-z]+|[0-9]+|[._/-]", body):
            words.append(read_digits(token) if token.isdigit() else spell_letters(token) if token.isalpha()
                         else {".": "chấm", "_": "gạch dưới", "/": "xuyệt", "-": "gạch ngang"}[token])
        prefix = "mã hàng " if re.sub(r"[ \t:]", "", cue).upper() == "SKU" else cue
        return prefix + " ".join(words)
    if name == "land_dimensions":
        match = re.fullmatch(rf"({_NUMBER})[ \t]*[x×][ \t]*({_NUMBER})[ \t]*(m|cm|mm)", body)
        if match is None:
            return None
        a, b = (_decimal(value, config) for value in match.groups()[:2])
        if a is None or b is None or a <= 0 or b <= 0:
            return None
        return cue + read_number(match[1], config) + " nhân " + read_number(match[2], config) + " " + read_unit(match[3], units, config)
    if name == "section_range":
        left, right = re.split(r"[ \t]*[-–][ \t]*", body)
        a, b = (_render("section", "", value, config, units) for value in (left, right))
        return cue + a + " đến " + b if a and b else None
    if name == "recipe_range":
        match = re.fullmatch(rf"({_NUMBER})[ \t]*[-–][ \t]*({_NUMBER})[ \t]*(tbsp|tsp|cup)", body)
        a, b = (_decimal(value, config) for value in match.groups()[:2])
        if a is None or b is None or not 0 <= a <= b:
            return None
        return cue + read_number(match[1], config) + " đến " + read_number(match[2], config) + " " + {"tbsp": "thìa canh", "tsp": "thìa cà phê", "cup": "cốc đong"}[match[3]]
    if name == "school_year":
        parts = re.split(r"[ \t]*[-–/][ \t]*", body)
        if len(parts) != 2:
            return None
        left, right = parts
        if re.fullmatch(r"[1-9][0-9]{3}", left) and re.fullmatch(r"[0-9]{2}", right):
            full = int(left[:2] + right)
            right = str(full + 100 if full <= int(left) else full)
        if not (re.fullmatch(r"[1-9][0-9]{3}", left) and re.fullmatch(r"[1-9][0-9]{3}", right)):
            return None
        cohort = re.sub(r"[ \t]+", " ", cue.casefold()).startswith("niên khóa")
        if (cohort and int(right) <= int(left)) or (not cohort and int(right) != int(left) + 1):
            return None
        return cue + integer(left) + " đến " + integer(right)
    if name == "class_label":
        match = re.fullmatch(r"([0-9]{1,2})([A-Za-z])([0-9]{0,2})", body)
        if match is None or not 1 <= int(match[1]) <= 12:
            return None
        suffix = " " + integer(match[3]) if match[3] else ""
        return cue + integer(match[1]) + " " + spell_letters(match[2]) + suffix
    if name == "grade":
        left, right = re.split(r"[ \t]*/[ \t]*", body)
        a, b = _decimal(left, config), _decimal(right, config)
        if a is None or b is None or not 0 <= a <= b or b <= 0:
            return None
        return cue + read_number(left, config) + " trên " + read_number(right, config)
    if name == "road":
        match = re.fullmatch(r"\.?[ \t]*([0-9]{1,4})([A-Z]?)", body)
        # Route markers are uppercase identifiers, even though ordinary cues ignore case.
        marker = re.sub(r"[ \t:]", "", cue)
        if match is None or marker not in ("QL", "ĐT"):
            return None
        return ("quốc lộ " if marker == "QL" else "đường tỉnh ") + integer(match[1]) + (" " + spell_letters(match[2]) if match[2] else "")
    if name == "chainage":
        match = re.fullmatch(r"[Kk][Mm][ \t]*([0-9]{1,6})[ \t]*\+[ \t]*([0-9]{3})", body)
        if match is None:
            return None
        return cue + "ki lô mét " + read_integer(match[1], config) + " cộng " + read_integer(match[2], config)
    if name == "trip_code":
        match = re.fullmatch(r"([A-Z]{0,3})[ \t]*([0-9]{1,6})", body)
        if match is None:
            return None
        letters = spell_letters(match[1]) + " " if match[1] else ""
        return cue + letters + read_digits(match[2])
    if name == "resolution":
        suffix = re.search(r"[ \t]*(px|pixel)$", body)
        values = re.split(r"[ \t]*[x×][ \t]*", body[:suffix.start()] if suffix else body)
        if len(values) != 2 or any(not re.fullmatch(r"[1-9][0-9]{0,5}", value) for value in values):
            return None
        return cue + " nhân ".join(integer(value) for value in values) + (" điểm ảnh" if suffix else "")
    if name == "frame_rate":
        value = body[:-3].strip()
        spoken = read_number(value, config)
        return cue + spoken + " khung hình trên giây" if spoken else None
    if name == "period_score":
        values = re.fullmatch(r"([0-9]{1,2})[ \t]*:[ \t]*([0-9]{1,3})[ \t]*[-–:][ \t]*([0-9]{1,3})", body)
        if values is None or int(values[1]) == 0:
            return None
        return cue + integer(values[1]) + ": " + integer(values[2]) + " " + integer(values[3])
    if name == "knockout":
        a, b = re.split(r"[ \t]*/[ \t]*", body)
        if a != "1" or b not in ("2", "4", "8", "16", "32", "64"):
            return None
        return cue + "một phần " + integer(b)
    if name == "rooms":
        parts = re.split(r"[ \t]*\+[ \t]*|[ \t]+", body.upper())
        readings, seen = [], set()
        if len(parts) > 3:
            return None
        for part in parts:
            match = re.fullmatch(r"([0-9]{1,2})(PN|WC|PK)", part)
            if match is None or match[2] in seen:
                return None
            seen.add(match[2])
            readings.append(integer(match[1]) + " " + {"PN": "phòng ngủ", "WC": "nhà vệ sinh", "PK": "phòng khách"}[match[2]])
        return cue + " và ".join(readings)
    if name == "section":
        parts = body.split(".")
        if not 2 <= len(parts) <= 8 or any(not re.fullmatch(r"[0-9]{1,4}", part) for part in parts):
            return None
        return cue + " chấm ".join(integer(part) for part in parts)
    if name == "recipe":
        match = re.fullmatch(r"(.*?)[ \t]*(tbsp|tsp|cup)", body)
        value, unit = match.groups()
        mixed = re.fullmatch(r"([0-9]+)[ \t]+([0-9]+)[ \t]*/[ \t]*([0-9]+)", value)
        if mixed:
            parts = [integer(part) for part in mixed.groups()]
            if any(part is None for part in parts) or not 0 < int(mixed[2]) < int(mixed[3]):
                return None
            spoken = parts[0] + " và " + parts[1] + " " + config.fraction_word + " " + parts[2]
        elif "/" in value:
            a, b = re.split(r"[ \t]*/[ \t]*", value)
            left, right = integer(a), integer(b)
            if left is None or right is None or not b.strip("0"):
                return None
            spoken = left + " " + config.fraction_word + " " + right
        elif value[-1:] in "¼½¾⅓⅔⅛⅜⅝⅞":
            a, b = unicodedata.normalize("NFKD", value[-1]).split("⁄")
            spoken = integer(a) + " " + config.fraction_word + " " + integer(b)
            if value[:-1]:
                whole = integer(value[:-1])
                if whole is None:
                    return None
                spoken = whole + " và " + spoken
        else:
            spoken = read_number(value, config)
        return cue + spoken + " " + {"tbsp": "thìa canh", "tsp": "thìa cà phê", "cup": "cốc đong"}[unit] if spoken else None
    return None


def _price(name, cue, body, config, units):
    tail = re.fullmatch(rf"(.*?)(?:[ \t]*({_CURRENCY}))?(?:[ \t]*/[ \t]*([\w²³/]+))?", body)
    amount, currency, rate = tail.groups()
    if currency and currency.casefold() not in ("đồng", "vnd", "vnđ", "đ", "₫"):
        return None
    suffix = ""
    if rate:
        reading = read_unit(rate, units, config)
        if reading is None:
            return None
        suffix = " trên " + reading
    scales = {"k": config.thousand, "tr": "triệu"}
    if name == "short_price":
        match = re.fullmatch(rf"({_NUMBER})[ \t]*((?i:tr|k))", amount.strip())
        if match is None:
            return None
        reading = read_number(match[1], config)
        return cue + reading + " " + scales[match[2].lower()] + " đồng" + suffix if reading else None
    pattern = (rf"({_NUMBER})[ \t]*((?i:tr|k))?[ \t]*[-–][ \t]*({_NUMBER})[ \t]*((?i:tr|k))"
               if name == "price_range" else rf"({_NUMBER})[ \t]*((?i:tr))[ \t]*({_NUMBER})[ \t]*((?i:k))")
    match = re.fullmatch(pattern, amount.strip())
    if match is None:
        return None
    a, sa, b, sb = match.groups()
    sa, sb = (sa or sb).lower(), sb.lower()
    x, y = _decimal(a, config), _decimal(b, config)
    if x is None or y is None:
        return None
    if name == "price_range":
        if _scaled_decimal(x, 3 if sa == "k" else 6) > _scaled_decimal(y, 3 if sb == "k" else 6):
            return None
        return cue + read_number(a, config) + " " + scales[sa] + " đồng đến " + read_number(b, config) + " " + scales[sb] + " đồng" + suffix
    if not re.fullmatch(r"[0-9]{1,6}", a) or not 0 <= y < 1000:
        return None
    return cue + read_number(a, config) + " triệu " + read_number(b, config) + " " + config.thousand + " đồng" + suffix


def _scaled_decimal(value, exponent):
    # Decimal tuple construction is exact and independent of ambient precision.
    sign, digits, power = value.as_tuple()
    return Decimal((sign, digits, power + exponent))
