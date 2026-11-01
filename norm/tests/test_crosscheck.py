"""Independent structural counterexamples from the post-release cross-check."""

import importlib.util
from pathlib import Path

import pytest

from vietnamese_tts_normalizer import Normalizer, NormalizerConfig


@pytest.mark.parametrize("source, expected", [
    ("Giá $40–$50/thùng.", "Giá từ bốn mươi đến năm mươi đô la trên thùng."),
    ("Giá từ $40-$50/thùng.", "Giá từ bốn mươi đến năm mươi đô la trên thùng."),
    ("USD 12,5–USD 17,75/gallon", "từ mười hai phẩy năm đến mười bảy phẩy bảy mươi lăm đô la Mỹ trên ga lông"),
    ("€5–EUR7/kg", "từ năm đến bảy ơ rô trên ki lô gam"),
    ("6 / 8\n/2026", "sáu tháng tám năm hai nghìn không trăm hai mươi sáu"),
    ("6/8/2026=1", "sáu chia tám chia hai nghìn không trăm hai mươi sáu bằng một"),
    ("6/8\n/2026=1", "sáu chia tám chia hai nghìn không trăm hai mươi sáu bằng một"),
    ("tính (6/8\n/2026)", "tính mở ngoặc sáu chia tám chia hai nghìn không trăm hai mươi sáu đóng ngoặc"),
    ("(6/8\n/2026)=1", "mở ngoặc sáu chia tám chia hai nghìn không trăm hai mươi sáu đóng ngoặc bằng một"),
    ("tính 6/2 - 3/1", "tính sáu chia hai trừ ba chia một"),
    ("tính 6/2-3/1", "tính sáu chia hai trừ ba chia một"),
    ("biểu thức: 9/3 - 4/2", "biểu thức: chín chia ba trừ bốn chia hai"),
    ("Ngày 14-15\ntháng 9", "Ngày mười bốn đến mười lăm tháng chín"),
    ("Ngày 14-15 tháng\n9", "Ngày mười bốn đến mười lăm tháng chín"),
    ("tính 2+3 kg/(m*s)", "tính hai cộng ba ki lô gam trên mở ngoặc mét nhân giây đóng ngoặc"),
    ("2=3 kg/(m*s)", "hai bằng ba ki lô gam trên mở ngoặc mét nhân giây đóng ngoặc"),
])
def test_crosscheck_readings(source, expected):
    n = Normalizer()
    r = n.normalize_with_trace(source)
    assert r.text == expected
    assert n.normalize(expected) == expected
    assert all(r.source[s.start:s.end] == s.source for s in r.spans)


@pytest.mark.parametrize("source", [
    "$44/thùng ^ 2", "$44/thùng ^ -2", "$44/thùng ^ 0",
    "$50–$40/thùng", "$40–€50/thùng", "USD40–GBP50/kg",
    "ngày 28-29 tháng\n2 năm 2023", "[Giá $40–$50/thùng]",
])
def test_crosscheck_preservation(source):
    assert Normalizer().normalize(source) == source


@pytest.mark.parametrize("left_currency,right_currency,spoken", [
    ("$", "$", "đô la"), ("USD", "USD", "đô la Mỹ"), ("$", "USD", "đô la"),
    ("EUR", "€", "ơ rô"), ("£", "GBP", "bảng Anh"), ("VND", "đ", "đồng"),
])
@pytest.mark.parametrize("gap, dash", [("", "-"), (" ", "–"), ("\t", "-")])
def test_repeated_currency_is_not_a_different_range(left_currency, right_currency, spoken, gap, dash):
    n = Normalizer(NormalizerConfig(enabled_domains=()))
    for a, b in [(0, 8), (17, 32), (90, 108), (1234, 7654)]:
        source = f"{left_currency}{gap}{a}{gap}{dash}{gap}{right_currency}{gap}{b}/Thùng"
        equivalent = f"{a}–{b} {left_currency}/thùng"
        assert n.normalize(source) == n.normalize(equivalent)
        assert spoken + " trên thùng" in n.normalize(source)


@pytest.mark.parametrize("gaps", [("\n", ""), ("", "\n"), (" \r\n ", " "), ("\t", "\n")])
@pytest.mark.parametrize("wrapped", [False, True])
def test_line_wrapped_dates_never_lose_components(gaps, wrapped):
    n = Normalizer()
    for day, month, year in [(6, 8, 2026), (29, 2, 2024), (31, 12, 1999), (1, 1, 2100)]:
        a, b = gaps
        source = f"{day}{a}/{month}{b}/{year}"
        expected = n.normalize(f"{day}/{month}/{year}")
        if wrapped:
            source, expected = "(" + source + ")", "(" + expected + ")"
        assert n.normalize(source) == expected


def _chunker():
    path = Path(__file__).resolve().parents[2] / "omnivoice/utils/text.py"
    spec = importlib.util.spec_from_file_location("text_crosscheck", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.chunk_text_punctuation


@pytest.mark.parametrize("source, expected", [
    ("Donald J.\nTrump nói. Hết.", ["Donald J.\nTrump nói.", "Hết."]),
    ("đọc J. K. Rowling hôm nay.", ["đọc J. K. Rowling hôm nay."]),
    ("Chọn A. Đây là câu sau.", ["Chọn A.", "Đây là câu sau."]),
    ("Mục A. Đây là câu sau.", ["Mục A.", "Đây là câu sau."]),
    ("Phần B. Nội dung tiếp.", ["Phần B.", "Nội dung tiếp."]),
])
def test_names_and_list_markers_have_different_boundaries(source, expected):
    assert _chunker()(source, 12) == expected
