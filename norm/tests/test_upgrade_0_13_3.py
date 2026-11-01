"""Acceptance tests for vietnamese_tts_normalizer 0.13.3: kilolitres and units after "mỗi", C-suite titles,
the letter T after a number, place names written in English, counts with English thousands.

Source: user review of 2026-10-05 on danhgia_tts_06 ("$400 mỗi kilolitre, xuống $1.100 mỗi kl -> kl đang ko
biết đọc", "CEO -> xi i ô", "mô-đun 1,6T đang ko hiểu ngữ cảnh", "Moscow -> Mát cơ va"); "1,850 điểm" was
read as a decimal in the same file. Design: docs/vi_normalization_release_0_13_3.md.
"""

import pytest

from vietnamese_tts_normalizer import Normalizer, NormalizerConfig, __version__, normalize_vi_text
from vietnamese_tts_normalizer import places

N = normalize_vi_text

# (id, input, must contain, must NOT contain)
ACCEPTANCE = [
    ('A01', 'giảm giá cho hãng hàng không quốc tế $400 mỗi kilolitre, xuống $1.100 mỗi kl, tương đương giảm 27%',
     ['bốn trăm đô la mỗi ki lô lít, xuống một nghìn một trăm đô la mỗi ki lô lít, tương đương giảm hai mươi bảy phần trăm'],
     ['kl', 'kilolitre']),
    ('A02', 'Hôm nay tại Đài Bắc, CEO của công ty chip AI NVIDIA', ['Hôm nay tại Đài Bắc, xi i ô của công ty chip AI NVIDIA'],
     ['C E O']),
    ('A03', 'các công nghệ quang như CPO, mô-đun 1,6T và hệ thống CoDoClaw',
     ['các công nghệ quang như C P O, mô-đun một phẩy sáu tê và hệ thống CoDoClaw'], ['tét la']),
    ('A04', 'Ngày 1 tháng 6 tại Moscow, Tư lệnh Hàng không Vận tải Quân sự Nga',
     ['Ngày một tháng sáu tại Mát cơ va, Tư lệnh Hàng không Vận tải Quân sự Nga'], ['Moscow']),
    ('A05', 'VN-Index đang tích lũy dưới kháng cự quanh 1,850 điểm và có thể điều chỉnh về 1,800 điểm hoặc sâu hơn '
            '1,750-1,800 điểm; VN30 có hỗ trợ quanh 1,975 điểm',
     ['quanh một nghìn tám trăm năm mươi điểm và có thể điều chỉnh về một nghìn tám trăm điểm hoặc sâu hơn một nghìn '
      'bảy trăm năm mươi đến một nghìn tám trăm điểm; vê nờ ba mươi có hỗ trợ quanh một nghìn chín trăm bảy mươi lăm điểm'],
     ['phẩy']),
]

GENERAL = [
    # Units: kilolitres, English litres, a unit after "mỗi" without a number.
    ('G01', '5 kl xăng, 10 kL dầu, 2 litres nước', ['năm ki lô lít xăng, mười ki lô lít dầu, hai lít nước'], []),
    ('G02', 'giá 50.000 đồng mỗi kg, 3 USD mỗi km, 1 triệu mỗi ha, mỗi MW',
     ['giá năm mươi nghìn đồng mỗi ki lô gam, ba đô la Mỹ mỗi ki lô mét, một triệu mỗi héc ta, mỗi mê ga oát'], []),
    # Company titles.
    ('G03', 'các CEO, CFO và CTO; COO, CMO', ['các xi i ô, xi ép ô và xi ti ô; xi ô ô, xi em ô'], []),
    # T after a number: tera by default, tesla beside a magnetic field, tấn beside a truck.
    ('G04', 'mô-đun 800G và 1.6T, dầu nhớt 4T', ['mô-đun tám trăm gờ và một phẩy sáu tê, dầu nhớt bốn tê'], []),
    ('G05', 'máy MRI 3T, nam châm 1,5T, từ trường 2T', ['ba tét la', 'một phẩy năm tét la', 'hai tét la'], []),
    ('G06', 'xe tải 5T, trọng tải 2,5T', ['xe tải năm tấn, trọng tải hai phẩy năm tấn'], []),
    # Place names written in English.
    ('G07', 'thăm Moscow và Kyiv', ['thăm Mát cơ va và Ki ép'], []),
    ('G08', 'tại Washington, London, Paris và Berlin', ['tại Oa sinh tơn, Luân Đôn, Pa ri và Béc lin'], []),
    ('G09', 'hội nghị GTC Taipei, nhà máy ở Changzhou, tỉnh Giang Tô', ['G T C Đài Bắc', 'Thường Châu, tỉnh Giang Tô'], []),
    ('G10', 'bay từ Tokyo tới Seoul, Singapore và Bangkok', ['bay từ Tô ky ô tới Xơ un, Xin ga po và Băng Cốc'], []),
    ('G11', 'giá 5 SGD', ['năm đô la Xin ga po'], ['Singapore']),
    # Counts with English thousands.
    ('G12', 'đóng cửa ở 1,845 điểm, tăng 1,250 người, 2,500 lượt', ['một nghìn tám trăm bốn mươi lăm điểm',
     'một nghìn hai trăm năm mươi người', 'hai nghìn năm trăm lượt'], ['phẩy']),
]

# Readings that stay as in 0.13.2.
UNCHANGED = [
    ('1,5 điểm', 'một phẩy năm điểm'),
    ('8,25 điểm', 'tám phẩy hai mươi lăm điểm'),
    ('1,845 km', 'một phẩy tám bốn năm ki lô mét'),
    ('1.850 điểm', 'một nghìn tám trăm năm mươi điểm'),
    ('3-5\nTOEIC', '3-5\nT O E I C'),
    ('mỗi người', 'mỗi người'),
    ('mỗi tạ', 'mỗi tạ'),
    ('Linux', 'Linux'),
    ('Hàng Châu', 'Hàng Châu'),
    ('Mát-xcơ-va', 'Mát cơ va'),
    ('MOSCOW', 'MOSCOW'),
    ('AI', 'AI'),
    ('G D P', 'G D P'),
]


def test_version():
    assert tuple(map(int, __version__.split("."))) >= (0, 13, 3)


@pytest.mark.parametrize("cid,text,expected,forbidden", ACCEPTANCE + GENERAL)
def test_acceptance(cid, text, expected, forbidden):
    out = N(text)
    assert all(e in out for e in expected), (cid, out)
    assert not any(f in out for f in forbidden), (cid, out)


@pytest.mark.parametrize("text,expected", UNCHANGED)
def test_unchanged_from_0_13_2(text, expected):
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


@pytest.mark.parametrize("name,reading", sorted(places.EXONYMS.items()))
def test_place_readings_are_fixed_points(name, reading):
    """A place name is read once: its reading is plain Vietnamese text that a second pass keeps."""
    assert N(name) == reading
    assert N(reading) == reading


def test_place_names_follow_the_abbreviation_policy():
    assert Normalizer(NormalizerConfig(abbreviation_policy="none")).normalize("tại Moscow") == "tại Moscow"
