"""Acceptance tests for vietnamese_tts_normalizer 0.13.0: codes, fuel grades and spoken domain names.

Source: user review of 2026-10-02 ("TEI-TF6000" -> "T E I T F sáu ngàn", "xăng E5RON 92" ->
"xăng e năm ron chín hai", "chinhphu.vn/TG" -> "chính phủ chấm vi en"). Each rule is checked on
sibling forms (GENERAL); UNCHANGED keeps the 0.12.0 readings of URLs, e-mails, other codes.
Design: docs/vi_normalization_release_0_13_0.md.
"""

import pytest

from vietnamese_tts_normalizer import Normalizer, NormalizerConfig, __version__, normalize_vi_text
from vietnamese_tts_normalizer import web

N = normalize_vi_text

# (id, input, must contain, must NOT contain)
ACCEPTANCE = [
    ('A01', 'Động cơ phản lực TEI-TF6000 đã hoàn thành thử nghiệm',
     ['Động cơ phản lực T E I T F sáu nghìn đã hoàn thành thử nghiệm'], ['TF sáu', 'không không không']),
    ('A02', 'giá bán tối đa là: xăng E5RON 92 không cao hơn 26.569 đồng/lít',
     ['giá bán tối đa là: xăng e năm ron chín hai không cao hơn hai mươi sáu nghìn năm trăm sáu mươi chín đồng trên lít'], ['R O N', 'chín mươi hai']),
    ('A03', 'phát biểu tại Diễn đàn - Ảnh: chinhphu.vn/TG',
     ['phát biểu tại Diễn đàn - Ảnh: chính phủ chấm vi en'], ['chinhphu', 'TG', 'T G']),
]

GENERAL = [
    ('G01', 'còn TEI-TF10000 hướng tới hoạt động',
     ['còn T E I T F mười nghìn hướng tới hoạt động'], []),
    ('G02', 'TF6000, MQ-9, QH15',
     ['T F sáu nghìn, M Q chín, Q H mười lăm'], []),
    ('G03', 'AB-1234, Su-30MK2, MH370',
     ['A B một hai ba bốn, Su ba mươi M K hai, M H ba trăm bảy mươi'], []),
    ('G04', 'XPS9300 và RTX4090',
     ['X P S chín ba không không và R T X bốn không chín không'], []),
    ('G05', 'A350-900',
     ['a ba trăm năm mươi chín trăm'], []),
    ('G06', 'xăng E10RON 95 không cao hơn 27.189 đồng/lít',
     ['xăng e mười ron chín lăm không cao hơn hai mươi bảy nghìn một trăm tám mươi chín đồng trên lít'], []),
    ('G07', 'xăng RON 95-III và RON 97',
     ['xăng ron chín lăm ba và ron chín bảy'], ['I I I', 'chín mươi']),
    ('G08', 'xăng RON95-III',
     ['xăng ron chín lăm ba'], []),
    ('G09', 'xăng E5 RON92-II',
     ['xăng e năm ron chín hai hai'], []),
    ('G10', 'xăng A92, xăng A95',
     ['xăng a chín hai, xăng a chín lăm'], []),
    ('G11', 'dầu DO 0,05S-II và dầu diesel 0,001S-V',
     ['dầu đê ô không phẩy không năm ét hai và dầu diesel không phẩy không không một ét năm'], ['0,05S', 'S-II']),
    ('G12', 'dầu FO 3,5S',
     ['dầu ép ô ba phẩy năm ét'], []),
    ('G13', 'Theo baochinhphu.vn, giá xăng giảm',
     ['Theo báo chính phủ chấm vi en, giá xăng giảm'], ['baochinhphu']),
    ('G14', 'Nguồn: dantri.com.vn',
     ['Nguồn: dân trí chấm com chấm vi en'], []),
    ('G15', 'theo tuoitre.vn và thanhnien.vn',
     ['theo tuổi trẻ chấm vi en và thanh niên chấm vi en'], []),
    ('G16', 'trên vnexpress.net',
     ['trên vi en express chấm nét'], []),
    ('G17', 'nộp hồ sơ tại dichvucong.gov.vn',
     ['nộp hồ sơ tại dịch vụ công chấm gov chấm vi en'], []),
    ('G18', 'tra cứu ở thuvienphapluat.vn',
     ['tra cứu ở thư viện pháp luật chấm vi en'], []),
    ('G19', 'kenh14.vn, www.chinhphu.vn',
     ['kênh mười bốn chấm vi en, vê kép vê kép vê kép chấm chính phủ chấm vi en'], []),
    ('G20', 'Ảnh: nhandan.vn/ABC',
     ['Ảnh: nhân dân chấm vi en'], ['ABC', 'A B C']),
    ('G21', 'cổng quangninh.gov.vn',
     ['cổng quảng ninh chấm gov chấm vi en'], []),
    ('G22', 'Theo google.com và youtube.com',
     ['Theo google chấm com và youtube chấm com'], []),
    ('G23', 'xăng thường được bán ở mức 5.150 riel/lít',
     ['xăng thường được bán ở mức năm nghìn một trăm năm mươi riel trên lít'], ['5.150', 'riel/']),
    ('G24', 'mức giảm khoảng 14.000–17.000 feet trong chưa đầy hai phút',
     ['mức giảm khoảng mười bốn nghìn đến mười bảy nghìn phít trong chưa đầy hai phút'], ['14.000']),
    ('G25', 'sản lượng khoảng 3.000–5.000 đơn vị mỗi tháng',
     ['sản lượng khoảng ba nghìn đến năm nghìn đơn vị mỗi tháng'], []),
    ('G26', 'Các nội dung đáng chú ý gồm 5G/6G; hệ thống cảnh báo',
     ['Các nội dung đáng chú ý gồm năm gờ, sáu gờ; hệ thống cảnh báo'], ['5G']),
    ('G27', 'điện thoại 4G/LTE',
     ['điện thoại bốn gờ, L T E'], ['bốnG', '4G']),
    ('G28', 'mức lương 14.000–17.000 baht/tháng',
     ['mức lương từ mười bốn nghìn đến mười bảy nghìn bạt trên tháng'], []),
    ('G29', 'giá 100 yên, 5 kíp',
     ['giá một trăm yên, năm kíp'], []),
]

# 0.12.0 readings that must not change.
UNCHANGED = [
    ('https://chinhphu.vn/abc', 'https://chinhphu.vn/abc'),
    ('abc@gmail.com', 'abc@gmail.com'),
    ('example.vn/12/3', 'example.vn/12/3'),
    ('giá A95', 'giá a chín mươi lăm'),
    ('RTX4090', 'R T X bốn không chín không'),
    ('S-400', 'ét bốn trăm'),
    ('G7', 'gờ bảy'),
    ('F-16', 'ép mười sáu'),
    ('E10', 'e mười'),
    ('A320neo', 'a ba trăm hai mươi neo'),
    ('Tòa án quốc tế về Luật Biển (ITLOS)', 'Tòa án quốc tế về Luật Biển (ITLOS)'),
    ('Tổ chức Y tế Thế giới (WHO)', 'Tổ chức Y tế Thế giới (W H O)'),
    ('VN-215', 'V N hai một năm'),
    ('CVE-2026-65660', 'C V E hai không hai sáu sáu năm sáu sáu không'),
    ('PM2.5', 'pê mờ hai chấm năm'),
    ('RTX 4090', 'R T X bốn nghìn không trăm chín mươi'),
    ('căn hộ 2PN', 'căn hộ hai phòng ngủ'),
    ('Mát-xcơ-va', 'Mát cơ va'),
    ('Bộ trưởng VH-TT-DL', 'Bộ trưởng Văn hóa, Thể thao và Du lịch'),
    ('USD/VND', 'USD/VND'),
    ('KM/H', 'KM/H'),
    ('điện thoại 0912345678', 'điện thoại không chín một hai ba bốn năm sáu bảy tám'),
]


def test_version():
    assert tuple(map(int, __version__.split("."))) >= (0, 13, 0)


@pytest.mark.parametrize("cid,text,expected,forbidden", ACCEPTANCE + GENERAL)
def test_acceptance(cid, text, expected, forbidden):
    out = N(text)
    assert any(e in out for e in expected), (cid, out)
    assert not any(f in out for f in forbidden), (cid, out)


@pytest.mark.parametrize("text,expected", UNCHANGED)
def test_unchanged_from_0_12_0(text, expected):
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


def test_thousand_word_follows_the_config():
    assert N("TEI-TF6000", NormalizerConfig(thousand="ngàn")) == "T E I T F sáu ngàn"


@pytest.mark.parametrize("mode,expected", [
    ("domain", "Ảnh: chính phủ chấm vi en"),
    ("preserve", "Ảnh: chinhphu.vn/TG"),
    ("speak", "Ảnh: chinhphu chấm vn xuyệt tg"),
])
def test_link_modes(mode, expected):
    assert N("Ảnh: chinhphu.vn/TG", NormalizerConfig(link_mode=mode)) == expected


@pytest.mark.parametrize("raw", ["https://chinhphu.vn/abc", "abc@gmail.com", "example.vn/12/3", "www.example.com/a?b=1",
                                 "chinhphu.vn/Tin", "[chinhphu.vn]", "`chinhphu.vn`"])
def test_urls_paths_mails_and_code_stay_protected(raw):
    assert N(raw) == raw


@pytest.mark.parametrize("label,expected", [
    ("chinhphu", "chính phủ"), ("baochinhphu", "báo chính phủ"), ("dichvucong", "dịch vụ công"), ("quangninh", "quảng ninh"),
    ("thuvienphapluat", "thư viện pháp luật"), ("tinhte", "tinh te"), ("kenh14", "kênh mười bốn"), ("vtv", "V T V"),
    ("google", "google"), ("youtube", "youtube"), ("openai", "openai"), ("shopee", "shopee"),
])
def test_domain_labels(label, expected):
    """Vietnamese words get their diacritics back; English names are never cut into Vietnamese syllables."""
    assert web.read_label(label) == expected
