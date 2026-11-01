"""A typed expression plus its trailing unit; readers never rescan spoken text."""

from dataclasses import dataclass
import re
from typing import Mapping, Optional, Pattern

from .config import NormalizerConfig
from .expressions import read_expression
from .units import read_unit


@dataclass(frozen=True)
class ExpressionQuantity:
    expression: str
    unit: str

    def speak(self, config: NormalizerConfig, units: Mapping[str, str]) -> Optional[str]:
        expression = read_expression(self.expression, config)
        unit = read_unit(self.unit, units, config)
        return expression + " " + unit if expression and unit else None


def parse_expression_quantity(
    text: str, unit_pattern: Pattern[str], *, dimensions: bool = False,
) -> Optional[ExpressionQuantity]:
    suffix = unit_pattern.search(text)
    if suffix is None:
        return None
    expression = text[:suffix.start()].strip()
    if dimensions:
        expression = re.sub(r"[x×]", "×", expression)
    return ExpressionQuantity(expression, suffix.group())


def read_grouped_quantity(text: str, config: NormalizerConfig, units: Mapping[str, str]):
    """Validate magnitude and grouped unit together; preserve either failure."""
    from .numbers import NUMBER_PATTERN, read_number
    from .unit_tree import parse_unit_tree

    if len(text) > config.max_expression_chars:
        return text, "resource_limit"
    first = re.search(r"[^\W\d_]|[°%‰$€£]", text)
    if first is None:
        return text, "invalid_quantity"
    split = first.start()
    # A unit may itself start with parentheses: 5 ((kg*m)/s).
    while split and text[split - 1] in "( \t":
        split -= 1
    value, unit = text[:split].strip(), text[split:].strip()
    tree, reason = parse_unit_tree(unit, units, config)
    if tree is None:
        return text, reason
    signed = rf"[+−-]?{NUMBER_PATTERN}"
    interval = re.fullmatch(rf"({signed})[ \t]*[–-][ \t]*({signed})", value)
    if interval:
        left, right = (read_number(v, config) for v in interval.groups())
        magnitude = left + " đến " + right if left and right else None
    else:
        magnitude = read_expression(value, config)
    if magnitude is None:
        return text, "invalid_or_ambiguous_magnitude"
    return magnitude + " " + tree.speak(units, config), reason
