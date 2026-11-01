"""0.10.0: common abbreviations + letter spelling, inferred number grouping,
dates/ranges, symbols and identifiers from the danhgia 02/03 evaluations."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import random
import re
import subprocess
import sys

import pytest

from vietnamese_tts_normalizer import COMMON_ABBREVIATIONS, Normalizer, NormalizerConfig
from vietnamese_tts_normalizer.acronyms import SAY, is_spell_candidate
from vietnamese_tts_normalizer.lexicon import LETTER_NAMES
from vietnamese_tts_normalizer.numbers import infer_ambiguous_number

ROOT = Path(__file__).resolve().parents[2]
LEGACY = NormalizerConfig(abbreviation_policy="extended", acronym_mode="preserve", ambiguous_number="preserve")

ACCEPTANCE = [
    # (nguồn, đầu vào, đầu ra bắt buộc) — kiểm chứng trên prototype 2026-09-30
    ('02 text_04_chunk_02', 'từ năm học 2027-28 và',
     'từ năm học hai nghìn không trăm hai mươi bảy đến hai nghìn không trăm hai mươi tám và'),
    ('02 text_06_chunk_01', 'Hiệp định Hành động Chung 2026-2030 nhằm',
     'Hiệp định Hành động Chung từ hai nghìn không trăm hai mươi sáu đến hai nghìn không trăm ba mươi nhằm'),
    ('02 text_06_chunk_04', 'Chủ tịch Tập đoàn SK Chey Tae-won và Chủ tịch Tập đoàn LG Koo Kwang-mo',
     'Chủ tịch Tập đoàn SK Chey Tae won và Chủ tịch Tập đoàn LG Koo Kwang mo'),
    ('02 text_06_chunk_05', 'mong đợi chuyến thăm của BTS vào năm 2027.',
     'mong đợi chuyến thăm của B T S vào năm hai nghìn không trăm hai mươi bảy.'),
    ('02 text_11_chunk_03a', 'Màn hình chính là LTPO AMOLED 2K, biến thiên 1-120Hz, độ sáng đỉnh 4.000 nits;',
     'Màn hình chính là L T P O AMOLED hai ca, biến thiên từ một đến một trăm hai mươi héc, độ sáng đỉnh bốn nghìn nít;'),
    ('02 text_11_chunk_03b', 'cụm camera 200MP + 200MP + 50MP, pin 7.000mAh và 8.500mAh, sạc 100W có dây',
     'cụm camera hai trăm mê ga pích xeo cộng hai trăm mê ga pích xeo cộng năm mươi mê ga pích xeo, pin bảy nghìn mi li am pe giờ và tám nghìn năm trăm mi li am pe giờ, sạc một trăm oát có dây'),
    ('02 text_11_chunk_04', 'Giá khởi điểm 5.999 nhân dân tệ ($894) cho 18 Pro và 6.999 nhân dân tệ ($1.043) cho 18 Pro Max;',
     'Giá khởi điểm năm nghìn chín trăm chín mươi chín nhân dân tệ (tám trăm chín mươi tư đô la) cho mười tám Pro và sáu nghìn chín trăm chín mươi chín nhân dân tệ (một nghìn không trăm bốn mươi ba đô la) cho mười tám Pro Max;'),
    ('02 text_13_chunk_02', 'với các ngày cụ thể là 25/9, 16/10, 16/11 và 16/12.',
     'với các ngày cụ thể là hai mươi lăm tháng chín, mười sáu tháng mười, mười sáu tháng mười một và mười sáu tháng mười hai.'),
    ('03 text_04_chunk_01', 'tại Washington ngày 24-25. Hai bên trao đổi',
     'tại Oa sinh tơn ngày hai mươi tư đến hai mươi lăm. Hai bên trao đổi'),
    ('03 text_06_chunk_03', 'Về hội nghị G20 tại Miami. Ông Peskov nói Nga sẽ tích cực tham gia công việc của G20. Ông',
     'Về hội nghị gờ hai mươi tại Miami. Ông Peskov nói Nga sẽ tích cực tham gia công việc của gờ hai mươi. Ông'),
    ('03 text_09_chunk_01', 'giao dịch quanh 4.265 USD một ounce trong bối cảnh',
     'giao dịch quanh bốn nghìn hai trăm sáu mươi lăm đô la Mỹ một ounce trong bối cảnh'),
    ('03 text_12_chunk_02', '(40% đến 2026, 60% 2027–2029, 80% từ 2030)',
     '(bốn mươi phần trăm đến hai nghìn không trăm hai mươi sáu, sáu mươi phần trăm từ hai nghìn không trăm hai mươi bảy đến hai nghìn không trăm hai mươi chín, tám mươi phần trăm từ hai nghìn không trăm ba mươi)'),
    ('03 text_14_chunk_01', 'Lỗ hổng Microsoft SharePoint CVE-2026-65660 đang bị khai thác',
     'Lỗ hổng Microsoft SharePoint C V E hai không hai sáu sáu năm sáu sáu không đang bị khai thác'),
    ('03 text_15_chunk_03', 'vào hôm thứ Sáu (25/9), việc cắt giảm',
     'vào hôm thứ Sáu (hai mươi lăm tháng chín), việc cắt giảm'),
    ('03 text_15_chunk_06', 'đưa tin vào thứ Bảy (26/9) rằng',
     'đưa tin vào thứ Bảy (hai mươi sáu tháng chín) rằng'),
    ('03 text_16_chunk_07', 'Tới tối 27.9, phần mềm này',
     'Tới tối hai mươi bảy tháng chín, phần mềm này'),
    ('extra 02', 'vi phạm có thể bị phạt tới 1.000 euro.',
     'vi phạm có thể bị phạt tới một nghìn ơ rô.'),
    ('extra 02', 'có 34.000 lớp học mà hơn 30% học sinh',
     'có ba mươi tư nghìn lớp học mà hơn ba mươi phần trăm học sinh'),
    ('extra 02', 'Mức trợ cấp bổ sung là 60.000 riel cho mỗi hộ và 5.000 riel',
     'Mức trợ cấp bổ sung là sáu mươi nghìn riel cho mỗi hộ và năm nghìn riel'),
    ('extra 02', 'hỗ trợ lẫn nhau tổ chức APEC 2026 và G20, và sau',
     'hỗ trợ lẫn nhau tổ chức a pếch hai nghìn không trăm hai mươi sáu và gờ hai mươi, và sau'),
    ('extra 02', 'robot đi bốn chân RAIBO2 đã chạy 42,195 km',
     'robot đi bốn chân RAIBO hai đã chạy bốn mươi hai phẩy một chín năm ki lô mét'),
    ('extra 03', 'lợi suất đạt 3,085% vào sáng 28',
     'lợi suất đạt ba phẩy không tám năm phần trăm vào sáng hai mươi tám'),
    ('extra 03', 'triển khai 26 vệ tinh Starlink V3 sau nâng cấp',
     'triển khai hai mươi sáu vệ tinh Starlink vê ba sau nâng cấp'),
    ('extra 03', 'giữa đường trung bình động 50 ngày ở 4.350 USD và 100 ngày ở 4.400 USD.',
     'giữa đường trung bình động năm mươi ngày ở bốn nghìn ba trăm năm mươi đô la Mỹ và một trăm ngày ở bốn nghìn bốn trăm đô la Mỹ.'),
    ('extra 03', 'nhóm các nền kinh tế lớn (G20). Theo đó',
     'nhóm các nền kinh tế lớn (gờ hai mươi). Theo đó'),
    ('extra 01', 'GPT-5.5-Cyber của OpenAI',
     'G P T năm chấm năm Cyber của Open AI'),
    ('extra 01', 'Thế chiến II',
     'Thế chiến hai'),
    ('guard', 'Donald J. Trump; Samuel A. Alito, Jr.; J.R.R. Tolkien',
     'Donald J. Trump; Samuel A. Alito, Jr.; J.R.R. Tolkien'),
    ('guard', 'TIN NÓNG: VIỆT NAM',
     'TIN NÓNG: VIỆT NAM'),
    ('guard', 'UBND TP Hà Nội, HĐND, THPT, CCCD',
     'Ủy ban nhân dân thành phố Hà Nội, Hội đồng nhân dân, trung học phổ thông, căn cước công dân'),
    ('guard', 'NATO, ASEAN, WHO, IMF, GDP, AI, CEO',
     'na tô, a xê an, W H O, I M F, G D P, AI, xi i ô'),
    ('guard', 'chiếm 1/3 dân số; 3/4; gấp 5/3 lần',
     'chiếm một trên ba dân số; ba trên bốn; gấp năm trên ba lần'),
    ('guard', '300 K; 10x20x30cm; Giá 20k; video 60fps',
     'ba trăm ken vin; 10x20x30cm; Giá hai mươi nghìn đồng; video sáu mươi khung hình trên giây'),
    ('guard', 'tính 2026-2030',
     'tính hai nghìn không trăm hai mươi sáu trừ hai nghìn không trăm ba mươi'),
    ('guard', '2026-09-21T19:00:00++07:00',
     '2026-09-21T19:00:00++07:00'),
]


def assert_reading(source, expected, config=None):
    n = Normalizer(config or NormalizerConfig())
    result = n.normalize_with_trace(source)
    assert result.text == expected
    assert n.normalize(result.text) == result.text, "a second pass must not change generated text"
    rebuilt, end = [], 0
    for span in result.spans:
        assert result.source[span.start:span.end] == span.source
        assert end <= span.start
        rebuilt.extend((result.source[end:span.start], span.spoken))
        end = span.end
    rebuilt.append(result.source[end:])
    assert "".join(rebuilt) == expected


@pytest.mark.parametrize("case_id,source,expected", ACCEPTANCE, ids=[f"{c}:{s[:24]}" for c, s, _ in ACCEPTANCE])
def test_acceptance(case_id, source, expected):
    assert_reading(source, expected)


@pytest.mark.parametrize("name", ["danhgia_tts.txt", "danhgia_tts_02.txt", "danhgia_tts_03.txt"])
def test_evaluation_corpora_have_no_unspoken_numbers_or_symbols(name):
    n = Normalizer()
    text = (ROOT / "norm/danhgia" / name).read_text(encoding="utf-8")
    out = n.normalize(text)
    assert n.normalize(out) == out
    assert [m.group() for m in re.finditer(r"\S*[0-9$€£²³%]\S*", out)] == []
    assert re.search(r"\s[+&]\s", out) is None


@pytest.mark.parametrize("source,expected", [
    ("SK", "SK"), ("BTS", "B T S"), ("LG", "LG"), ("WHO", "W H O"), ("ODA", "O D A"),
    ("UBND TP Hà Nội", "Ủy ban nhân dân thành phố Hà Nội"), ("NATO", "na tô"), ("AI", "AI"),
    ("BCHTW", "Ban Chấp hành Trung ương"), ("KRX", "K R X"),
    ("TIN NÓNG: VIỆT NAM", "TIN NÓNG: VIỆT NAM"), ("BẢN TIN VTV", "BẢN TIN V T V"), ("5 ĐỒNG BS", "năm đồng BS"),
    ("Donald J. Trump", "Donald J. Trump"), ("J.R.R. Tolkien", "J.R.R. Tolkien"), ("D.C.", "D.C."),
    ("Thế chiến II", "Thế chiến hai"), ("chương IV", "chương bốn"), ("AMOLED", "AMOLED"), ("HAMAS", "HAMAS"),
    ("GPT-6", "G P T sáu"), ("VN-215", "V N hai một năm"), ("COVID-19", "cô vít mười chín"),
    ("OpenAI", "Open AI"), ("IP 192.168.1.1", "I P một trăm chín mươi hai chấm một trăm sáu mươi tám chấm một chấm một"),
    ("IPv4: 10.0.0.1", "IPv bốn: mười chấm không chấm không chấm một"),
])
def test_abbreviation_policy(source, expected):
    assert_reading(source, expected)


def test_policy_switches_and_legacy_configuration():
    for source, expected in [("SK", "sân khấu"), ("BTS", "Ban tuyển sinh"), ("AI", "AI"), ("USD 1.234", "USD 1.234"),
                             ("GDP năm 2026", "tổng sản phẩm trong nước năm hai nghìn không trăm hai mươi sáu"),
                             ("tổ chức WHO", "tổ chức Y tế Thế giới"), ("1.234", "1.234")]:
        assert_reading(source, expected, LEGACY)
    assert_reading("AI UBND", "AI U B N D", NormalizerConfig(abbreviation_policy="none"))
    assert_reading("BTS UBND", "BTS Ủy ban nhân dân", NormalizerConfig(acronym_mode="preserve"))
    assert_reading("BTS", "bi ti ét", NormalizerConfig(abbreviation_overrides={"BTS": "bi ti ét"}))


def test_common_table_is_small_consistent_and_stable():
    n = Normalizer()
    assert len(COMMON_ABBREVIATIONS) <= 120 and SAY <= COMMON_ABBREVIATIONS.keys()
    for key, reading in COMMON_ABBREVIATIONS.items():
        assert not re.search(r"\b[A-ZĐ]{2,}\b", reading), key
        assert n.normalize(reading) == reading, key
    assert all(name == name.lower() for name in LETTER_NAMES.values())


@pytest.mark.parametrize("token,expected", [
    ("SK", True), ("BTS", True), ("BCHTW", True), ("LV", True), ("AMOLED", False), ("RAIBO", False),
    ("NÓNG", False), ("J.R.R", False), ("II", False), ("XIV", False), ("A", False), ("Tp", False),
])
def test_spell_candidates(token, expected):
    assert is_spell_candidate(token) is expected


@pytest.mark.parametrize("source,expected", [
    ("1.234", "vi"), ("6,23 USD và 1.234", "vi"), ("", "vi"),
    ("1,234,567 và 1,234", "en"), ("1,234.5 và 1,234", "en"),
])
def test_ambiguous_number_inference(source, expected):
    assert infer_ambiguous_number(source) == expected


@pytest.mark.parametrize("source,expected,config", [
    ("Dân số 1,234,567 người và 1,234 km", "Dân số một triệu hai trăm ba mươi tư nghìn năm trăm sáu mươi bảy người và một nghìn hai trăm ba mươi tư ki lô mét", None),
    ("1,234 km", "một phẩy hai ba bốn ki lô mét", NormalizerConfig(ambiguous_number="vi")),
    ("1.234 kg", "một phẩy hai ba bốn ki lô gam", NormalizerConfig(ambiguous_number="en")),
    ("4.265 USD", "4.265 USD", NormalizerConfig(ambiguous_number="preserve")),
    ("1.000 km²", "một phẩy không không không ki lô mét vuông", NormalizerConfig(number_locale="en")),
    ("3.14 và 0.005", "ba phẩy mười bốn và không phẩy không không năm", None),
])
def test_ambiguous_number_policies(source, expected, config):
    assert_reading(source, expected, config)


def test_inferred_locale_is_per_call_and_thread_safe():
    n = Normalizer()
    vi, en = "Giá 6,23 USD; 1.234 người", "Pop 1,234,567; 1.234 kg"
    expected = {vi: n.normalize(vi), en: n.normalize(en)}
    assert expected[vi] != expected[en].replace("Pop", "Giá")
    texts = [vi, en] * 200
    with ThreadPoolExecutor(8) as pool:
        for text, out in zip(texts, pool.map(n.normalize, texts)):
            assert out == expected[text]
    assert n.config.ambiguous_number == "infer"


@pytest.mark.parametrize("source,expected", [
    ("các ngày 25/9, 16/10 và 10/11", "các ngày hai mươi lăm tháng chín, mười sáu tháng mười và mười tháng mười một"),
    ("thứ Hai (5/10)", "thứ Hai (năm tháng mười)"), ("dịp 2/9", "dịp hai tháng chín"),
    ("chiếm 1/3 dân số", "chiếm một trên ba dân số"), ("3/4", "ba trên bốn"), ("gấp 5/3 lần", "gấp năm trên ba lần"),
    ("tối 27.9", "tối hai mươi bảy tháng chín"), ("tăng 27.9%", "tăng hai mươi bảy phẩy chín phần trăm"),
    ("ngày 24-25", "ngày hai mươi tư đến hai mươi lăm"), ("ngày 24-25. Sau đó", "ngày hai mươi tư đến hai mươi lăm. Sau đó"),
    ("ngày 3-5", "ngày ba tháng năm"),
    ("năm học 2008-09", "năm học hai nghìn không trăm lẻ tám đến hai nghìn không trăm lẻ chín"),
    ("1999-00", "từ một nghìn chín trăm chín mươi chín đến hai nghìn"),
    ("1945-2025", "từ một nghìn chín trăm bốn mươi lăm đến hai nghìn không trăm hai mươi lăm"),
    ("tính 2026-2030", "tính hai nghìn không trăm hai mươi sáu trừ hai nghìn không trăm ba mươi"),
    ("2026-09", "2026-09"), ("2027-2026", "2027-2026"), ("2026-09-21T19:00:00++07:00", "2026-09-21T19:00:00++07:00"),
])
def test_dates_and_ranges(source, expected):
    assert_reading(source, expected)


@pytest.mark.parametrize("source,expected", [
    ("200MP + 50MP", "hai trăm mê ga pích xeo cộng năm mươi mê ga pích xeo"), ("Johnson & Johnson", "Johnson và Johnson"),
    ("màn 2K", "màn hai ca"), ("300 K", "ba trăm ken vin"), ("pin 5.000mAh", "pin năm nghìn mi li am pe giờ"),
    ("(40% dân số)", "(bốn mươi phần trăm dân số)"), ("phạt 1.000 euro", "phạt một nghìn ơ rô"),
    ("G20", "gờ hai mươi"), ("5G", "năm gờ"), ("RAIBO2", "RAIBO hai"), ("iPhone15", "iPhone mười lăm"),
    ("MH370", "M H ba trăm bảy mươi"), ("RTX4090", "R T X bốn không chín không"),
    ("3tsp", "3tsp"), ("10x20x30cm", "10x20x30cm"), ("bs.ck1", "bs.ck1"),
])
def test_symbols_units_and_identifiers(source, expected):
    assert_reading(source, expected)


def _atoms():
    atoms = [source for _, source, _ in ACCEPTANCE]
    for path in ("norm/tests/data/news.json", "tests/data/vi_normalizer/domains.json",
                 "tests/data/vi_normalizer/expansion_0_7.json", "tests/data/vi_normalizer/stage_ab.json",
                 "tests/data/vi_normalizer/stage_c.json"):
        atoms += [case["input"] for case in json.loads((ROOT / path).read_text(encoding="utf-8"))["cases"]]
    return atoms


@pytest.mark.parametrize("config", [
    NormalizerConfig(), LEGACY, NormalizerConfig(abbreviation_policy="none"),
    NormalizerConfig(abbreviation_policy="extended"), NormalizerConfig(acronym_mode="preserve"),
    NormalizerConfig(number_locale="vi"), NormalizerConfig(number_locale="en"), NormalizerConfig(enabled_domains=[]),
], ids=["default", "legacy", "none", "extended", "preserve", "vi", "en", "no-domains"])
def test_second_pass_is_stable_across_policies(config):
    n = Normalizer(config)
    atoms = _atoms()
    rng = random.Random(20260930)
    for text in atoms + [" ; ".join(rng.choices(atoms, k=4)) for _ in range(300)]:
        out = n.normalize(text)
        assert n.normalize(out) == out, (text, out)


def test_cli_defaults_match_api_and_legacy_flags():
    def run(*args):
        return subprocess.run([sys.executable, "-m", "vietnamese_tts_normalizer", *args], capture_output=True,
                              text=True, check=True, cwd=ROOT, timeout=60).stdout.strip()
    text = "Tập đoàn SK; 4.265 USD"
    assert run(text) == Normalizer().normalize(text) == "Tập đoàn SK; bốn nghìn hai trăm sáu mươi lăm đô la Mỹ"
    legacy = run("--abbreviations", "extended", "--acronyms", "preserve", "--ambiguous-number", "preserve", text)
    assert legacy == Normalizer(LEGACY).normalize(text) == "Tập đoàn sân khấu; 4.265 USD"
