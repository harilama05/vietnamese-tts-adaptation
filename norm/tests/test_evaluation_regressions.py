"""Reported September 25 errors, plus competing readings of '/' and '-'."""

import calendar
import csv
import importlib.util
from pathlib import Path
import random

import pytest

from vietnamese_tts_normalizer import Normalizer, NormalizerConfig
from vietnamese_tts_normalizer.expressions import read_expression
from vietnamese_tts_normalizer.numbers import read_integer, read_number

ROOT = Path(__file__).resolve().parents[2]


def assert_reading(source, expected, config=None):
    n = Normalizer(config or NormalizerConfig())
    result = n.normalize_with_trace(source)
    assert result.text == expected
    assert n.normalize(result.text) == result.text
    rebuilt, end = [], 0
    for span in result.spans:
        assert result.source[span.start:span.end] == span.source
        assert end <= span.start
        rebuilt.extend((result.source[end:span.start], span.spoken))
        end = span.end
    rebuilt.append(result.source[end:])
    assert "".join(rebuilt) == expected


@pytest.mark.parametrize("source,expected", [
    ("6,23 USD/gallon", "sáu phẩy hai mươi ba đô la Mỹ trên ga lông"),
    ("$4,47/gallon", "bốn phẩy bốn mươi bảy đô la trên ga lông"),
    ("ngày 18-19 tháng 11", "ngày mười tám đến mười chín tháng mười một"),
    ("Ngày 14-15 tháng 9", "Ngày mười bốn đến mười lăm tháng chín"),
    ("(6/8/1976-6/8 /2026)", "(từ sáu tháng tám năm một nghìn chín trăm bảy mươi sáu đến sáu tháng tám năm hai nghìn không trăm hai mươi sáu)"),
    ("(6/8/1976-6/8/2026)", "(từ sáu tháng tám năm một nghìn chín trăm bảy mươi sáu đến sáu tháng tám năm hai nghìn không trăm hai mươi sáu)"),
    ("1.000 km²", "một nghìn ki lô mét vuông"),
    ("USD/Thùng", "đô la Mỹ trên thùng"),
    ("$44/thùng", "bốn mươi tư đô la trên thùng"),
])
def test_reported_errors(source, expected):
    assert_reading(source, expected)


@pytest.mark.parametrize("domains", [None, ()])
@pytest.mark.parametrize("currency,spoken", [("USD", "đô la Mỹ"), ("$", "đô la"), ("EUR", "ơ rô"), ("€", "ơ rô"), ("£", "bảng Anh")])
@pytest.mark.parametrize("denominator,spoken_unit", [("Thùng", "thùng"), ("THÙNG", "thùng"), ("gallon", "ga lông"), ("Gallon", "ga lông"), ("gal", "ga lông"), ("bbl", "thùng"), ("kg", "ki lô gam")])
def test_currency_rates_share_grammar(domains, currency, spoken, denominator, spoken_unit):
    cfg = NormalizerConfig() if domains is None else NormalizerConfig(enabled_domains=domains)
    for source in (f"{currency}44 / {denominator}", f"44 {currency} / {denominator}"):
        assert_reading(source, f"bốn mươi tư {spoken} trên {spoken_unit}", cfg)


@pytest.mark.parametrize("source,expected", [
    ("$4,47 / gallon / ngày", "bốn phẩy bốn mươi bảy đô la trên ga lông trên ngày"),
    ("USD 40–44/thùng", "từ bốn mươi đến bốn mươi tư đô la Mỹ trên thùng"),
    ("€44/100 kg", "bốn mươi tư ơ rô trên một trăm ki lô gam"),
    ("$.5/Thùng", "không phẩy năm đô la trên thùng"),
    ("USD-.5/gallon", "âm không phẩy năm đô la Mỹ trên ga lông"),
    ("44 USD/Thùng/ngày", "bốn mươi tư đô la Mỹ trên thùng trên ngày"),
    ("1.200 km", "một nghìn hai trăm ki lô mét"),
    ("1.000–2.000 km²", "từ một nghìn đến hai nghìn ki lô mét vuông"),
    ("0.005 km²", "không phẩy không không năm ki lô mét vuông"),
    ("3.5 km²", "ba phẩy năm ki lô mét vuông"),
    ("248.000 người", "hai trăm bốn mươi tám nghìn người"),
    ("248.000 binh sĩ", "hai trăm bốn mươi tám nghìn binh sĩ"),
    ("ngày 22 (giờ Nhật Bản 23)", "ngày hai mươi hai (giờ Nhật Bản hai mươi ba)"),
    ("ngày 18 – 19 tháng 11 năm 2026", "ngày mười tám đến mười chín tháng mười một năm hai nghìn không trăm hai mươi sáu"),
    ("14—15 tháng 9", "từ mười bốn đến mười lăm tháng chín"),
    ("ngày 3 - 5 / 4", "ngày ba đến năm tháng tư"),
    ("ngày 3 - 5 / 4 / 2026", "ngày ba đến năm tháng tư năm hai nghìn không trăm hai mươi sáu"),
    ("6 / 8 / 2026", "sáu tháng tám năm hai nghìn không trăm hai mươi sáu"),
])
def test_generalized_forms(source, expected):
    assert_reading(source, expected)


@pytest.mark.parametrize("source", [
    "USD/VND", "5 USD/VND",
    "USD/ThùngX", "$44/thùngX", "$44/0 thùng", "44 USD/Thùng/unknown",
    "$44/thùng / unknown", "44 USD/Thùng / unknown", "USD/Thùng / unknown",
    "44 usd/thùng", "44 USD/THÙNG^2", "44 USD/GAL", "44 KM/H",
    "ngày 31-32 tháng 2", "ngày 19-18 tháng 11", "ngày 28-29 tháng 2 năm 2023",
    "ngày 18-19 tháng 11 năm 202600", "ngày 3-5 tháng 130", "ngày 100-120 tháng 11",
    "ngày 3 - 5 / 4 / 26", "ngày 31 - 32 / 2 / 2026",
    "(31/2/2026-6/8 /2026)", "(6/8/2026-6/8/1976)", "(6/8/76-6/8/26)",
    "(6/8-1976-6/8/2026)", "(31 / 2 / 2026)",
    "https://example.vn/6/8/1976-6/8/2026", "[6/8/1976-6/8/2026]",
    "`$44/Thùng`", "[1.000 km²]", "(6/8/1976-6/8/2026",
])
def test_invalid_ambiguous_and_protected_forms(source):
    assert_reading(source, source)


@pytest.mark.parametrize("source,expected", [
    ("USD 1.234", "một nghìn hai trăm ba mươi tư đô la Mỹ"),
    ("1.234", "một nghìn hai trăm ba mươi tư"),
    ("1,234 km²", "một phẩy hai ba bốn ki lô mét vuông"),
])
def test_ambiguous_number_is_inferred_by_default_and_preserved_on_request(source, expected):
    # "preserve" keeps the 0.9.x behaviour; the 0.10.0 default reads the number.
    assert_reading(source, source, NormalizerConfig(ambiguous_number="preserve"))
    assert_reading(source, expected)


@pytest.mark.parametrize("source,expected", [
    ("3/4", "ba trên bốn"), ("ngày 3/4", "ngày ba tháng tư"),
    ("tính 3 / 4", "tính ba chia bốn"),
    ("số nhà 3/4", "số nhà ba xuyệt bốn"),
    ("điểm 3/4", "điểm ba trên bốn"),
    ("tỷ số 3-4", "tỷ số ba bốn"),
])
def test_context_selects_slash_reading(source, expected):
    assert_reading(source, expected)


@pytest.mark.parametrize("cue", ["tính", "tính:", "phép chia", "phép tính", "biểu thức"])
@pytest.mark.parametrize("expression", ["3/4", "3 / 4", "(3/4)", "(3 / 4)"])
def test_math_cues_apply_with_or_without_operator_spaces(cue, expression):
    assert_reading(cue + " " + expression, cue + " " + read_expression(expression, NormalizerConfig()))


@pytest.mark.parametrize("expression", [
    "(6/8/1976-6/8/2026)", "6 / 8 / 2026", "(6 / 8 / 2026)",
    "(6/8/1976-6/8/2026)+2", "(6/8/1976-6/8/2026) = 0", "2*(6/8/2026)",
])
def test_explicit_math_retains_operators(expression):
    assert_reading("tính " + expression, "tính " + read_expression(expression, NormalizerConfig()))
    if "+2" in expression or "=" in expression or expression.startswith("2*"):
        assert_reading(expression, read_expression(expression, NormalizerConfig()))


@pytest.mark.parametrize("year", [2023, 2024, 2026])
@pytest.mark.parametrize("month", range(1, 13))
def test_date_ranges_validate_real_calendar(year, month):
    last = calendar.monthrange(year, month)[1]
    n = Normalizer()
    source = f"ngày {last - 1}-{last} tháng {month} năm {year}"
    expected = "ngày " + read_integer(str(last - 1)) + " đến " + n.normalize(f"{last}/{month}/{year}")
    assert_reading(source, expected)
    invalid = f"ngày {last}-{last + 1} tháng {month} năm {year}"
    assert_reading(invalid, invalid)


@pytest.mark.parametrize("separator", ["/", "-", "."])
@pytest.mark.parametrize("gap", ["", " ", "\t", "\n"])
@pytest.mark.parametrize("wrapper", [False, True])
def test_full_date_range_punctuation_and_spacing(separator, gap, wrapper):
    sep = gap + separator + gap
    source = sep.join(("6", "8", "1976")) + gap + "–" + gap + sep.join(("6", "8", "2026"))
    expected = "từ sáu tháng tám năm một nghìn chín trăm bảy mươi sáu đến sáu tháng tám năm hai nghìn không trăm hai mươi sáu"
    if wrapper:
        source, expected = "(" + source + ")", "(" + expected + ")"
    assert_reading(source, expected)


def test_reading_policies_and_overrides_win():
    assert_reading("1.000 km²", "một phẩy không không không ki lô mét vuông", NormalizerConfig(number_locale="en"))
    assert_reading("1.000 km²", "một ngàn ki lô mét vuông", NormalizerConfig(thousand="ngàn"))
    assert_reading("$4,47/Thùng", "bốn phẩy bốn mươi bảy đô la Mỹ trên thùng",
                   NormalizerConfig(decimal_reading="cardinal", dollar_name="đô la Mỹ"))
    assert_reading("$44/Thùng", "bốn mươi tư đô la trên thùng hàng",
                   NormalizerConfig(unit_overrides={"thùng": "thùng hàng"}))
    assert_reading("5mW và 5MW", "năm mi li oát và năm mê ga oát")


@pytest.mark.parametrize("domains", [None, ()])
@pytest.mark.parametrize("decimal_reading", ["digits", "cardinal"])
def test_generated_prices_do_not_depend_on_reported_values(domains, decimal_reading):
    rng = random.Random(20260925)
    cfg = NormalizerConfig(decimal_reading=decimal_reading, **({"enabled_domains": domains} if domains is not None else {}))
    n = Normalizer(cfg)
    values = ["0", "1", "999999999", "-17", "0,05"]
    values += [f"{rng.randrange(1, 1000000)},{rng.randrange(100):02d}" for _ in range(40)]
    for value in values:
        for currency, spoken_currency in (("$", "đô la"), ("USD", "đô la Mỹ"), ("EUR", "ơ rô"), ("£", "bảng Anh")):
            for unit, spoken_unit in (("thùng", "thùng"), ("Thùng", "thùng"), ("gallon", "ga lông"), ("kg", "ki lô gam"), ("m²", "mét vuông")):
                gap = rng.choice(("", " ", "\t"))
                expected = read_number(value, cfg) + " " + spoken_currency + " trên " + spoken_unit
                for source in (f"{currency}{gap}{value}{gap}/{gap}{unit}", f"{value} {currency}{gap}/{gap}{unit}"):
                    actual = n.normalize(source)
                    assert actual == expected, source
                    assert n.normalize(actual) == actual


def test_generated_dates_do_not_depend_on_reported_years_or_days():
    rng = random.Random(81763)
    n = Normalizer()
    for _ in range(150):
        year = rng.randrange(1900, 2200)
        month = rng.randrange(1, 13)
        last = calendar.monthrange(year, month)[1]
        a, b = sorted(rng.sample(range(1, last + 1), 2))
        source = f"({a} / {month}/{year} - {b}/{month} / {year})"
        expected = "(từ " + n.normalize(f"{a}/{month}/{year}") + " đến " + n.normalize(f"{b}/{month}/{year}") + ")"
        assert n.normalize(source) == expected
        reversed_range = f"({b}/{month}/{year}-{a}/{month}/{year})"
        assert n.normalize(reversed_range) == reversed_range


def load_chunker():
    spec = importlib.util.spec_from_file_location("text_utils_regression", ROOT / "omnivoice/utils/text.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.chunk_text_punctuation


@pytest.mark.parametrize("name", ["Donald J. Trump", "Samuel A. Alito", "John F. Kennedy", "J. R. R. Tolkien", "J.R.R. Tolkien"])
def test_name_initials_are_not_sentence_boundaries(name):
    chunker = load_chunker()
    assert chunker(name + ". Tiếp theo.", chunk_len=len(name) - 2) == [name + ".", "Tiếp theo."]
    from scripts.text_normalize import split_text, chunk_words
    for size in (len(name) + 5, len(name) + 15, 60):
        chunks = split_text("Ông " + name + " phát biểu. Hết.", average_char=size, min_char=0, max_char=size + 4)
        assert any(name in chunk for chunk in chunks), chunks
        assert all(len(chunk) <= size + 4 for chunk in chunks)
    assert chunk_words('“' + name + '.”', len(name) + 4) == ['“' + name + '.”']


def test_chunker_preserves_real_sentence_breaks():
    chunker = load_chunker()
    assert chunker("Đáp án A. Đây là câu sau.", chunk_len=9) == ["Đáp án A.", "Đây là câu sau."]
    assert chunker("Dr. Smith đến. Hết.", chunk_len=5) == ["Dr. Smith đến.", "Hết."]


def test_original_csv_and_full_document():
    n = Normalizer()
    with (ROOT / "norm/danhgia/norm_errors_final.csv").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            source = row["vi_tri_loi"].strip()
            if source:
                spoken = n.normalize(source)
                assert not any(c.isdigit() for c in spoken), (row["case_id"], spoken)
                assert "chia" not in spoken and "mở ngoặc" not in spoken
                assert n.normalize(spoken) == spoken
    source = (ROOT / "norm/danhgia/danhgia_tts.txt").read_text(encoding="utf-8")
    result = n.normalize_with_trace(source)
    assert n.normalize(result.text) == result.text
    for span in result.spans:
        if span.kind in ("quantity", "calendar_range", "word_date_range", "domain_news_count_quantity"):
            assert span.status == "expanded", span
    ranges = [span for span in result.spans if span.kind == "calendar_range"]
    assert ranges and any("\n" in span.source for span in ranges)
    assert all("chia" not in span.spoken and "mở ngoặc" not in span.spoken for span in ranges)
