"""Case-sensitive units and attributed abbreviation data, loaded lazily."""

from functools import lru_cache
from pathlib import Path

# SI prefixes are case-sensitive: mW and MW must never share a reading.
UNITS = {
    "%": "phần trăm", "‰": "phần nghìn", "ppm": "phần triệu",
    "mm": "mi li mét", "cm": "xăng ti mét", "dm": "đề xi mét", "m": "mét",
    "km": "ki lô mét", "nm": "na nô mét", "µm": "mi crô mét", "μm": "mi crô mét",
    "mg": "mi li gam", "g": "gam", "kg": "ki lô gam", "µg": "mi crô gam",
    "μg": "mi crô gam", "cg": "xăng ti gam", "dg": "đề xi gam",
    "ml": "mi li lít", "mL": "mi li lít", "cl": "xăng ti lít", "kl": "ki lô lít", "kL": "ki lô lít",
    "dl": "đề xi lít", "l": "lít", "L": "lít", "ha": "héc ta",
    "ns": "na nô giây", "µs": "mi crô giây", "μs": "mi crô giây",
    "ms": "mi li giây", "s": "giây", "min": "phút", "h": "giờ",
    "°": "độ", "°C": "độ xê", "°F": "độ ép", "K": "ken vin",
    "Pa": "pát can", "kPa": "ki lô pát can", "MPa": "mê ga pát can",
    "bar": "ba", "atm": "át mốt phe", "psi": "pi ét xi", "mmHg": "mi li mét thủy ngân",
    "J": "jun", "kJ": "ki lô jun", "MJ": "mê ga jun",
    "W": "oát", "mW": "mi li oát", "kW": "ki lô oát", "MW": "mê ga oát",
    "GW": "ghi ga oát", "Wh": "oát giờ", "kWh": "ki lô oát giờ",
    "V": "vôn", "mV": "mi li vôn", "kV": "ki lô vôn",
    "A": "am pe", "mA": "mi li am pe", "kA": "ki lô am pe",
    "Ω": "ôm", "ohm": "ôm", "Wb": "vê be", "T": "tét la",
    "Hz": "héc", "kHz": "ki lô héc", "MHz": "mê ga héc", "GHz": "ghi ga héc",
    "lm": "lu men", "lx": "lúc", "cd": "can đê la", "rad": "ra đi an",
    "mol": "mol", "N": "niu tơn", "kN": "ki lô niu tơn", "C": "cu lông",
    "B": "bai", "KB": "ki lô bai", "MB": "mê ga bai", "GB": "ghi ga bai",
    "TB": "tê ra bai", "Kb": "ki lô bít", "Mb": "mê ga bít", "Gb": "ghi ga bít",
    "bps": "bít trên giây", "Mbps": "mê ga bít trên giây", "Gbps": "ghi ga bít trên giây",
    "đồng": "đồng", "đ": "đồng", "₫": "đồng", "VND": "đồng", "VNĐ": "đồng",
    "USD": "đô la Mỹ", "EUR": "ơ rô", "€": "ơ rô", "£": "bảng Anh",
    "GBP": "bảng Anh", "JPY": "yên Nhật", "CNY": "nhân dân tệ", "KRW": "uôn Hàn Quốc",
}
# Currency codes and prefixed dollar signs, read by meaning (US$5 -> năm đô la Mỹ).
# The bare "$" keeps NormalizerConfig.dollar_name.
CURRENCY_NAMES = {
    "AUD": "đô la Úc", "CAD": "đô la Canada", "SGD": "đô la Xin ga po", "HKD": "đô la Hồng Kông",
    "NZD": "đô la New Zealand", "TWD": "Đài tệ", "THB": "bạt Thái", "INR": "rupee Ấn Độ",
    "RUB": "rúp Nga", "CHF": "franc Thụy Sĩ", "MYR": "ringgit Malaysia", "IDR": "rupiah Indonesia",
    "LAK": "kíp Lào", "KHR": "riel Campuchia",
}
CURRENCY_SYMBOLS = {
    "US$": "USD", "HK$": "HKD", "S$": "SGD", "A$": "AUD", "AU$": "AUD", "C$": "CAD", "CA$": "CAD",
    "NZ$": "NZD", "NT$": "TWD", "¥": "JPY", "₩": "KRW", "₹": "INR", "₽": "RUB", "฿": "THB",
}
UNITS.update(CURRENCY_NAMES)
UNITS.update({symbol: UNITS[code] for symbol, code in CURRENCY_SYMBOLS.items()})
UNITS.update({
    "µmol": "mi crô mol", "μmol": "mi crô mol", "dB": "đề xi ben",
    "KiB": "ki bi bai", "MiB": "mê bi bai", "GiB": "ghi bi bai",
    "lít": "lít", "vòng": "vòng",
    "litre": "lít", "litres": "lít", "liter": "lít", "liters": "lít", "kilolít": "ki lô lít",
    "kilolitre": "ki lô lít", "kilolitres": "ki lô lít", "kiloliter": "ki lô lít", "kiloliters": "ki lô lít",
    "tấn": "tấn", "tạ": "tạ", "yến": "yến", "lượng": "lượng", "chỉ": "chỉ",
    "bbl": "thùng", "oz": "ao xơ", "ounce": "ao xơ", "ounces": "ao xơ", "gallon": "ga lông", "gal": "ga lông",
    "feet": "phít", "ft": "phít", "dặm": "dặm", "mile": "dặm", "miles": "dặm",
    # Currencies written as words in Vietnamese text: 5.150 riel/lít.
    "riel": "riel", "kíp": "kíp", "bạt": "bạt", "baht": "bạt", "yên": "yên", "won": "uôn", "rúp": "rúp",
    "ringgit": "ringgit", "rupiah": "rupiah", "rupee": "rupee", "peso": "pê xô",
    "mAh": "mi li am pe giờ", "MP": "mê ga pích xeo", "nit": "nít", "nits": "nít", "euro": "ơ rô",
})
# Written unit names may be capitalized in headings; SI symbols remain exact.
WORD_CURRENCIES = frozenset(("riel", "kíp", "bạt", "baht", "yên", "won", "rúp", "ringgit", "rupiah", "rupee", "peso"))
WORD_UNITS = frozenset(("đồng", "lít", "vòng", "tấn", "tạ", "yến", "lượng", "chỉ", "gallon", "euro", "feet", "dặm", "ounce", "ounces",
                        "litre", "litres", "liter", "liters", "kilolít", "kilolitre", "kilolitres", "kiloliter", "kiloliters")
                       ) | WORD_CURRENCIES
for _base in ("mm", "cm", "dm", "m", "km"):
    for _power, _reading in (("2", "vuông"), ("3", "khối")):
        for _suffix in (_power, {"2": "²", "3": "³"}[_power], "^" + _power):
            UNITS[_base + _suffix] = UNITS[_base] + " " + _reading
for _numerator, _denominator in (
    ("m", "s"), ("km", "h"), ("km", "s"), ("mg", "kg"), ("mg", "ml"),
    ("g", "l"), ("mol", "l"), ("MB", "s"), ("GB", "s"), ("l", "min"),
):
    UNITS[_numerator + "/" + _denominator] = UNITS[_numerator] + " trên " + UNITS[_denominator]

# Common acceleration, surface density and medical concentration forms.
for _unit, _reading in {
    "m/s²": "mét trên giây bình phương", "m/s2": "mét trên giây bình phương",
    "m/s^2": "mét trên giây bình phương", "kg/m²": "ki lô gam trên mét vuông",
    "kg/m2": "ki lô gam trên mét vuông", "kg/m³": "ki lô gam trên mét khối",
    "mg/dL": "mi li gam trên đề xi lít", "mmol/L": "mi li mol trên lít",
}.items():
    UNITS[_unit] = _reading

LETTER_NAMES = dict(zip(
    "ABCDEFGHIJKLMNOPQRSTUVWXYZĐĂÂÊÔƠƯ",
    ("a", "bê", "xê", "đê", "e", "ép", "gờ", "hắt", "i", "giây", "ca", "lờ",
     "mờ", "nờ", "ô", "pê", "quy", "e rờ", "ét", "tê", "u", "vê", "vê kép",
     "ích", "y", "giét", "đê", "á", "ớ", "ê", "ô", "ơ", "ư"),
))


def spell_letters(value: str) -> str:
    """Vietnamese letter names: GDP -> "gờ đê pê"."""
    return " ".join(LETTER_NAMES.get(c, c) for c in value.upper())


def latin_letters(value: str) -> str:
    """Spaced capitals the TTS model reads itself: GDP -> "G D P"."""
    return " ".join(value.upper())


@lru_cache(maxsize=1)
def _abbreviations() -> dict[str, tuple[str, ...]]:
    table = {}
    path = Path(__file__).parent / "data" / "abbreviations.txt"
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#") or ":" not in line:
            continue
        key, values = line.split(":", 1)
        if not key.isupper():
            continue
        entries = list(table.get(key, ()))
        for reading in values.split(","):
            reading = reading.strip()
            if reading and reading.casefold() not in {v.casefold() for v in entries}:
                entries.append(reading)
        table[key] = tuple(entries)
    return table


def load_abbreviations() -> dict[str, list[str]]:
    """Return a copy: callers cannot mutate the cached default dictionary."""
    return {k: list(v) for k, v in _abbreviations().items()}
