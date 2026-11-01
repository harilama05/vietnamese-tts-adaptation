"""Acceptance tests for vietnamese_tts_normalizer 0.13.2: a two-digit decimal fraction is read as a number.

Source: user review of 2026-10-05 ("34.457,37-35.920,12 chỗ 37 -> ba bảy, tôi nghĩ là nên kiểu ba mươi
bảy, còn 12 thì là mười hai"). The rule covers every decimal (money, percentages, measures, plain
numbers); a leading zero and longer fractions stay digit by digit. Design: docs/vi_normalization_release_0_13_2.md.
"""

import pytest

from vietnamese_tts_normalizer import Normalizer, NormalizerConfig, __version__, normalize_vi_text
from vietnamese_tts_normalizer.numbers import read_number

N = normalize_vi_text

# (id, input, must contain, must NOT contain)
ACCEPTANCE = [
    ('A01', 'tại Vietcombank giao dịch 34.457,37-35.920,12 VND/GBP',
     ['giao dịch từ ba mươi tư nghìn bốn trăm năm mươi bảy phẩy ba mươi bảy đến ba mươi lăm nghìn chín trăm hai mươi '
      'phẩy mười hai đồng trên bảng Anh'], ['phẩy ba bảy', 'phẩy một hai']),
]

GENERAL = [
    ('G01', 'lãi suất 3,5%-3,75%', ['lãi suất từ ba phẩy năm phần trăm đến ba phẩy bảy mươi lăm phần trăm'], ['bảy năm']),
    ('G02', 'cao 1,75 m, nặng 62,45 kg', ['cao một phẩy bảy mươi lăm mét, nặng sáu mươi hai phẩy bốn mươi lăm ki lô gam'], []),
    ('G03', 'giá 2,50 USD và $12.50', ['giá hai phẩy năm mươi đô la Mỹ và mười hai phẩy năm mươi đô la'], ['năm không']),
    ('G04', 'đạt 36,25 tỷ đồng', ['đạt ba mươi sáu phẩy hai mươi lăm tỷ đồng'], []),
    ('G05', 'tốc độ khung hình 59,94fps', ['năm mươi chín phẩy chín mươi tư khung hình trên giây'], []),
    ('G06', 'tăng 0,25 điểm %', ['tăng không phẩy hai mươi lăm điểm phần trăm'], []),
    ('G07', 'số pi xấp xỉ 3,14', ['số pi xấp xỉ ba phẩy mười bốn'], []),
    ('G08', 'tỷ lệ 1,10 và 24,24', ['tỷ lệ một phẩy mười và hai mươi tư phẩy hai mươi tư'], []),
    ('G09', 'giá 1.250,75 USD/ounce', ['giá một nghìn hai trăm năm mươi phẩy bảy mươi lăm đô la Mỹ trên ao xơ'], []),
]

# Readings that stay digit by digit (as in 0.13.1).
UNCHANGED = [
    ('0,05%', 'không phẩy không năm phần trăm'),
    ('3,05 kg', 'ba phẩy không năm ki lô gam'),
    ('3,00 kg', 'ba phẩy không không ki lô gam'),
    ('3,14159', 'ba phẩy một bốn một năm chín'),
    ('1,125 tấn', 'một phẩy một hai năm tấn'),
    ('62,5 triệu USD', 'sáu mươi hai phẩy năm triệu đô la Mỹ'),
    ('0,8%', 'không phẩy tám phần trăm'),
    ('dầu DO 0,05S-II', 'dầu đê ô không phẩy không năm ét hai'),
    ('PM2.5', 'pê mờ hai chấm năm'),
    ('phiên bản 1.12', 'phiên bản một chấm mười hai'),
    ('12:30', 'mười hai giờ ba mươi phút'),
]


def test_version():
    assert tuple(map(int, __version__.split("."))) >= (0, 13, 2)


@pytest.mark.parametrize("cid,text,expected,forbidden", ACCEPTANCE + GENERAL)
def test_acceptance(cid, text, expected, forbidden):
    out = N(text)
    assert any(e in out for e in expected), (cid, out)
    assert not any(f in out for f in forbidden), (cid, out)


@pytest.mark.parametrize("text,expected", UNCHANGED)
def test_unchanged_from_0_13_1(text, expected):
    assert N(text) == expected


@pytest.mark.parametrize("text", [c[1] for c in ACCEPTANCE + GENERAL] + [c[0] for c in UNCHANGED])
def test_two_pass_stable(text):
    once = N(text)
    assert N(once) == once


@pytest.mark.parametrize("value,auto,digits,cardinal", [
    ("3,75", "ba phẩy bảy mươi lăm", "ba phẩy bảy năm", "ba phẩy bảy mươi lăm"),
    ("3,10", "ba phẩy mười", "ba phẩy một không", "ba phẩy mười"),
    ("3,05", "ba phẩy không năm", "ba phẩy không năm", "ba phẩy không năm"),
    ("3,5", "ba phẩy năm", "ba phẩy năm", "ba phẩy năm"),
    ("3,125", "ba phẩy một hai năm", "ba phẩy một hai năm", "ba phẩy một trăm hai mươi lăm"),
    ("-0,25", "âm không phẩy hai mươi lăm", "âm không phẩy hai năm", "âm không phẩy hai mươi lăm"),
])
def test_decimal_reading_modes(value, auto, digits, cardinal):
    """auto (default): two digits without a leading zero are a number; digits and cardinal as before."""
    vi = NormalizerConfig(number_locale="vi")
    assert read_number(value, vi) == auto
    assert read_number(value, NormalizerConfig(number_locale="vi", decimal_reading="digits")) == digits
    assert read_number(value, NormalizerConfig(number_locale="vi", decimal_reading="cardinal")) == cardinal


def test_digits_mode_keeps_the_0_13_1_reading():
    n = Normalizer(NormalizerConfig(decimal_reading="digits"))
    assert n.normalize("giao dịch 34.457,37-35.920,12 VND/GBP") == (
        "giao dịch từ ba mươi tư nghìn bốn trăm năm mươi bảy phẩy ba bảy đến ba mươi lăm nghìn chín trăm hai mươi "
        "phẩy một hai đồng trên bảng Anh")
