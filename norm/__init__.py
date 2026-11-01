"""Portable, standard-library-only Vietnamese text normalization for TTS."""

from ._version import __version__
from .acronyms import COMMON as COMMON_ABBREVIATIONS
from .config import NormalizerConfig
from .lexicon import load_abbreviations
from .normalizer import NormalizationResult, Normalizer, normalize_vi_text
from .numbers import expand_number, read_digits, read_integer

__all__ = [
    "__version__", "COMMON_ABBREVIATIONS", "NormalizerConfig", "Normalizer", "NormalizationResult", "normalize_vi_text",
    "expand_number", "read_digits", "read_integer", "load_abbreviations",
]
