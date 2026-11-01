"""Bounded grammar for explicit unit groups; no evaluation or unit conversion."""

from dataclasses import dataclass
import re
from typing import Mapping, Optional

from .config import NormalizerConfig
from .numbers import read_number
from .units import CURRENCY, _read_atom

_SUPERSCRIPT = "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺"
_TRANS = str.maketrans(_SUPERSCRIPT, "0123456789-+")
_POWER = re.compile(r"\^[ \t]*[+−-]?[0-9]+|[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+")


@dataclass(frozen=True)
class UnitNode:
    kind: str  # atom | group | product | quotient | power
    value: str = ""
    left: Optional["UnitNode"] = None
    right: Optional["UnitNode"] = None

    def speak(self, table: Mapping[str, str], config: NormalizerConfig) -> str:
        if self.kind == "atom":
            return _read_atom(self.value, table, config)
        left = self.left.speak(table, config)
        if self.kind == "group":
            return "mở ngoặc " + left + " đóng ngoặc"
        if self.kind == "power":
            suffix = {"2": "bình phương", "3": "lập phương"}.get(self.value)
            return left + " " + (suffix or "mũ " + read_number(self.value, config))
        join = " trên " if self.kind == "quotient" else " nhân "
        return left + join + self.right.speak(table, config)


class _InvalidUnit(ValueError):
    pass


class _Parser:
    def __init__(self, text, table, config):
        self.text, self.table, self.config = text, table, config
        self.pos, self.nodes = 0, 0

    def skip(self):
        while self.pos < len(self.text) and self.text[self.pos] in " \t":
            self.pos += 1

    def node(self, kind, value="", left=None, right=None):
        self.nodes += 1
        if self.nodes > 64:
            raise _InvalidUnit("resource_limit")
        return UnitNode(kind, value, left, right)

    def factor(self, depth):
        self.skip()
        if depth > 16:
            raise _InvalidUnit("resource_limit")
        if self.pos == len(self.text):
            raise _InvalidUnit("invalid_unit_syntax")
        if self.text[self.pos] == "(":
            self.pos += 1
            inner = self.expression(depth + 1)
            self.skip()
            if self.pos == len(self.text) or self.text[self.pos] != ")":
                raise _InvalidUnit("invalid_unit_syntax")
            self.pos += 1
            node = self.node("group", left=inner)
        else:
            start = self.pos
            while self.pos < len(self.text) and self.text[self.pos] not in " \t\r\n/*·()^" + _SUPERSCRIPT:
                self.pos += 1
            token = self.text[start:self.pos]
            if not token:
                raise _InvalidUnit("invalid_unit_syntax")
            if token in CURRENCY:
                raise _InvalidUnit("unsupported_currency_group")
            if _read_atom(token, self.table, self.config) is None:
                raise _InvalidUnit("unknown_unit")
            node = self.node("atom", token)
        self.skip()
        power = _POWER.match(self.text, self.pos)
        if power:
            value = power.group().lstrip("^").strip().translate(_TRANS).replace("−", "-")
            if not re.fullmatch(r"[+-]?[0-9]{1,2}", value):
                raise _InvalidUnit("unsupported_unit_exponent")
            # A second exponent is rejected by the enclosing full-consumption check.
            self.pos = power.end()
            node = self.node("power", value, node)
        return node

    def expression(self, depth=0):
        node = self.factor(depth)
        while True:
            self.skip()
            if self.pos == len(self.text) or self.text[self.pos] == ")":
                return node
            op = self.text[self.pos]
            if op not in "/*·":
                raise _InvalidUnit("invalid_unit_syntax")
            self.pos += 1
            right = self.factor(depth)
            node = self.node("quotient" if op == "/" else "product", left=node, right=right)


def parse_unit_tree(text: str, table: Mapping[str, str], config: NormalizerConfig):
    """Return (tree, reason); bounded to 16 nested groups and 64 AST nodes.

    Only explicit multiplication/division and integer powers -99..99 are
    supported. Whitespace alone is never multiplication. Groups remain spoken
    so division scope and powers of a group survive rendering.
    """
    if len(text) > config.max_expression_chars:
        return None, "resource_limit"
    compact = re.sub(r"[ \t]+", "", text)
    if any(re.sub(r"\s+", "", key) == compact for key in config.unit_overrides):
        return UnitNode("atom", compact), "configured_unit_reading"
    parser = _Parser(text, table, config)
    try:
        tree = parser.expression()
        if parser.pos != len(text):
            return None, "invalid_unit_syntax"
        return tree, "validated_unit_tree"
    except _InvalidUnit as error:
        return None, str(error)
