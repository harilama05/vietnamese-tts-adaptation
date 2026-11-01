"""Vietnamese cardinal/digit readers with validated separator conventions."""

import re
from dataclasses import replace
from typing import Optional

from .config import DEFAULT_CONFIG, NormalizerConfig

NUMBER_PATTERN = r"(?:[0-9]{1,3}(?: [0-9]{3})+(?:[.,][0-9]+)?|[0-9]+(?:[.,][0-9]+)*|\.[0-9]+(?:[.,][0-9]+)*)"

DIGITS = ("không", "một", "hai", "ba", "bốn", "năm", "sáu", "bảy", "tám", "chín")


def read_digits(value: str) -> str:
    return " ".join(DIGITS[int(c)] for c in value if c in "0123456789")


def _chunk(value: int, full: bool, cfg: NormalizerConfig) -> str:
    h, rest = divmod(value, 100)
    t, u = divmod(rest, 10)
    out = []
    if h or full:
        out.extend((DIGITS[h], "trăm"))
    if t >= 2:
        out.extend((DIGITS[t], "mươi"))
    elif t == 1:
        out.append("mười")
    elif u and (h or full):
        out.append(cfg.zero_tens)
    if u:
        if u == 1 and t >= 2:
            out.append("mốt")
        elif u == 5 and t:
            out.append("lăm")
        elif u == 4 and t >= 2:
            out.append("tư")
        elif u == 4 and not t and (h or full):
            out.append(cfg.four_after_zero)
        else:
            out.append(DIGITS[u])
    return " ".join(out)


def read_integer(value: str, cfg: NormalizerConfig = DEFAULT_CONFIG) -> str:
    """Read an unsigned ASCII integer. Leading zeros are a caller's decision."""
    if not re.fullmatch(r"[0-9]+", value):
        raise ValueError("expected unsigned ASCII digits")
    value = value.lstrip("0") or "0"
    if value == "0":
        return DIGITS[0]
    # Bound work and avoid Python's huge-int conversion limits.
    if len(value) > 24:
        return read_digits(value)
    groups = [value[max(0, i - 3):i] for i in range(len(value), 0, -3)][::-1]
    out = []
    for index, group in enumerate(groups):
        n = int(group)
        scale = len(groups) - index - 1
        if not n:
            continue
        suffix = ["", cfg.thousand, "triệu"][scale % 3]
        suffix = " ".join([suffix] + ["tỷ"] * (scale // 3)).strip()
        out.append(" ".join(filter(None, (_chunk(n, index > 0, cfg), suffix))))
    return " ".join(out)


def parse_number(value: str, locale: str = "auto", ambiguous: str = "preserve") -> Optional[tuple[str, str, Optional[str]]]:
    """Return (sign, integer digits, fraction digits) or None for invalid/ambiguous.

    Auto recognizes consistent repeated thousands groups and mixed conventions.
    A single separator followed by three digits is ambiguous (except 0.xxx).
    Spaces group thousands only when every following group has exactly 3 digits.
    """
    sign = ""
    if value[:1] in ("+", "-", "−"):
        sign, value = value[0], value[1:]
    if re.fullmatch(r"\.[0-9]+", value):
        value = "0" + value
    if not value or not re.fullmatch(r"[0-9][0-9., ]*", value):
        return None
    space_grouped = " " in value
    if space_grouped:
        if not re.fullmatch(r"[0-9]{1,3}(?: [0-9]{3})+(?:[.,][0-9]+)?", value):
            return None
        value = value.replace(" ", "")
    if value.isascii() and value.isdigit():
        return sign, value, None
    if locale in ("vi", "en"):
        dec, group = (",", ".") if locale == "vi" else (".", ",")
    elif "." in value and "," in value:
        dec = "." if value.rfind(".") > value.rfind(",") else ","
        group = "," if dec == "." else "."
    else:
        sep = "." if "." in value else ","
        if value.count(sep) > 1:
            dec, group = (",", ".") if sep == "." else (".", ",")
        else:
            left, right = value.split(sep)
            if len(right) == 3 and left != "0" and not space_grouped:
                if ambiguous not in ("vi", "en"):
                    return None
                dec, group = (",", ".") if ambiguous == "vi" else (".", ",")
            else:
                dec, group = sep, ("," if sep == "." else ".")
    if value.count(dec) > 1:
        return None
    parts = value.split(dec)
    whole = parts[0]
    fraction = parts[1] if len(parts) == 2 else None
    if fraction is not None and not re.fullmatch(r"[0-9]+", fraction):
        return None
    if group in whole:
        if not re.fullmatch(r"[0-9]{1,3}(?:" + re.escape(group) + r"[0-9]{3})+", whole):
            return None
        whole = whole.replace(group, "")
    if not re.fullmatch(r"[0-9]+", whole):
        return None
    return sign, whole, fraction


def read_number(value: str, cfg: NormalizerConfig = DEFAULT_CONFIG) -> Optional[str]:
    parsed = parse_number(value, cfg.number_locale, cfg.ambiguous_number)
    if parsed is None:
        return None
    sign, whole, fraction = parsed
    out = read_integer(whole, cfg)
    if fraction is not None:
        # "auto": 34.457,37 -> phẩy ba mươi bảy, 35.920,12 -> phẩy mười hai; a leading zero (0,05)
        # or a longer fraction (3,14159) is read digit by digit.
        if cfg.decimal_reading == "digits" or (cfg.decimal_reading == "auto" and not re.fullmatch(r"[1-9][0-9]", fraction)):
            tail = read_digits(fraction)
        else:
            zero_count = len(fraction) - len(fraction.lstrip("0"))
            tail = " ".join(["không"] * zero_count)
            if fraction.lstrip("0"):
                tail = (tail + " " + read_integer(fraction, cfg)).strip()
        out += " phẩy " + tail
    return ({"-": "âm ", "−": "âm ", "+": "cộng "}.get(sign, "") + out)


def quantity_config(value: str, cfg: NormalizerConfig) -> NormalizerConfig:
    """Vietnamese dotted thousands only beside a validated unit/count noun.

    Bare ambiguous numbers keep the conservative auto policy. Explicit vi/en
    always wins; comma groups and leading-zero decimals are never guessed.
    """
    if cfg.number_locale == "auto" and cfg.ambiguous_number != "en" and re.fullmatch(r"[+−-]?[1-9][0-9]{0,2}(?:\.[0-9]{3})+", value):
        return replace(cfg, number_locale="vi")
    return cfg


def expand_number(value: str, config: NormalizerConfig = DEFAULT_CONFIG) -> str:
    """Public conservative number reader: unsupported forms pass through."""
    return read_number(value, config) or value


_VI_EVIDENCE = re.compile(r"(?<![\w.,])(?:[0-9]{1,3}(?:\.[0-9]{3}){2,}|[0-9]{1,3}(?:\.[0-9]{3})+,[0-9]+|[0-9]+,[0-9]{1,2}|[0-9]+,[0-9]{4,})(?![\w.,]*[0-9])")
_EN_EVIDENCE = re.compile(r"(?<![\w.,])(?:[0-9]{1,3}(?:,[0-9]{3}){2,}|[0-9]{1,3}(?:,[0-9]{3})+\.[0-9]+)(?![\w.,]*[0-9])")


def infer_ambiguous_number(source: str) -> str:
    """Vietnamese unless unambiguous English grouping outnumbers Vietnamese evidence."""
    vi = len(_VI_EVIDENCE.findall(source))
    en = len(_EN_EVIDENCE.findall(source))
    return "en" if en > vi else "vi"
