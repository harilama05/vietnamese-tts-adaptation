"""Name initials shared by character and word based TTS chunkers."""

import re

_NAME = r"[^\W\d_]{2,}(?:[-’'][^\W\d_]+)*"
_SPACE = r"[ \t]*(?:\r?\n[ \t]*)?"
_GAP = r"(?:[ \t]+(?:\r?\n[ \t]*)?|\r?\n[ \t]*)"
_INITIAL_NAME = re.compile(rf"\b(?:(?P<lead>{_NAME}){_GAP})?(?P<initials>(?:[A-ZĐ]\.{_SPACE})+)(?P<surname>{_NAME})\b")
# A capital letter after a list/category cue is a label, not a personal initial.
_SPELLED_TAIL = re.compile(r"(?<![\w.])[A-ZĐ][ \t]+$")
_LABEL_CUES = frozenset(("chọn", "án", "mục", "phần", "loại", "hạng", "bảng", "nhóm",
                         "đội", "lớp", "khu", "lô", "khối", "điểm", "câu", "cột", "hàng"))


def initial_name_spans(text: str):
    """Yield name spans containing initials, without treating every 'A.' as a name.

    Require capitalized surrounding names (Donald J. Trump, J. R. R. Tolkien).
    The final full name must have at least two letters. Sentence punctuation
    after the surname is outside the protected span.
    """
    for match in _INITIAL_NAME.finditer(text):
        lead = match["lead"]
        if not match["surname"][0].isupper() or (lead and lead.casefold() in _LABEL_CUES):
            continue
        # "G D P. Năm nay": spaced capitals are a spelled acronym, not initials.
        if not lead and _SPELLED_TAIL.search(text, 0, match.start("initials")):
            continue
        start = match.start()
        if lead and not lead[0].isupper():
            # Multiple initials are enough evidence for a name after prose;
            # a single initial remains ambiguous with a sentence-ending label.
            if match["initials"].count(".") < 2:
                continue
            start = match.start("initials")
        yield start, match.end()


def initial_periods(text: str) -> set[int]:
    return {i for start, end in initial_name_spans(text)
            for i in range(start, end) if text[i] == "."}
