"""Acceptance tests for vietnamese_tts_normalizer 0.13.1: exchange rates, numbers before brackets,
number glosses, period words and code-style English words.

Source: user review of 2026-10-05 on danhgia_tts_06 ("nguyên text này đang normalize sai số tiền??",
"localStorage -> model đang ko đọc được"). Each rule is checked on sibling forms (GENERAL);
UNCHANGED keeps the 0.13.0 readings. Design: docs/vi_normalization_release_0_13_1.md.
"""

import pytest

from vietnamese_tts_normalizer import Normalizer, NormalizerConfig, __version__, normalize_vi_text
from vietnamese_tts_normalizer.lexicon import UNITS
from vietnamese_tts_normalizer.units import read_unit

N = normalize_vi_text

# (id, input, must contain, must NOT contain)
ACCEPTANCE = [
    ('A01', 'Ngân hàng Nhà nước công bố tỷ giá trung tâm USD tăng 18 đồng, đạt 25.338 đồng/USD.',
     ['đạt hai mươi lăm nghìn ba trăm ba mươi tám đồng trên đô la Mỹ.'], ['25.338', 'USD']),
    ('A02', 'trong biên độ 24.071,1-26.604,9 VND/USD, với Vietcombank niêm yết 26.060-26.470 VND/USD',
     ['trong biên độ từ hai mươi tư nghìn không trăm bảy mươi mốt phẩy một đến hai mươi sáu nghìn sáu trăm lẻ bốn '
      'phẩy chín đồng trên đô la Mỹ, với Vietcombank niêm yết từ hai mươi sáu nghìn không trăm sáu mươi đến hai mươi '
      'sáu nghìn bốn trăm bảy mươi đồng trên đô la Mỹ'], ['VND', '/']),
    ('A03', 'USD giao dịch quanh 26.250-26.280 VND/USD',
     ['đô la Mỹ giao dịch quanh hai mươi sáu nghìn hai trăm năm mươi đến hai mươi sáu nghìn hai trăm tám mươi đồng trên đô la Mỹ'],
     ['quanh từ']),
    ('A04', 'tại Vietcombank giao dịch 34.457,37-35.920,12 VND/GBP',
     ['giao dịch từ ba mươi tư nghìn bốn trăm năm mươi bảy phẩy ba mươi bảy đến ba mươi lăm nghìn chín trăm hai mươi '
      'phẩy mười hai đồng trên bảng Anh'], ['GBP']),
    ('A05', 'đã chính thức vận hành thương mại giai đoạn 1 (300 MW) vào cuối năm 2025',
     ['vận hành thương mại giai đoạn một (ba trăm mê ga oát) vào cuối năm hai nghìn không trăm hai mươi lăm'], ['MW', '1 (']),
    ('A06', 'giữ nguyên lãi suất trong cuộc họp thứ 05 liên tiếp',
     ['trong cuộc họp thứ năm liên tiếp'], ['không năm']),
    ('A07', 'lưu mã độc trong localStorage và IndexedDB',
     ['lưu mã độc trong local Storage và Indexed DB'], ['localStorage']),
]

GENERAL = [
    # Exchange rates: đồng per one unit of a foreign currency.
    ('G01', 'giá 26.000 đồng/USD, 25.338 VNĐ/USD, 27.500 đ/EUR',
     ['giá hai mươi sáu nghìn đồng trên đô la Mỹ, hai mươi lăm nghìn ba trăm ba mươi tám đồng trên đô la Mỹ, '
      'hai mươi bảy nghìn năm trăm đồng trên ơ rô'], []),
    ('G02', 'tỷ giá 170 đồng/yên và 3.600 VND/CNY',
     ['tỷ giá một trăm bảy mươi đồng trên yên và ba nghìn sáu trăm đồng trên nhân dân tệ'], []),
    ('G03', 'quy đổi 26.000 VND/1 USD', ['quy đổi hai mươi sáu nghìn đồng trên một đô la Mỹ'], []),
    # A number, then a bracket of its own.
    ('G04', 'giai đoạn 2 (200 MW), năm 2025 (300 MW)',
     ['giai đoạn hai (hai trăm mê ga oát), năm hai nghìn không trăm hai mươi lăm (ba trăm mê ga oát)'], []),
    ('G05', 'khoảng 5 (5 kg) gạo, đạt 2 (+3%)', ['khoảng năm (năm ki lô gam) gạo, đạt hai (cộng ba phần trăm)'], []),
    ('G06', 'theo Điều 5 (khoản 2)', ['theo Điều năm (khoản hai)'], []),
    ('G07', 'năm 2024 (tăng 5%)', ['năm hai nghìn không trăm hai mươi tư (tăng năm phần trăm)'], []),
    ('G08', 'giai đoạn 2 (2026-2030)',
     ['giai đoạn hai (từ hai nghìn không trăm hai mươi sáu đến hai nghìn không trăm ba mươi)'], []),
    ('G09', 'Chương 3 (Điều 10 đến Điều 15)', ['Chương ba (Điều mười đến Điều mười lăm)'], []),
    ('G10', 'lần 2 (ngày 5/10), mục 4 (b)', ['lần hai (ngày năm tháng mười), mục bốn (b)'], []),
    ('G11', 'nhóm 1 (gồm 3 người), top 10 (năm 2025)',
     ['nhóm một (gồm ba người), top mười (năm hai nghìn không trăm hai mươi lăm)'], []),
    # Administrative style: the number written again in words is read once.
    ('G12', 'trong thời hạn 05 (năm) ngày làm việc', ['trong thời hạn năm ngày làm việc'], ['ngoặc', 'năm năm']),
    ('G13', 'lập thành 02 (hai) bản, gồm 3 (ba) lần', ['lập thành hai bản, gồm ba lần'], []),
    ('G14', 'trong 15 (mười lăm) ngày, 30 (Ba mươi) ngày', ['trong mười lăm ngày, ba mươi ngày'], []),
    ('G15', 'số tiền 1.500.000 (một triệu năm trăm nghìn) đồng', ['số tiền một triệu năm trăm nghìn đồng'], []),
    ('G16', '24 (hai mươi tư) tháng, 105 (một trăm linh năm) hộ', ['hai mươi tư tháng, một trăm lẻ năm hộ'], []),
    ('G17', 'thời hạn 10 (năm), 15 (mười sáu) ngày', ['thời hạn mười (năm), mười lăm (mười sáu) ngày'], ['ngoặc']),
    # Period words: a month, quarter, day or ordinal.
    ('G18', 'thứ 01, thứ 04, quý 01, ngày 05', ['thứ nhất, thứ tư, quý một, ngày năm'], []),
    ('G19', 'tháng 05 vừa qua; vào tháng 4; từ tháng 4 đến tháng 6',
     ['tháng năm vừa qua; vào tháng tư; từ tháng tư đến tháng sáu'], []),
    ('G20', 'mỗi tháng 4 buổi, hằng tháng 4 lần', ['mỗi tháng bốn buổi, hằng tháng bốn lần'], ['tháng tư']),
    ('G24', 'sáng thứ 5 (3/4), thứ 04 và CN, từ thứ 02 đến CN',
     ['sáng thứ năm (ba tháng tư), thứ tư và chủ nhật, từ thứ hai đến chủ nhật'], ['trên bốn']),
    # Code-style English words.
    ('G21', 'dùng sessionStorage, getElementsByClassName, useState và onClick',
     ['dùng session Storage, get Elements By Class Name, use State và on Click'], []),
    # A bracket closed before a list comma is not part of the expression after it.
    ('G23', 'giai đoạn (2026-2030), 26.000 VND/1 USD',
     ['giai đoạn (hai nghìn không trăm hai mươi sáu đến hai nghìn không trăm ba mươi), hai mươi sáu nghìn đồng '
      'trên một đô la Mỹ'], []),
    # Approximators frame a range like "khoảng".
    ('G22', 'xung quanh 3-5 kg, xấp xỉ 20%-30%',
     ['xung quanh ba đến năm ki lô gam, xấp xỉ hai mươi phần trăm đến ba mươi phần trăm'], ['từ']),
]

# 0.13.0 readings that must not change.
UNCHANGED = [
    ('5 USD/VND', '5 USD/VND'),
    ('1,08 EUR/USD', '1,08 EUR/USD'),
    ('tỷ giá USD/VND', 'tỷ giá USD/VND'),
    ('tỷ giá VND/USD', 'tỷ giá VND/USD'),
    ('đồng/USD', 'đồng/USD'),
    ('25.338 VND/VND', '25.338 VND/VND'),
    ('2(3+4)', '2(3+4)'),
    ('5 (kgm/s)', '5 (kgm/s)'),
    ('5 (USD/m)', '5 (USD/m)'),
    ('tháng 13', 'tháng mười ba'),
    ('phòng số 05', 'phòng số không năm'),
    ('năm 05', 'năm không năm'),
    ('quý 4', 'quý bốn'),
    ('ngày 4', 'ngày bốn'),
    ('thứ 4', 'thứ tư'),
    ('iPhone', 'iPhone'),
    ('eBay', 'eBay'),
    ('YouTube', 'YouTube'),
    ('TikTok', 'TikTok'),
    ('MacBook', 'MacBook'),
    ('McDonald', 'McDonald'),
    ('kWh', 'kWh'),
    ('mAh', 'mAh'),
    ('mmHg', 'mmHg'),
    ('jQuery', 'jQuery'),
    ('macOS', 'mac OS'),
    ('getElementById', 'getElementById'),
    ('userID 123', 'user ID một trăm hai mươi ba'),
    ('OpenAI', 'Open AI'),
    ('dao động 3-5 kg', 'dao động từ ba đến năm ki lô gam'),
    ('khoảng 3.000–5.000 đơn vị', 'khoảng ba nghìn đến năm nghìn đơn vị'),
    ('giá xăng 26.569 đồng/lít', 'giá xăng hai mươi sáu nghìn năm trăm sáu mươi chín đồng trên lít'),
    ('100 USD/thùng', 'một trăm đô la Mỹ trên thùng'),
    ('(300 MW)', '(ba trăm mê ga oát)'),
    ('hạng 3 (sau Mỹ)', 'hạng ba (sau Mỹ)'),
]


def test_version():
    assert tuple(map(int, __version__.split("."))) >= (0, 13, 1)


@pytest.mark.parametrize("cid,text,expected,forbidden", ACCEPTANCE + GENERAL)
def test_acceptance(cid, text, expected, forbidden):
    out = N(text)
    assert any(e in out for e in expected), (cid, out)
    assert not any(f in out for f in forbidden), (cid, out)


@pytest.mark.parametrize("text,expected", UNCHANGED)
def test_unchanged_from_0_13_0(text, expected):
    assert N(text) == expected


@pytest.mark.parametrize("text", [c[1] for c in ACCEPTANCE + GENERAL] + [c[0] for c in UNCHANGED])
def test_two_pass_stable(text):
    once = N(text)
    assert N(once) == once


@pytest.mark.parametrize("text", [c[1] for c in ACCEPTANCE + GENERAL])
def test_trace_rebuilds_output(text):
    result = Normalizer().normalize_with_trace(text)
    rebuilt, end = [], 0
    for span in result.spans:
        assert result.source[span.start:span.end] == span.source and end <= span.start
        rebuilt.extend((result.source[end:span.start], span.spoken))
        end = span.end
    rebuilt.append(result.source[end:])
    assert "".join(rebuilt) == result.text


@pytest.mark.parametrize("unit,expected", [
    ("đồng/USD", "đồng trên đô la Mỹ"), ("VND/GBP", "đồng trên bảng Anh"), ("VNĐ/EUR", "đồng trên ơ rô"),
    ("đ/JPY", "đồng trên yên Nhật"), ("USD/VND", None), ("EUR/USD", None), ("VND/VND", None), ("VND/USD/kg", None),
])
def test_exchange_rate_units(unit, expected):
    """Only đồng per one foreign unit is read; other pairs depend on a quoting convention."""
    assert read_unit(unit, UNITS) == expected


@pytest.mark.parametrize("config,text,expected", [
    ({"thousand": "ngàn"}, "1.500.000 (một triệu năm trăm ngàn) đồng", "một triệu năm trăm ngàn đồng"),
    ({"thousand": "ngàn"}, "1.500.000 (một triệu năm trăm nghìn) đồng", "một triệu năm trăm ngàn đồng"),
    ({"zero_tens": "linh"}, "105 (một trăm lẻ năm) hộ", "một trăm linh năm hộ"),
    ({"thousand": "ngàn"}, "đạt 25.338 đồng/USD", "đạt hai mươi lăm ngàn ba trăm ba mươi tám đồng trên đô la Mỹ"),
    ({"range_prefix": ""}, "niêm yết 26.060-26.470 VND/USD",
     "niêm yết hai mươi sáu nghìn không trăm sáu mươi đến hai mươi sáu nghìn bốn trăm bảy mươi đồng trên đô la Mỹ"),
    ({"split_camel_case": False}, "localStorage", "localStorage"),
])
def test_configurations(config, text, expected):
    assert Normalizer(NormalizerConfig(**config)).normalize(text) == expected
