# Provenance

`abbreviations.txt` is adapted from soe-vinorm by Vinh Dang via the local
ZeroTTS integration (`src/zerotts/text_norm/data/abbreviations.txt`). Its MIT
license is retained verbatim in `LICENSE.soe-vinorm`.

The scanner architecture, conservative URL protection and context-aware date
and abbreviation handling build on ZeroTTS's `vi_normalizer.py`. The unit and
letter-name inventories combine that implementation with OmniVoice's local
`scripts/text_normalize.py`. Number parsing, configuration, span tracing and
integration code were implemented for this combined package.

Readings are application policies, not a claim that every abbreviation or
ambiguous numeric form has a unique interpretation. Dictionary ambiguity is
retained instead of selecting the first reading.
