"""Linear boundaries for grouped units, including malformed candidates."""


def consume_unit_group(source: str, opening_end: int) -> int:
    """Consume a unit group and attached operators, groups or exponents.

    The scanner consumed the first opening parenthesis. An incomplete group
    stops at the clause boundary. Balanced groups can continue with a spaced
    operator, e.g. kg/(m*s) / (s*A). Ordinary prose is never consumed solely
    because whitespace follows a balanced group.
    """
    depth, end = 1, opening_end
    size = len(source)
    while end < size:
        char = source[end]
        decimal_separator = char in ".," and end > 0 and end + 1 < size and source[end - 1].isdigit() and source[end + 1].isdigit()
        if (char in "\n\r,;!?" and not decimal_separator) or (char == "." and (end + 1 == size or source[end + 1].isspace())):
            break
        if depth:
            end += 1
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            continue
        # An adjacent invalid token must stay with the candidate as well.
        if char == "(":
            depth = 1
            end += 1
        elif decimal_separator or char.isalnum() or char in ")/·*^⁻⁺−-+°%‰$€£":
            end += 1
        elif char in " \t":
            next_pos = end
            while next_pos < size and source[next_pos] in " \t":
                next_pos += 1
            if next_pos < size and source[next_pos] in "/·*^⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺":
                end = next_pos + 1
                while end < size and source[end] in " \t":
                    end += 1
            else:
                break
        else:
            break
    return end
