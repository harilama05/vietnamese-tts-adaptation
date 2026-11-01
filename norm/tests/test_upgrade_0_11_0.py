"""Acceptance tests for vietnamese_tts_normalizer 0.11.0.

Source: user listening review of danhgia_tts_02..05 (2026-10-01), the follow-up
decisions ("từ ... đến ...", "quý một và quý hai", "ép mười sáu") and the request
to make every rule general, not tied to the reviewed sentences. Plan:
docs/vi_normalization_upgrade_plan_0_11_0.md. Copy this file to
norm/tests/test_upgrade_0_11_0.py. Do NOT edit the expected values: if a case
fails, fix the code (see the plan, section 3).

Acceptance cases check only the target span (substring) so that unrelated
readings elsewhere in the sentence do not make the table brittle. Group R/D/A/N/L/H/U
are the reviewed sentences; group G checks that each rule works beyond them.
"""

import os
import subprocess
import sys

import pytest

from vietnamese_tts_normalizer import Normalizer, NormalizerConfig, __version__, normalize_vi_text
from vietnamese_tts_normalizer.sentences import initial_periods

N = normalize_vi_text

# (id, input, must contain, must NOT contain)
ACCEPTANCE = [
    # R: Vietnamese document symbols -> number + separate letters, separators dropped
    ("R01", "Nghị quyết số 02/NQ-CP năm 2026.",
     ["Nghị quyết số không hai N Q C P năm hai nghìn không trăm hai mươi sáu."], ["/", "NQ", "nờ"]),
    ("R02", "Bài báo nêu việc triển khai Nghị quyết 57-NQ/TW cùng các cải cách.",
     ["Nghị quyết năm mươi bảy N Q T W cùng"], ["57", "NQ/TW", "Trung ương"]),
    ("R03", "ký Nghị quyết số 298/NQ-CP ban hành Kế hoạch thực hiện Nghị quyết số 05-NQ/ĐU ngày 12/6/2026 về",
     ["số hai trăm chín mươi tám N Q C P ban hành",
      "số không năm N Q Đ U ngày mười hai tháng sáu năm hai nghìn không trăm hai mươi sáu về"], ["/", "-"]),
    ("R04", "Quyết định số 1234/QĐ-UBND ngày 5/3",
     ["Quyết định số một nghìn hai trăm ba mươi tư Q Đ U B N D ngày"], ["Ủy ban", "1234"]),
    ("R05", "Nghị định 15/2020/NĐ-CP và Thông tư 01/2024/TT-BTC",
     ["Nghị định mười lăm năm hai nghìn không trăm hai mươi N Đ C P và "
      "Thông tư không một năm hai nghìn không trăm hai mươi tư T T B T C"], ["xuyệt", "gạch ngang"]),
    ("R06", "Chỉ thị 05-CT/TW, Công văn 456/BTC-TCT",
     ["Chỉ thị không năm C T T W, Công văn bốn trăm năm mươi sáu B T C T C T"], ["/"]),
    ("R07", "Luật số 61/2020/QH14",
     ["Luật số sáu mươi mốt năm hai nghìn không trăm hai mươi Q H mười bốn"], ["/", "QH"]),
    # D: technical designators -> every letter separate, 3+ digit groups digit by digit
    ("D01", "cho hệ thống Identification Friend or Foe (IFF) AN/APX-127(V)1, được thiết kế",
     ["(I F F) A N A P X một hai bảy V một, được thiết kế"], ["AN/APX", "(V)", "i ép ép"]),
    ("D02", "các phiên bản AN/APX-113(V), AN/APX-125(V) và AN/APX-126(V) trên",
     ["A N A P X một một ba V, A N A P X một hai năm V và A N A P X một hai sáu V trên"], ["(vê)", "AN/"]),
    # A: acronyms. 2 letters keep, 3 letters and unpronounceable 4+ spelled in Latin capitals,
    # pronounceable 4+ letters keep (the model reads them itself)
    ("A01", "góp phần đạt mục tiêu tăng trưởng GDP hai con số",
     ["tăng trưởng G D P hai con số"], ["gờ đê pê"]),
    ("A02", "giới thiệu mô hình AI GPT-6 Cyber", ["mô hình AI G P T sáu Cyber"], ["ây ai", "gi pi ti"]),
    ("A03", "tập đoàn LG và SK Hynix", ["tập đoàn LG và SK Hynix"], ["lờ gờ", "ét ca"]),
    ("A04", "hội nghị thượng đỉnh Nhóm BRICS đang diễn ra", ["Nhóm BRICS đang diễn ra"], ["brích"]),
    ("A05", "huy động nguồn lực, trong đó có sáng kiến POWERR ASIA.",
     ["sáng kiến POWERR ASIA."], ["a ét i a", "A S I A"]),
    ("A06", "Công nghệ Biển–Trái đất Nhật Bản (JAMSTEC), dự kiến", ["(JAMSTEC), dự kiến"], ["J A M"]),
    ("A07", "Theo báo cáo GII 2026 của WIPO, Việt Nam",
     ["báo cáo G I I hai nghìn không trăm hai mươi sáu của WIPO, Việt Nam"], ["gờ i i", "vê kép"]),
    ("A08", "Trung tâm Nghiên cứu Chiến lược và Quốc tế Mỹ (CSIS) ghi nhận ... và trinh sát (C4ISR).",
     ["(C S I S) ghi nhận", "(C bốn I S R)."], ["xê ét"]),
    ("A09", "Hội nghị Cấp cao CLMV lần thứ 12. Tại SOM CLMV, bà đề nghị",
     ["Cấp cao C L M V lần thứ mười hai.", "Tại S O M C L M V, bà"], ["xê lờ"]),
    ("A10", "MOL ký thỏa thuận với BAE Systems", ["M O L ký thỏa thuận với B A E Systems"], ["mờ ô lờ"]),
    ("A11", "Giá dầu WTI sáng 28 tại New York", ["Giá dầu W T I sáng hai mươi tám"], ["vê kép"]),
    ("A12", "Elon Musk, CEO của SpaceX", ["Elon Musk, xi i ô của SpaceX"], ["C E O"]),
    ("A13", "ra mắt chatbot AI công khai, hợp tác với SpaceXAI và OpenAI",
     ["chatbot AI công khai", "Space X A I", "Open AI"], ["ây ai", "ích"]),
    ("A14", "gia nhập lại Liên minh châu Âu (EU), hội nghị thượng đỉnh Anh-EU",
     ["Liên minh châu Âu (EU), hội nghị thượng đỉnh Anh-EU"], ["e u"]),
    ("A15", "Tổ chức Y tế Thế giới (WHO) và Tổ chức Thương mại Thế giới (WTO)",
     ["(W H O) và", "(W T O)"], ["vê kép"]),
    ("A16", "IMEI, ICAO, IAEA, OECD, EVFTA, CPTPP",
     ["I M E I, I C A O, I A E A, O E C D, E V F T A, C P T P P"], []),
    ("A17", "AMOLED, KAIST, HAMAS, NVIDIA", ["AMOLED, KAIST, HAMAS, NVIDIA"], []),
    ("A18", "phi công F-16 và F-35", ["phi công ép mười sáu và ép ba mươi lăm"], ["một sáu", "ba năm"]),
    # VN expands to "Việt Nam" when standalone, so inside a code it is spelled (stable second pass).
    ("A19", "VN-215, AB-1234, CVE-2026-65660, RTX4090",
     ["V N hai một năm, A B một hai ba bốn, C V E hai không hai sáu sáu năm sáu sáu không, R T X bốn không chín không"], []),
    ("A20", "Su-30MK2, MiG-21, GPT-5.5-Cyber",
     ["Su ba mươi M K hai, MiG hai mươi mốt, G P T năm chấm năm Cyber"], []),
    # N: ordinals and ranges ("từ A đến B" unless a framing word precedes the range)
    ("N01", "đã làm chủ công nghệ, đạt vị trí khoảng thứ 4-5 thế giới trong một số phân khúc",
     ["đạt vị trí khoảng thứ tư đến thứ năm thế giới"], ["4-5", "thứ bốn"]),
    ("N02", "lần thứ 1, lần thứ 4, thứ 4 tuần sau, thứ 2-3 hằng tuần",
     ["lần thứ nhất, lần thứ tư, thứ tư tuần sau, thứ hai đến thứ ba hằng tuần"], ["thứ một", "thứ bốn"]),
    ("N03", "trong 4-5 năm, hạng 4-5, top 4-5, mất 4-5 ngày",
     ["trong bốn đến năm năm, hạng bốn đến năm, top bốn đến năm, mất từ bốn đến năm ngày"], ["4-5"]),
    ("N04", "giá trị nội địa hóa còn thấp (20%-30%) và tăng 20%-30% so với, giảm từ 5%-7%",
     ["(từ hai mươi phần trăm đến ba mươi phần trăm) và tăng từ hai mươi phần trăm đến ba mươi phần trăm "
      "so với, giảm từ năm phần trăm đến bảy phần trăm"],
     ["âm", "trămâm", "từ từ"]),
    ("N05", "đà tăng đã chậm lại so với quý I và II. Quý II, III và IV; Thế chiến I và II; "
            "xếp thứ I và II; thế kỷ XIX-XX",
     ["so với quý một và quý hai. Quý hai, quý ba và quý bốn; Thế chiến một và thế chiến hai; "
      "xếp thứ nhất và thứ hai; thế kỷ mười chín đến thế kỷ hai mươi"],
     [" II", "III", " IV", "XX", "thứ một"]),
    # L: list markers
    ("L01", "❶ Trung Quốc và Lào đưa vào hoạt động.\n❷ Mỹ phản ứng.",
     ["một, Trung Quốc và Lào", "\nhai, Mỹ phản ứng."], ["❶", "❷"]),
    ("L02", "cụ thể: (i) tại căn cứ Ream; (ii) tại Djibouti; (iii) tại Gwadar; (iv) nơi khác",
     ["cụ thể: một, tại căn cứ Ream; hai, tại Djibouti; ba, tại Gwadar; bốn, nơi khác"], ["(i)", "(ii)"]),
    ("L03", "Các bước:\n(I) chuẩn bị;\n(II) thực hiện.", ["\nmột, chuẩn bị;\nhai, thực hiện."], ["(I)"]),
    # H: hyphenated transliterations
    ("H01", "Ả Rập Xê-út, Bô-li-vi-a và Lee Jae-myung",
     ["Ả Rập Xê út, Bô li vi a và Lee Jae myung"], ["Xê-út", "-li-"]),
    # U: currency read by meaning
    ("U01", "giá 100 USD/thùng, 4.265 USD một ounce, 2 tỷ USD",
     ["một trăm đô la Mỹ trên thùng, bốn nghìn hai trăm sáu mươi lăm đô la Mỹ một ounce, hai tỷ đô la Mỹ"], []),
    ("U02", "USD 5, US$5 và $5", ["năm đô la Mỹ, năm đô la Mỹ và năm đô la"], ["u ét", "$"]),
]

# G: the same rules on forms that were NOT in the review (generality).
GENERAL = [
    # acronyms
    ("G01", "thương vụ M&A, chi phí R&D, AT&T và P&G", ["M và A", "R và D", "A T và T và P và G"], ["&"]),
    ("G02", "các CEOs và NGOs, 3 ATMs, nhiều KPIs",
     ["các xi i ô và N G O, ba A T M, nhiều K P I"], ["Os", "Ms"]),
    ("G03", "TOP 10 sản phẩm HOT, hàng NEW, SEA Games, bản tin NEWS",
     ["TOP mười sản phẩm HOT, hàng NEW, SEA Games, bản tin NEWS"], ["T O P", "H O T"]),
    ("G04", "AWS, IELTS, HIMARS, AUKUS", ["A W S, IELTS, HIMARS, AUKUS"], []),
    ("G05", "trường ĐH, hệ CĐ, BCĐ tỉnh", ["trường đại học, hệ cao đẳng, Ban Chỉ đạo tỉnh"], []),
    ("G06", "ChatGPT, OpenAI, ZeroTTS", ["Chat G P T, Open AI, Zero T T S"], []),
    ("G06b", "ngành IT, Liên Hợp Quốc (UN), mã XE4, IP 10.0.0.1", ["ngành I T, Liên Hợp Quốc (U N), mã X E bốn, I P mười"], []),
    # document symbols in other shapes
    ("G07", "Quyết định 15/QĐ-TTg, Thông tư 08/2021/TT-BGDĐT, Luật 36/2024/QH15, Công điện 1234/CĐ-TTg",
     ["Quyết định mười lăm Q Đ T T G, Thông tư không tám năm hai nghìn không trăm hai mươi mốt T T B G D Đ T, "
      "Luật ba mươi sáu năm hai nghìn không trăm hai mươi tư Q H mười lăm, "
      "Công điện một nghìn hai trăm ba mươi tư C Đ T T G"], ["/", "TTg"]),
    ("G08", "văn bản số 123/UBND-VP và Nghị quyết 68-NQ/TW",
     ["văn bản số một trăm hai mươi ba U B N D V P và Nghị quyết sáu mươi tám N Q T W"], []),
    ("G09", "theo NĐ-CP, quan hệ EU-ASEAN, WTO-IMF",
     ["theo N Đ C P, quan hệ EU-a xê an, W T O I M F"], ["NĐ-CP"]),
    # designators and model codes
    ("G10", "radar AN/TPY-2, tiêm kích F/A-18E/F, hệ thống S-400, S-300 và máy bay B-52",
     ["radar A N T P Y hai, tiêm kích F A mười tám E F, hệ thống ét bốn trăm, ét ba trăm và máy bay bê năm mươi hai"], []),
    # ranges
    ("G11", "5kg-10kg, 5m-10km, nhiệt độ 5°C-10°C, 20% - 30%, (20 - 30%)",
     ["từ năm ki lô gam đến mười ki lô gam, từ năm mét đến mười ki lô mét, nhiệt độ từ năm độ xê đến mười độ xê, "
      "từ hai mươi phần trăm đến ba mươi phần trăm, (từ hai mươi đến ba mươi phần trăm)"], []),
    ("G12", "dự án (2024-2033) và (20-30), lãi suất 5%-6%/năm",
     ["dự án (từ hai nghìn không trăm hai mươi tư đến hai nghìn không trăm ba mươi ba) và (từ hai mươi đến ba mươi), "
      "lãi suất từ năm phần trăm đến sáu phần trăm trên năm"], ["mở ngoặc", "trừ"]),
    ("G13", "giá 20k-30k đồng, dao động 20-30%, lượng mưa 50-100mm, 1-2 tuần",
     ["giá từ hai mươi nghìn đồng đến ba mươi nghìn đồng, dao động từ hai mươi đến ba mươi phần trăm, "
      "lượng mưa từ năm mươi đến một trăm mi li mét, từ một đến hai tuần"], []),
    ("G14", "khoảng 20-30%, gió cấp 6–7, Điều 4-6, năm học 2025-2026, lúc 8h-10h",
     ["khoảng hai mươi đến ba mươi phần trăm, gió cấp sáu đến bảy, Điều bốn đến sáu, "
      "năm học hai nghìn không trăm hai mươi lăm đến hai nghìn không trăm hai mươi sáu, lúc tám giờ đến mười giờ"],
     ["từ"]),
    ("G15", "tháng 4-5, quý 1-2, quý I–II/2026, tháng 6-7/2026",
     ["tháng tư đến tháng năm, quý một đến quý hai, quý một đến quý hai năm hai nghìn không trăm hai mươi sáu, "
      "tháng sáu đến tháng bảy năm hai nghìn không trăm hai mươi sáu"], []),
    ("G16", "giảm 10% - 5% = 5%", ["giảm mười phần trăm - năm phần trăm = năm phần trăm"], ["đến"]),
    # Roman numerals, list markers and numeral characters
    ("G17", "trường cấp II, cấp III; Mục II; Tập II; giai đoạn II; nhóm II; vùng I; Phụ lục IV; học kỳ I",
     ["trường cấp hai, cấp ba; Mục hai; Tập hai; giai đoạn hai; nhóm hai; vùng một; Phụ lục bốn; học kỳ một"], []),
    ("G18", "chương I-III, cấp II và III", ["chương một đến chương ba, cấp hai và cấp ba"], []),
    ("G19", "Nữ hoàng Elizabeth II, Vua Charles III, Đức Giáo hoàng Leo XIV, vua Louis XIV",
     ["Nữ hoàng Elizabeth đệ nhị, Vua Charles đệ tam, Đức Giáo hoàng Leo mười bốn, vua Louis mười bốn"], []),
    ("G20", "I. MỞ ĐẦU\nII. Nội dung", ["một. MỞ ĐẦU\nhai. Nội dung"], []),
    ("G21", "loại C, phần D, chương M", ["loại C, phần D, chương M"], ["một trăm", "năm trăm", "nghìn"]),
    ("G22", "Ⅱ, ⑴, ⒈ Trung Quốc, ㉑, ➊ Mỹ, Thế chiến Ⅱ, ① ② ③",
     ["hai, một, một. Trung Quốc, hai mươi mốt, một, Mỹ, Thế chiến hai, một, hai, ba"], []),
    # currency
    ("G23", "US$5, HK$5, S$5, A$5, NT$5, C$5, NZ$5, ¥500, ₩1000, ₹50, ₽100, ฿20",
     ["năm đô la Mỹ, năm đô la Hồng Kông, năm đô la Xin ga po, năm đô la Úc, năm Đài tệ, năm đô la Canada, "
      "năm đô la New Zealand, năm trăm yên Nhật, một nghìn uôn Hàn Quốc, năm mươi rupee Ấn Độ, "
      "một trăm rúp Nga, hai mươi bạt Thái"], ["$"]),
    ("G24", "5 AUD, 5 SGD, 5 THB, 5 CAD, 100 HKD; phần mềm CAD, CAD 2024",
     ["năm đô la Úc, năm đô la Xin ga po, năm bạt Thái, năm đô la Canada, một trăm đô la Hồng Kông; "
      "phần mềm C A D, C A D hai nghìn không trăm hai mươi tư"], []),
    # hyphenated transliterations
    ("G25", "Ô-xtrây-li-a, Mát-xcơ-va, Kim Jong-un, X-quang, Phi-líp-pin",
     ["Ô trây li a, Mát cơ va, Kim Jong un, X quang, Phi líp pin"], ["-"]),
]

# Exact 0.10.0 outputs that 0.11.0 must keep byte for byte.
UNCHANGED = [
    ("NATO, ASEAN, NASA, COVID-19, UBND, TP.HCM, TIN NÓNG VIỆT NAM",
     "na tô, a xê an, na sa, cô vít mười chín, Ủy ban nhân dân, thành phố Hồ Chí Minh, TIN NÓNG VIỆT NAM"),
    ("lớp 12A1, G7, G20, H5N1, U23, 5G, H2O, VN30, QL1A, chuyến bay VJ123",
     "lớp mười hai a một, gờ bảy, gờ hai mươi, hắt năm nờ một, u hai mươi ba, năm gờ, hắt hai ô, "
     "vê nờ ba mươi, quốc lộ một a, chuyến bay vê giây một hai ba"),
    ("hôm 4-5 tôi đi, nhiệt độ -5°C, giảm từ 2% xuống -1%",
     "hôm bốn tháng năm tôi đi, nhiệt độ âm năm độ xê, giảm từ hai phần trăm xuống âm một phần trăm"),
    ("lần thứ 14, thứ 24, thứ 2 tuần sau", "lần thứ mười bốn, thứ hai mươi tư, thứ hai tuần sau"),
    ("Hàn-Mỹ, Mekong-Nhật Bản, Wi-Fi, COVID-19, logistics - kinh tế, Biển–Trái đất",
     "Hàn-Mỹ, Mekong-Nhật Bản, Wi-Fi, cô vít mười chín, logistics - kinh tế, Biển–Trái đất"),
    ("Donald J. Trump nói", "Donald J. Trump nói"),
    ("Thế chiến II, quý III/2026", "Thế chiến hai, quý ba năm hai nghìn không trăm hai mươi sáu"),
    ("khoảng 20-30% dân số", "khoảng hai mươi đến ba mươi phần trăm dân số"),
    ("lớp 6B, số nhà 12/3A", "lớp sáu bê, số nhà mười hai xuyệt ba a"),
    ("giá $5", "giá năm đô la"),
    ("AMOLED, KAIST, HAMAS, RAIBO2", "AMOLED, KAIST, HAMAS, RAIBO hai"),
    ("an ninh quốc phòng-an ninh, kinh tế-thương mại-đầu tư, tương thích drop-in",
     "an ninh quốc phòng-an ninh, kinh tế-thương mại-đầu tư, tương thích drop-in"),
    # Match scores and a bare "3-5" stay ambiguous; letter-only slash pairs stay intact.
    ("Việt Nam 3-1 Thái Lan, thắng 2-1, 3-5", "Việt Nam 3-1 Thái Lan, thắng hai một, 3-5"),
    ("USD/VND, KM/H, ABC/DEF", "USD/VND, KM/H, ABC/DEF"),
    ("V. Putin phát biểu", "V. Putin phát biểu"),
    ("ô-tô, Al-Qaeda, 30 độ C", "ô-tô, Al-Qaeda, ba mươi độ C"),
]

LEGACY = {"acronym_mode": "spell"}
PRESERVE = {"acronym_mode": "preserve"}
NO_FROM = {"range_prefix": ""}


def test_version():
    # 0.12.0 keeps every 0.11.0 reading checked here.
    assert tuple(map(int, __version__.split("."))) >= (0, 11, 0)


def test_default_policies():
    config = NormalizerConfig()
    assert config.acronym_mode == "latin" and config.range_prefix == "từ"
    for mode in ("latin", "spell", "preserve"):
        assert NormalizerConfig(acronym_mode=mode).acronym_mode == mode
    with pytest.raises(ValueError):
        NormalizerConfig(acronym_mode="english")
    with pytest.raises(ValueError):
        NormalizerConfig(range_prefix="từ khoảng")


@pytest.mark.parametrize("case_id,text,must,must_not", ACCEPTANCE + GENERAL, ids=[c[0] for c in ACCEPTANCE + GENERAL])
def test_acceptance(case_id, text, must, must_not):
    out = N(text)
    for expected in must:
        assert expected in out, out
    for forbidden in must_not:
        assert forbidden not in out, out


@pytest.mark.parametrize("text,expected", UNCHANGED)
def test_unchanged_from_0_10_0(text, expected):
    assert N(text) == expected


@pytest.mark.parametrize("text", [c[1] for c in ACCEPTANCE + GENERAL] + [c[0] for c in UNCHANGED])
def test_two_pass_stable(text):
    once = N(text)
    assert N(once) == once


@pytest.mark.parametrize("text", [c[1] for c in ACCEPTANCE + GENERAL])
def test_trace_rebuilds_output(text):
    """Source gaps + span readings must rebuild the output (joined hyphens included)."""
    result = Normalizer().normalize_with_trace(text)
    rebuilt, end = [], 0
    for span in result.spans:
        assert result.source[span.start:span.end] == span.source and end <= span.start
        rebuilt.extend((result.source[end:span.start], span.spoken))
        end = span.end
    rebuilt.append(result.source[end:])
    assert "".join(rebuilt) == result.text


@pytest.mark.parametrize("policy,text,expected", [
    (LEGACY, "GDP, AI, CEO, LG, BRICS", "gờ đê pê, ây ai, xi i ô, lờ gờ, brích"),
    (LEGACY, "số 02/NQ-CP", "số không hai nờ quy xê pê"),
    (LEGACY, "AN/APX-127(V)1", "a nờ a pê ích một hai bảy vê một"),
    # preserve keeps the 0.10.0 behaviour: acronyms and document symbols stay as written.
    (PRESERVE, "GDP, AI và số 02/NQ-CP", "GDP, AI và số 02/NQ-CP"),
    (NO_FROM, "tăng 20%-30%, giá 20k-30k đồng",
     "tăng hai mươi phần trăm đến ba mươi phần trăm, giá hai mươi nghìn đồng đến ba mươi nghìn đồng"),
])
def test_other_policies(policy, text, expected):
    normalizer = Normalizer(NormalizerConfig(**policy))
    out = normalizer.normalize(text)
    assert out == expected
    assert normalizer.normalize(out) == out


def test_usd_reading_can_be_overridden():
    assert Normalizer(NormalizerConfig(unit_overrides={"USD": "đô la"})).normalize("5 USD") == "năm đô la"


@pytest.mark.parametrize("token,expected", [
    ("GDP", "spell"), ("GII", "spell"), ("WHO", "spell"), ("CEO", "spell"), ("MOL", "spell"),
    ("OECD", "spell"), ("CSIS", "spell"), ("CLMV", "spell"), ("IAEA", "spell"), ("EVFTA", "spell"),
    ("CPTPP", "spell"), ("FOMC", "spell"), ("IRGC", "spell"), ("JETP", "spell"), ("LTPO", "spell"),
    ("IMEI", "spell"), ("ICAO", "spell"), ("AWS", "spell"), ("ĐH", "spell"), ("BCĐ", "spell"),
    ("IT", "spell"), ("UN", "spell"), ("IP", "spell"), ("XE", "spell"), ("BA", "spell"),  # read as Vietnamese words otherwise
    ("AI", "keep"), ("LG", "keep"), ("EU", "keep"), ("SK", "keep"), ("UK", "keep"), ("BRICS", "keep"), ("JAMSTEC", "keep"),
    ("POWERR", "keep"), ("ASIA", "keep"), ("WIPO", "keep"), ("AMOLED", "keep"), ("KAIST", "keep"),
    ("IELTS", "keep"), ("HIMARS", "keep"), ("MAHA", "keep"), ("DOGE", "keep"), ("NVIDIA", "keep"),
    ("TOP", "keep"), ("HOT", "keep"), ("NEWS", "keep"), ("XIV", "keep"), ("U.S.", "keep"),
])
def test_classify_acronym(token, expected):
    from vietnamese_tts_normalizer.acronyms import classify_acronym
    assert classify_acronym(token) == expected


def test_spelled_acronym_does_not_protect_sentence_period():
    text = "Tăng trưởng G D P. Năm nay tăng."
    assert text.index("P.") + 1 not in initial_periods(text)
    assert initial_periods("Ông Donald J. Trump nói.")
    assert initial_periods("Nhà văn J. R. R. Tolkien viết.")


@pytest.mark.parametrize("mode,expected", [("latin", "G D P"), ("spell", "gờ đê pê"), ("preserve", "GDP")])
def test_cli_acronym_modes(mode, expected):
    env = dict(os.environ)
    result = subprocess.run([sys.executable, "-m", "vietnamese_tts_normalizer", "--acronyms", mode, "GDP"],
                            capture_output=True, text=True, env=env, check=True)
    assert result.stdout.strip() == expected
