"""Acceptance tests for vietnamese_tts_normalizer 0.12.0: Vietnamese abbreviations by meaning.

Source: user review of 2026-10-02 ("Bộ trưởng VH-TT-DL" -> "Bộ trưởng Văn hóa, Thể thao và
Du lịch", "T T X V N" -> "Thông tấn xã Việt Nam", "Mát xcơ va" -> "Mát cơ va"), the request to
expand Vietnamese abbreviation clusters in general, and to tell fields apart ("lỡ đâu là PET/CT
thì sao"): an ambiguous short form is read with the meaning it has in its sentence, or not
expanded at all. Plan: docs/vi_normalization_upgrade_plan_0_12_0.md.

ACCEPTANCE: the reviewed sentences. GENERAL: each rule on forms that were not reviewed
(clusters, sectors, glosses, contexts, fields, documents, transliterations). UNCHANGED:
foreign acronyms, tickers, codes and unknown contexts read exactly as in 0.11.0.
"""

import re

import pytest

from vietnamese_tts_normalizer import Normalizer, NormalizerConfig, __version__, normalize_vi_text
from vietnamese_tts_normalizer import vi_abbreviations as vi

N = normalize_vi_text

# (id, input, must contain, must NOT contain)
ACCEPTANCE = [
    ("A01", "Bộ trưởng VH-TT-DL Nguyễn Văn Hùng",
     ["Bộ trưởng Văn hóa, Thể thao và Du lịch Nguyễn Văn Hùng"], ["V H", "VH"]),
    ("A02", "Hà Nội (TTXVN) - Theo TTXVN, phóng viên TTXVN tại Mát-xcơ-va cho biết",
     ["Hà Nội (Thông tấn xã Việt Nam) - Theo Thông tấn xã Việt Nam, phóng viên Thông tấn xã Việt Nam tại Mát cơ va"],
     ["T T X", "xcơ"]),
    ("A03", "Mát xcơ va", ["Mát cơ va"], ["xcơ"]),
    ("A04", "Bệnh nhân được chụp PET/CT và CT 64 lát cắt", ["chụp PET/CT và CT sáu mươi tư lát cắt"], ["chỉ thị", "chủ tịch"]),
]

GENERAL = [
    ('G01', 'Bộ VH,TT&DL',
     ['Bộ Văn hóa, Thể thao và Du lịch'], []),
    ('G02', 'Bộ VHTTDL',
     ['Bộ Văn hóa, Thể thao và Du lịch'], []),
    ('G03', 'Sở GD & ĐT Hà Nội',
     ['Sở Giáo dục và Đào tạo Hà Nội'], []),
    ('G04', 'Bộ LĐ-TB&XH',
     ['Bộ Lao động - Thương binh và Xã hội'], []),
    ('G05', 'Bộ KH&CN',
     ['Bộ Khoa học và Công nghệ'], []),
    ('G06', 'Sở TN-MT',
     ['Sở Tài nguyên và Môi trường'], []),
    ('G07', 'Bộ NN&PTNT',
     ['Bộ Nông nghiệp và Phát triển nông thôn'], []),
    ('G08', 'Thông tư 01/2020/TT-BGDĐT của BGDĐT',
     ['Thông tư không một năm hai nghìn không trăm hai mươi T T B G D Đ T của Bộ Giáo dục và Đào tạo'], []),
    ('G09', 'SKHĐT tỉnh',
     ['Sở Kế hoạch và Đầu tư tỉnh'], []),
    ('G10', 'BR-VT',
     ['Bà Rịa - Vũng Tàu'], []),
    ('G11', 'ĐHQG-HCM',
     ['Đại học Quốc gia Thành phố Hồ Chí Minh'], []),
    ('G12', 'KT-XH-QP-AN',
     ['kinh tế - xã hội - quốc phòng - an ninh'], []),
    ('G13', 'UBND, HĐND & MTTQ',
     ['Ủy ban nhân dân, Hội đồng nhân dân và Mặt trận Tổ quốc'], []),
    ('G14', 'CNH-HĐH',
     ['công nghiệp hóa, hiện đại hóa'], []),
    ('G15', 'Bộ NN&MT, Bộ DT&TG',
     ['Bộ Nông nghiệp và Môi trường, Bộ Dân tộc và Tôn giáo'], []),
    ('G16', 'Bộ TC, Sở TP, Bộ CT',
     ['Bộ Tài chính, Sở Tư pháp, Bộ Công Thương'], []),
    ('G17', 'Bộ CA và Bộ QP',
     ['Bộ Công an và Bộ Quốc phòng'], []),
    ('G18', 'Sở YT, ngành GD',
     ['Sở Y tế, ngành Giáo dục'], []),
    ('G19', 'HTX, ĐHĐCĐ, UBCKNN',
     ['hợp tác xã, Đại hội đồng cổ đông, Ủy ban Chứng khoán Nhà nước'], []),
    ('G20', 'NHNN yêu cầu các TCTD',
     ['Ngân hàng Nhà nước yêu cầu các tổ chức tín dụng'], []),
    ('G21', 'LNST theo BCTC',
     ['lợi nhuận sau thuế theo báo cáo tài chính'], []),
    ('G22', 'CCHC, TTHC, CĐS',
     ['cải cách hành chính, thủ tục hành chính, chuyển đổi số'], []),
    ('G23', 'THADS, TANDTC, VKSNDTC',
     ['thi hành án dân sự, Tòa án nhân dân tối cao, Viện kiểm sát nhân dân tối cao'], []),
    ('G24', 'BHXHVN, TLĐLĐVN',
     ['Bảo hiểm Xã hội Việt Nam, Tổng Liên đoàn Lao động Việt Nam'], []),
    ('G25', 'TNHH MTV, THPT QG, BCH TW',
     ['trách nhiệm hữu hạn một thành viên, trung học phổ thông quốc gia, Ban Chấp hành Trung ương'], []),
    ('G26', 'Ủy ban nhân dân (UBND) tỉnh',
     ['Ủy ban nhân dân tỉnh'], ['(', 'U B']),
    ('G27', 'Đại học Quốc gia Hà Nội (ĐHQGHN).',
     ['Đại học Quốc gia Hà Nội.'], ['(', 'Đ H']),
    ('G28', 'Hà Nội (TTXVN) - Chiều nay',
     ['Hà Nội (Thông tấn xã Việt Nam) - Chiều nay'], []),
    ('G29', 'Bộ Văn hóa, Thể thao và Du lịch (VH-TT-DL), Bộ Y tế',
     ['Bộ Văn hóa, Thể thao và Du lịch, Bộ Y tế'], ['(', 'V H']),
    ('G30', 'Tổ chức Y tế Thế giới (WHO)',
     ['Tổ chức Y tế Thế giới (W H O)'], []),
    ('G31', 'BV Bạch Mai, BV tỉnh',
     ['bệnh viện Bạch Mai, bệnh viện tỉnh'], []),
    ('G32', 'BN 123 đã xuất viện',
     ['bệnh nhân một trăm hai mươi ba đã xuất viện'], []),
    ('G33', 'giành 3 HCV',
     ['giành ba huy chương vàng'], []),
    ('G34', 'các HS lớp 12',
     ['các học sinh lớp mười hai'], []),
    ('G35', '200 TS dự thi',
     ['hai trăm thí sinh dự thi'], []),
    ('G36', 'TS Nguyễn Văn A',
     ['tiến sĩ Nguyễn Văn A'], []),
    ('G37', 'năm 111 TCN',
     ['năm một trăm mười một trước Công nguyên'], []),
    ('G38', 'TK XX và TK 21',
     ['thế kỷ hai mươi và thế kỷ hai mươi mốt'], []),
    ('G39', 'ĐH XIII của Đảng',
     ['Đại hội mười ba của Đảng'], []),
    ('G40', 'thi ĐH, CĐ',
     ['thi đại học, cao đẳng'], []),
    ('G41', 'Thứ 2 - CN',
     ['Thứ hai - chủ nhật'], []),
    ('G42', 'Chủ tịch QH',
     ['Chủ tịch Quốc hội'], []),
    ('G43', 'CA tỉnh',
     ['Công an tỉnh'], []),
    ('G44', 'VD: ĐC: 12 Lê Lợi',
     ['ví dụ: địa chỉ: mười hai Lê Lợi'], []),
    ('G45', 'QL 1A, ĐT 741',
     ['quốc lộ một a, đường tỉnh bảy trăm bốn mươi mốt'], []),
    ('G46', 'ĐT: 0912 345 678',
     ['điện thoại: không chín một hai ba bốn năm sáu bảy tám'], []),
    ('G47', 'Công ty CP Vinamilk',
     ['Công ty cổ phần Vinamilk'], []),
    ('G48', 'PGS.TS Nguyễn Văn A, GS.TSKH Trần B, ThS.BS Lê C, BS.CKII Hoàng D',
     ['phó giáo sư tiến sĩ Nguyễn Văn A, giáo sư tiến sĩ khoa học Trần B, thạc sĩ bác sĩ Lê C, bác sĩ chuyên khoa hai Hoàng D'], []),
    ('G49', 'Đ/c Nguyễn, v/v, K/g',
     ['đồng chí Nguyễn, về việc, kính gửi'], []),
    ('G50', 'các sản phẩm v.v.',
     ['các sản phẩm vân vân.'], []),
    ('G51', 'Cty TNHH',
     ['công ty trách nhiệm hữu hạn'], []),
    ('G52', 'Tp HCM, Tp.HCM, TT-Huế',
     ['thành phố Hồ Chí Minh, thành phố Hồ Chí Minh, Thừa Thiên-Huế'], []),
    ('G53', 'ĐT Việt Nam thắng',
     ['đội tuyển Việt Nam thắng'], []),
    ('G54', 'CT UBND tỉnh, PCT HĐND xã',
     ['chủ tịch Ủy ban nhân dân tỉnh, phó chủ tịch Hội đồng nhân dân xã'], []),
    ('G55', 'chụp CT ngực, máy CT 128 dãy',
     ['chụp CT ngực, máy CT một trăm hai mươi tám dãy'], ['chỉ thị', 'chủ tịch']),
    ('G56', 'kết quả MRI và CT',
     ['kết quả M R I và CT'], ['chỉ thị']),
    ('G57', 'Thủ tướng ban hành CT 20',
     ['Thủ tướng ban hành chỉ thị hai mươi'], []),
    ('G58', 'thực hiện CT 05/CT-TTg',
     ['thực hiện chỉ thị không năm C T T T G'], []),
    ('G59', 'xét nghiệm PCT tăng',
     ['xét nghiệm P C T tăng'], ['chủ tịch']),
    ('G60', 'mộ LS Nguyễn Văn Trỗi',
     ['mộ liệt sĩ Nguyễn Văn Trỗi'], []),
    ('G61', 'LS Trương Thanh Đức bào chữa cho bị cáo',
     ['luật sư Trương Thanh Đức bào chữa cho bị cáo'], []),
    ('G62', 'tấm pin PV công suất 100 MW',
     ['tấm pin PV công suất một trăm mê ga oát'], ['phóng viên']),
    ('G63', 'PV Gas, PV Power',
     ['PV Gas, PV Power'], ['phóng viên']),
    ('G64', 'PV Nguyễn Hà',
     ['phóng viên Nguyễn Hà'], []),
    ('G65', 'phát hành TP doanh nghiệp',
     ['phát hành trái phiếu doanh nghiệp'], []),
    ('G66', 'lãi suất TP chính phủ',
     ['lãi suất trái phiếu chính phủ'], []),
    ('G67', 'TP Hà Nội',
     ['thành phố Hà Nội'], []),
    ('G68', 'mã HS 8471',
     ['mã HS tám nghìn bốn trăm bảy mươi mốt'], ['học sinh']),
    ('G69', 'thuế xuất khẩu theo HS',
     ['thuế xuất khẩu theo HS'], ['học sinh']),
    ('G70', 'nộp HS xét tuyển',
     ['nộp hồ sơ xét tuyển'], []),
    ('G71', 'giá CP ngân hàng',
     ['giá cổ phiếu ngân hàng'], []),
    ('G72', 'Nghị quyết của CP về phát triển',
     ['Nghị quyết của Chính phủ về phát triển'], []),
    ('G73', '2 BN USD',
     ['hai BN đô la Mỹ'], ['bệnh nhân']),
    ('G74', 'các NV xét tuyển',
     ['các nguyện vọng xét tuyển'], []),
    ('G75', 'các NV ngân hàng',
     ['các nhân viên ngân hàng'], []),
    ('G76', 'KS 5 sao',
     ['khách sạn năm sao'], []),
    ('G77', 'KS Mường Thanh đón du khách',
     ['khách sạn Mường Thanh đón du khách'], []),
    ('G78', 'các GV đại học',
     ['các giảng viên đại học'], []),
    ('G79', 'các GV mầm non',
     ['các giáo viên mầm non'], []),
    ('G80', 'tổng TS của ngân hàng',
     ['tổng tài sản của ngân hàng'], []),
    ('G81', 'xe mang BS 30A-123.45',
     ['xe mang biển số ba không a gạch ngang một hai ba chấm bốn năm'], []),
    ('G82', 'BS Lê Văn B',
     ['bác sĩ Lê Văn B'], []),
    ('G83', 'CN Hà Nội của Vietcombank',
     ['chi nhánh Hà Nội của Vietcombank'], []),
    ('G84', 'các CN nhà máy đình công',
     ['các công nhân nhà máy đình công'], []),
    ('G85', 'năm 179 trước CN',
     ['năm một trăm bảy mươi chín trước Công nguyên'], []),
    ('G86', 'BTL Quân khu 7',
     ['Bộ Tư lệnh Quân khu bảy'], []),
    ('G87', 'BCH Quân sự tỉnh',
     ['Ban Chỉ huy Quân sự tỉnh'], []),
    ('G88', 'quyền lợi NTD',
     ['quyền lợi người tiêu dùng'], []),
    ('G89', 'NTD tuyển dụng ứng viên',
     ['nhà tuyển dụng tuyển dụng ứng viên'], []),
    ('G90', 'các ĐV chi đoàn tình nguyện',
     ['các đoàn viên chi đoàn tình nguyện'], []),
    ('G91', 'các ĐV trực thuộc',
     ['các đơn vị trực thuộc'], []),
    ('G92', 'điểm TB, TB 45/TB-VP',
     ['điểm trung bình, thông báo bốn mươi lăm T B V P'], []),
    ('G93', 'vốn NN, trung tâm NN',
     ['vốn nhà nước, trung tâm ngoại ngữ'], []),
    ('G94', 'thi TN THPT, Đoàn TN',
     ['thi tốt nghiệp trung học phổ thông, Đoàn Thanh niên'], []),
    ('G95', 'ĐH SP Hà Nội, các SP OCOP',
     ['Đại học Sư phạm Hà Nội, các sản phẩm OCOP'], []),
    ('G96', 'KH cá nhân, KH 123/KH-UBND',
     ['khách hàng cá nhân, kế hoạch một trăm hai mươi ba K H U B N D'], []),
    ('G97', 'NĐ 100/2019',
     ['nghị định một trăm năm hai nghìn không trăm mười chín'], []),
    ('G98', 'theo QĐ số 15/2020',
     ['theo quyết định số mười lăm năm hai nghìn không trăm hai mươi'], []),
    ('G99', 'Nghị định 12/2020',
     ['Nghị định mười hai năm hai nghìn không trăm hai mươi'], []),
    ('G100', 'UBND năm 2020 đã chi',
     ['Ủy ban nhân dân năm hai nghìn không trăm hai mươi đã chi'], []),
    ('G101', 'HĐND năm nay, BHXH một tháng',
     ['Hội đồng nhân dân năm nay, bảo hiểm xã hội một tháng'], []),
    ('G102', 'ĐT 0912345678',
     ['điện thoại không chín một hai ba bốn năm sáu bảy tám'], []),
    ('G103', 'Ôxtrâylia, Mátxcơva',
     ['Ô trây lia, Mát cơ va'], ['xc', 'xt']),
    ('G104', 'Xtốc-khôm, Xlô-va-ki-a',
     ['Tốc khôm, Lô va ki a'], ['Xt', 'Xl']),
    ('G105', 'Kadắcxtan, Phran-xi-xcô',
     ['Ka dắc tan, Phran xi cô'], ['xt', 'xc']),
]

# 0.11.0 readings that must not change: foreign acronyms, tickers, codes, unknown contexts.
UNCHANGED = [
    ('GDP', 'G D P'),
    ('CEO', 'xi i ô'),
    ('BTS', 'B T S'),
    ('SK hynix', 'SK hynix'),
    ('LG', 'LG'),
    ('giá BTC hôm nay', 'giá B T C hôm nay'),
    ('NCT 127', 'N C T một trăm hai mươi bảy'),
    ('cổ phiếu HSG và KDC', 'cổ phiếu H S G và K D C'),
    ('EU-ASEAN', 'EU-a xê an'),
    ('M&A, AT&T', 'M và A, A T và T'),
    ('S&P 500', 'S và P năm trăm'),
    ('15/2020/NĐ-CP', 'mười lăm năm hai nghìn không trăm hai mươi N Đ C P'),
    ('57-NQ/TW', 'năm mươi bảy N Q T W'),
    ('các KH', 'các KH'),
    ('KS Nguyễn Văn C', 'KS Nguyễn Văn C'),
    ('TK 123', 'TK một trăm hai mươi ba'),
    ('TL 10%', 'TL mười phần trăm'),
    ('PET-CT', 'P E T C T'),
    ('chụp PET/CT', 'chụp PET/CT'),
    ('Xbox', 'Xbox'),
    ('X-quang', 'X quang'),
    ('Krông Pắc', 'Krông Pắc'),
    ('Pakixtan', 'Pakixtan'),
    ('virus HCV', 'virus H C V'),
    ('QH 1/500', 'QH một trên năm trăm'),
    ('CPU TDP 65W', 'C P U T D P sáu mươi lăm oát'),
    ('nộp BTL môn học', 'nộp B T L môn học'),
    ('VTV, HTV', 'V T V, H T V'),
    ('TIN NÓNG', 'TIN NÓNG'),
    ('CA SĨ', 'CA SĨ'),
    ('AI', 'AI'),
    ('QL1AB', 'QL1AB'),
]


def test_version():
    # 0.13.0 keeps every 0.12.0 reading checked here.
    assert tuple(map(int, __version__.split("."))) >= (0, 12, 0)


@pytest.mark.parametrize("cid,text,expected,forbidden", ACCEPTANCE + GENERAL)
def test_acceptance(cid, text, expected, forbidden):
    out = N(text)
    assert any(e in out for e in expected), (cid, out)
    assert not any(f in out for f in forbidden), (cid, out)


@pytest.mark.parametrize("text,expected", UNCHANGED)
def test_unchanged_from_0_11_0(text, expected):
    assert N(text) == expected


@pytest.mark.parametrize("text", [c[1] for c in ACCEPTANCE + GENERAL] + [c[0] for c in UNCHANGED])
def test_two_pass_stable(text):
    once = N(text)
    assert N(once) == once


@pytest.mark.parametrize("text", [c[1] for c in ACCEPTANCE + GENERAL])
def test_trace_rebuilds_output(text):
    """Source gaps + span readings rebuild the output, dropped glosses included."""
    result = Normalizer().normalize_with_trace(text)
    rebuilt, end = [], 0
    for span in result.spans:
        assert result.source[span.start:span.end] == span.source and end <= span.start
        rebuilt.extend((result.source[end:span.start], span.spoken))
        end = span.end
    rebuilt.append(result.source[end:])
    assert "".join(rebuilt) == result.text


def _readings():
    pairs = [*vi.ALWAYS.items(), *vi.SECTORS.items(), *vi.SPECIAL.items(), *vi.SPECIAL_PAIRS.items(), *vi.TITLES.items()]
    pairs += [(form, reading) for form, options in vi.CONTEXTUAL.items() for _, reading in options if reading]
    return pairs


def test_readings_are_plain_text_and_fixed_points():
    """No digits or capital runs in a reading, and a reading normalizes to itself."""
    for form, reading in _readings():
        assert not re.search(r"[0-9]|[A-ZĐ]{2,}", reading), (form, reading)
        assert N(reading) == reading, (form, reading)


# Foreign acronyms, brands and stock tickers common in Vietnamese news.
FOREIGN = ("GDP CPI FDI ODA CEO CFO IT AI IMF WHO WTO UN EU NATO ASEAN USD EUR BTC ETH NFT ETF IPO CNN BBC AFP AP VOA "
           "NHK KBS SBS MBC CCTV NASA FBI CIA FIFA AFF AFC VAR MVP NBA BTS SK LG HP IBM BMW FPT VNPT EVN BIDV VCB ACB SHB "
           "MB HSG KDC NCT HSV SGD VIC VHM VNM HPG MWG SSI CTG TCB MBB VPB TPB STB HDB GAS PLX POW SAB VJC DGC DPM").split()


def test_no_foreign_acronym_or_ticker_is_expanded():
    for token in FOREIGN:
        assert token not in vi.ALWAYS and vi.lookup(token) is None, token


@pytest.mark.parametrize("frame", ["{}", "theo {}", "Bộ {}", "các {} năm 2024", "{} 123", "3 {}", "{} Bạch Mai",
                                   "Thông tấn xã Việt Nam ({})", "{} năm nay", "chụp {} ngực"])
@pytest.mark.parametrize("config", [{}, {"acronym_mode": "spell"}, {"acronym_mode": "preserve"}, {"number_locale": "vi"}],
                         ids=["default", "spell", "preserve", "vi"])
def test_every_lexicon_form_is_stable_in_context(frame, config):
    n = Normalizer(NormalizerConfig(**config))
    forms = [*vi.ALWAYS, *vi.SECTORS, *vi.CONTEXTUAL, *vi.SPECIAL, *vi.SPECIAL_PAIRS]
    for form in forms:
        once = n.normalize(frame.format(form))
        assert n.normalize(once) == once, (frame, form, once)


@pytest.mark.parametrize("cue,text", [
    (vi.MEDICAL, "chụp CT, kết quả MRI và PET"), (vi.ADMIN, "UBND tỉnh"), (vi.FINANCE, "cổ phiếu HOSE"),
    (vi.UNIVERSITY, "trường ĐH, SV"), (vi.SPORTS, "đội tuyển, SEA Games"), (vi.BANKING, "chi nhánh Vietcombank"),
])
def test_field_cues_survive_normalization(cue, text):
    """A cue must still be found after a pass, so a second pass takes the same decision."""
    assert cue.search(text) and cue.search(N(text))


@pytest.mark.parametrize("policy,text,expected", [
    ("none", "TTXVN", "T T X V N"), ("none", "Bộ VH-TT-DL", "Bộ V H T T D L"), ("none", "BV Bạch Mai", "BV Bạch Mai"),
    ("none", "KH&CN", "K H và C N"), ("extended", "TTXVN", "Thông tấn xã Việt Nam"),
    ("extended", "Bộ VH-TT-DL", "Bộ V H T T D L"), ("extended", "BV Bạch Mai", "bệnh viện Bạch Mai"),
    # Transliterated syllables are a reading rule, not an abbreviation policy.
    ("none", "Mát-xcơ-va", "Mát cơ va"), ("extended", "Mát-xcơ-va", "Mát cơ va"),
])
def test_other_abbreviation_policies_keep_0_11_0(policy, text, expected):
    assert Normalizer(NormalizerConfig(abbreviation_policy=policy)).normalize(text) == expected


def test_preserve_mode_keeps_the_gloss():
    n = Normalizer(NormalizerConfig(acronym_mode="preserve"))
    assert n.normalize("Thông tấn xã Việt Nam (TTXVN) đưa tin.") == "Thông tấn xã Việt Nam (TTXVN) đưa tin."


@pytest.mark.parametrize("text,expected", [
    ("Xbox", "Xbox"), ("X-quang", "X quang"), ("next text", "next text"), ("Excel", "Excel"),
    ("Krông Pắc", "Krông Pắc"), ("Pakixtan", "Pakixtan"), ("Xingapo", "Xingapo"),
])
def test_transliteration_rule_only_touches_vietnamese_syllables(text, expected):
    """English words and clusters other than x+consonant are left alone."""
    assert N(text) == expected
