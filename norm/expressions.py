"""Validate and speak numeric expressions; never evaluate user input."""

import re
from typing import Optional

from .config import NormalizerConfig
from .numbers import NUMBER_PATTERN, read_number

OPERATORS = {
    "+": "cộng", "-": "trừ", "−": "trừ", "*": "nhân", "×": "nhân",
    "/": "chia", "÷": "chia", "^": "mũ", "=": "bằng", "<": "nhỏ hơn",
    ">": "lớn hơn", "≤": "nhỏ hơn hoặc bằng", "≥": "lớn hơn hoặc bằng",
    "<=": "nhỏ hơn hoặc bằng", ">=": "lớn hơn hoặc bằng", "!=": "khác",
    "≠": "khác", "±": "cộng trừ",
}
_TOKEN = re.compile(rf"{NUMBER_PATTERN}|<=|>=|!=|[()+*×÷/^=<>≤≥≠±−-]")


def read_expression(text: str, config: NormalizerConfig) -> Optional[str]:
    """Return None for malformed input, unbalanced parentheses or ambiguous numbers.

    Parentheses are spoken explicitly to retain grouping. An iterative syntax
    check avoids recursion limits on deep input. No arithmetic is performed.
    """
    out = []
    end, depth = 0, 0
    operand, sign_used = True, False
    for match in _TOKEN.finditer(text):
        if text[end:match.start()].strip():
            return None
        end = match.end()
        token = match.group()
        if token == "(":
            if not operand:
                return None
            depth += 1
            out.append("mở ngoặc")
            sign_used = False
        elif token == ")":
            if operand or not depth:
                return None
            depth -= 1
            out.append("đóng ngoặc")
            operand = False
        elif token in OPERATORS:
            if operand:
                if token not in ("+", "-", "−", "±") or sign_used:
                    return None
                out.append("âm" if token in ("-", "−") else OPERATORS[token])
                sign_used = True
            else:
                out.append(OPERATORS[token])
                operand, sign_used = True, False
        else:
            if not operand:
                return None
            spoken = read_number(token, config)
            if spoken is None:
                return None
            out.append(spoken)
            operand, sign_used = False, False
    if text[end:].strip() or operand or depth:
        return None
    return " ".join(out)
