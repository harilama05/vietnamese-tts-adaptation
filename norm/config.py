"""Explicit reading policies; normalization does not infer a speaker's dialect."""

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


DOMAIN_NAMES = ("commerce", "education", "transport", "technology", "sports", "housing", "administration", "lifestyle", "news")


@dataclass(frozen=True)
class NormalizerConfig:
    zero_tens: str = "lẻ"
    thousand: str = "nghìn"
    four_after_zero: str = "bốn"
    # auto: a two-digit fraction is a number (3,75 -> ba phẩy bảy mươi lăm), others digit by digit
    # (0,05 -> không phẩy không năm, 3,14159); digits: always digit by digit; cardinal: always a number.
    decimal_reading: str = "auto"  # auto | digits | cardinal
    number_locale: str = "auto"  # auto | vi | en
    ambiguous_number: str = "infer"  # infer | vi | en | preserve (auto locale only)
    acronym_mode: str = "latin"  # latin (G D P) | spell (0.10.0 Vietnamese letter names) | preserve
    abbreviation_policy: str = "common"  # common | extended (legacy soe-vinorm) | none
    link_mode: str = "domain"  # domain (bare domains read, URLs kept) | preserve | speak
    datetime_mode: str = "speak"  # speak | preserve (ISO timestamps)
    normalize_fullwidth_numbers: bool = True
    fraction_word: str = "trên"  # trên | phần
    range_prefix: str = "từ"  # từ: "20%-30%" -> "từ ... đến ..."; "" keeps "... đến ..."
    preserve_case: bool = True
    preserve_punctuation: bool = True
    split_camel_case: bool = True
    dollar_name: str = "đô la"
    abbreviation_overrides: Mapping[str, str] = field(default_factory=dict)
    unit_overrides: Mapping[str, str] = field(default_factory=dict)

    max_token_chars: int = 512  # preserve longer non-whitespace tokens atomically

    duration_format: str = "clock"  # clock (compatible default) | mm:ss | hh:mm
    max_expression_chars: int = 2048  # includes internal horizontal whitespace

    enabled_domains: tuple[str, ...] = DOMAIN_NAMES

    content_profile: str = "omnivoice"  # compatible protected brackets | plain_text

    def __post_init__(self):
        if not isinstance(self.enabled_domains, (list, tuple)) or any(not isinstance(name, str) or name not in DOMAIN_NAMES for name in self.enabled_domains):
            raise ValueError("enabled_domains must be a list/tuple of supported domain names")
        if len(set(self.enabled_domains)) != len(self.enabled_domains):
            raise ValueError("enabled_domains must not contain duplicates")
        object.__setattr__(self, "enabled_domains", tuple(name for name in DOMAIN_NAMES if name in self.enabled_domains))
        if type(self.max_token_chars) is not int or not 64 <= self.max_token_chars <= 4096:
            raise ValueError("max_token_chars must be an integer between 64 and 4096")
        if type(self.max_expression_chars) is not int or not 64 <= self.max_expression_chars <= 65536:
            raise ValueError("max_expression_chars must be an integer between 64 and 65536")
        choices = {
            "content_profile": {"omnivoice", "plain_text"},
            "duration_format": {"clock", "mm:ss", "hh:mm"},
            "zero_tens": {"linh", "lẻ"},
            "thousand": {"nghìn", "ngàn"},
            "four_after_zero": {"bốn", "tư"},
            "decimal_reading": {"auto", "digits", "cardinal"},
            "number_locale": {"auto", "vi", "en"},
            "ambiguous_number": {"infer", "vi", "en", "preserve"},
            "acronym_mode": {"latin", "preserve", "spell"},
            "abbreviation_policy": {"common", "extended", "none"},
            "link_mode": {"domain", "preserve", "speak"},
            "datetime_mode": {"speak", "preserve"},
            "fraction_word": {"trên", "phần"},
            "range_prefix": {"từ", ""},
        }
        for name, allowed in choices.items():
            if not isinstance(getattr(self, name), str) or getattr(self, name) not in allowed:
                raise ValueError(f"{name} must be one of {sorted(allowed)}")
        for name in ("preserve_case", "preserve_punctuation", "split_camel_case", "normalize_fullwidth_numbers"):
            if not isinstance(getattr(self, name), bool):
                raise ValueError(f"{name} must be a boolean")
        if not isinstance(self.dollar_name, str) or not self.dollar_name.strip():
            raise ValueError("dollar_name must be a nonempty string")
        for name in ("abbreviation_overrides", "unit_overrides"):
            values = dict(getattr(self, name))
            if any(not isinstance(k, str) or not k.strip() or not isinstance(v, str) or not v.strip()
                   for k, v in values.items()):
                raise ValueError(f"{name} must map nonempty strings to readings")
            object.__setattr__(self, name, MappingProxyType(values))


DEFAULT_CONFIG = NormalizerConfig()
