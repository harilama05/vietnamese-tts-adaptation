"""Compositional units with case-sensitive symbols, products and exponents."""

import re
from typing import Mapping, Optional

from .config import DEFAULT_CONFIG, NormalizerConfig
from .lexicon import CURRENCY_NAMES, CURRENCY_SYMBOLS, WORD_CURRENCIES, WORD_UNITS
from .numbers import read_number

# Shared count/rate vocabulary for both ordinary quantities and commerce rules.
# These are denominator atoms, not special cases for complete unit strings.
RATE_WORDS = {
    "người": "người", "lần": "lần", "ngày": "ngày", "đêm": "đêm",
    "tuần": "tuần", "tháng": "tháng", "năm": "năm", "giờ": "giờ",
    "phút": "phút", "giây": "giây", "vé": "vé", "chiếc": "chiếc", "lượt": "lượt",
    "ly": "ly", "cốc": "cốc", "chai": "chai", "hộp": "hộp",
    "suất": "suất", "phần": "phần", "gói": "gói", "phòng": "phòng",
    "thùng": "thùng", "bao": "bao", "kiện": "kiện",
}
VI_CURRENCY = frozenset(("đ", "₫", "VND", "VNĐ", "đồng"))
# CAD is also "computer-aided design": it is a unit after a number ("5 CAD")
# but never a currency prefix ("CAD 2024" stays a product name).
CURRENCY = (VI_CURRENCY | frozenset(("$", "USD", "EUR", "€", "£", "GBP", "JPY", "CNY", "KRW"))
            | frozenset(CURRENCY_NAMES).difference(("CAD",)) | frozenset(CURRENCY_SYMBOLS) | WORD_CURRENCIES)
# Amounts written in Vietnamese text group thousands with a dot: 26.569 đồng, 5.150 riel.
VI_FORMAT_CURRENCY = VI_CURRENCY | WORD_CURRENCIES
_SUPERSCRIPT = "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺"
_POWER = rf"(?:\^[+−-]?[0-9]+|[{_SUPERSCRIPT}]+)"


def currency_identity(symbol: str) -> str:
    """Compare currency aliases without inferring exchange rates or readings."""
    if symbol in VI_CURRENCY:
        return "VND"
    return {"$": "USD", "€": "EUR", "£": "GBP", **CURRENCY_SYMBOLS}.get(symbol, symbol)


def literal_pattern(unit: str) -> str:
    pattern = re.escape(unit).replace("/", r"[ \t]*/[ \t]*").replace("°", r"°[ \t]*").replace(r"\ ", r"[ \t]+")
    return "(?i:" + pattern + ")" if unit in WORD_UNITS or unit in RATE_WORDS else pattern


def unit_pattern(keys: tuple[str, ...], *, compound_only: bool = False) -> str:
    base = "(?:" + "|".join(literal_pattern(k) for k in sorted(keys, key=len, reverse=True)) + ")"
    words = "(?i:" + "|".join(re.escape(k) for k in RATE_WORDS) + ")"
    atom = base + rf"(?:{_POWER})?"
    denominator = rf"(?:[0-9]{{1,6}}[ \t]*)?(?:{atom}|{words})"
    tail = rf"(?:[ \t]*/[ \t]*{denominator}|[ \t]*[*·][ \t]*(?:{atom}|{words}))"
    if not compound_only:
        return atom + tail + "{0,3}"
    # A bare unit must contain an explicit operator. Include registered compound
    # aliases whose components are not individually registered (e.g. mg/dL).
    compounds = [literal_pattern(k) for k in sorted(keys, key=len, reverse=True)
                 if any(operator in k for operator in "/·*")]
    composed = atom + tail + "{1,3}"
    if compounds:
        aliases = "(?:" + "|".join(compounds) + ")"
        return "(?:" + composed + "|" + aliases + tail + "{0,3})"
    return composed


def _read_atom(unit: str, table: Mapping[str, str], config: NormalizerConfig) -> Optional[str]:
    if unit in table:
        return table[unit]
    word = unit.casefold()
    if word in RATE_WORDS or word in WORD_UNITS:
        return table.get(word, RATE_WORDS.get(word))
    match = re.fullmatch(rf"(.+?)({_POWER})", unit)
    if not match or match[1] not in table:
        return None
    base, exponent = match.groups()
    # Do not interpret repeated powers or powers attached to compound units.
    if re.search(rf"[/·*^0-9{_SUPERSCRIPT}]", base) or base in CURRENCY or base.casefold() in RATE_WORDS:
        return None
    exponent = exponent.lstrip("^").translate(str.maketrans(_SUPERSCRIPT, "0123456789-+"))
    if not re.fullmatch(r"[+−-]?[0-9]+", exponent):
        return None
    spoken = read_number(exponent, config)
    if spoken is None:
        return None
    suffix = {"2": "bình phương", "3": "lập phương"}.get(exponent, "mũ " + spoken)
    return table[base] + " " + suffix


def exchange_rate(parts: list[str]) -> bool:
    """đồng/USD, VND/GBP: Vietnamese đồng per one unit of a foreign currency (25.338 đồng/USD).

    Other currency pairs after an amount (5 USD/VND, 1,08 EUR/USD) may follow the market quote
    convention, where USD/VND is the price of one dollar in đồng; they stay as written.
    """
    return (len(parts) == 3 and parts[1] == "/" and parts[0] in VI_CURRENCY
            and parts[2] in CURRENCY and parts[2] not in VI_CURRENCY)


def read_unit(unit: str, table: Mapping[str, str], config: NormalizerConfig = DEFAULT_CONFIG) -> Optional[str]:
    unit = re.sub(r"\s+", "", unit)
    if unit in table:
        return table[unit]
    parts = re.split(r"([/·*])", unit)
    if len(parts) > 7:
        return None
    atoms = parts[::2]
    if any(atom in CURRENCY for atom in atoms[1:]) and atoms[0] in CURRENCY and not exchange_rate(parts):
        return None
    readings = []
    for i, atom in enumerate(atoms):
        reading = _read_atom(atom, table, config)
        if reading is None and i and parts[2 * i - 1] == "/":
            counted = re.fullmatch(r"([0-9]{1,6})(.+)", atom)
            if counted and int(counted[1]) > 0:
                unit_reading = _read_atom(counted[2], table, config)
                if unit_reading:
                    reading = read_number(counted[1], config) + " " + unit_reading
        readings.append(reading)
    if any(reading is None for reading in readings):
        return None
    out = readings[0]
    for separator, reading in zip(parts[1::2], readings[1:]):
        out += (" trên " if separator == "/" else " nhân ") + reading
    return out
