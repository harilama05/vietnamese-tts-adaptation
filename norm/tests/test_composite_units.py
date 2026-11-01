"""Composed rates, currency policy, and alphanumeric override regressions."""

import json
from pathlib import Path

import pytest

from vietnamese_tts_normalizer import Normalizer, NormalizerConfig


@pytest.mark.parametrize("unit, spoken", [
    ("USD", "đô la Mỹ"), ("$", "đô la"), ("EUR", "ơ rô"),
    ("đ", "đồng"), ("VND", "đồng"), ("kg", "ki lô gam"),
])
@pytest.mark.parametrize("container", ["thùng", "chai", "hộp", "bao", "kiện", "gói", "ly"])
def test_units_compose_with_count_denominators(unit, spoken, container):
    n = Normalizer()
    source = f"2–3 {unit}/{container}"
    expected = f"từ hai đến ba {spoken} trên {container}"
    result = n.normalize_with_trace(source)
    assert result.text == expected
    assert n.normalize(result.text) == result.text
    assert len(result.spans) == 1
    assert result.spans[0].source == source
    assert result.spans[0].status == "expanded"


@pytest.mark.parametrize("source, expected", [
    ("83,75–83,88 USD/thùng",
     "từ tám mươi ba phẩy bảy mươi lăm đến tám mươi ba phẩy tám mươi tám đô la Mỹ trên thùng"),
    ("80,87–81,15 USD/thùng",
     "từ tám mươi phẩy tám mươi bảy đến tám mươi mốt phẩy mười lăm đô la Mỹ trên thùng"),
    ("83,75 USD/thùng", "tám mươi ba phẩy bảy mươi lăm đô la Mỹ trên thùng"),
    ("83.75 - 83.88 USD / thùng",
     "từ tám mươi ba phẩy bảy mươi lăm đến tám mươi ba phẩy tám mươi tám đô la Mỹ trên thùng"),
    ("50.000–60.000đ/chai", "từ năm mươi nghìn đến sáu mươi nghìn đồng trên chai"),
    ("5 kg / bao / ngày", "năm ki lô gam trên bao trên ngày"),
    ("Giá 20k/thùng", "Giá hai mươi nghìn đồng trên thùng"),
    ("Giá 20k/chai/ngày", "Giá hai mươi nghìn đồng trên chai trên ngày"),
    ("Giá 20–30k/hộp", "Giá từ hai mươi nghìn đồng đến ba mươi nghìn đồng trên hộp"),
    ("2 kg/(bao*ngày)", "hai ki lô gam trên mở ngoặc bao nhân ngày đóng ngoặc"),
])
def test_rate_forms(source, expected):
    n = Normalizer()
    assert n.normalize(source) == expected
    assert n.normalize(expected) == expected


@pytest.mark.parametrize("source", [
    "USD/VND", "5 USD/VND", "83,75 USD/thùngXYZ",
    "83,75 USD/thùng^2", "83,75 USD/thùng/unknown",
    "83,75 usd/thùng", "5 kg/unknown", "Giá 20k/unknown",
])
def test_default_preservation(source):
    assert Normalizer().normalize(source) == source


@pytest.mark.parametrize("source, expected", [
    ("E4", "e bốn"), ("E40", "e bốn mươi"), ("5G", "năm gờ"),
    ("iPhone15", "iPhone mười lăm"), ("H2O", "hắt hai ô"),
])
def test_alphanumeric_codes_are_read_by_component(source, expected):
    n = Normalizer()
    assert n.normalize(source) == expected
    assert n.normalize(expected) == expected


def test_currency_and_atom_overrides_apply_inside_rates():
    n = Normalizer(NormalizerConfig(dollar_name="đô la Mỹ"))
    assert n.normalize("2 USD/chai; 2 $/hộp; USD2") == (
        "hai đô la Mỹ trên chai; hai đô la Mỹ trên hộp; hai đô la Mỹ"
    )
    n = Normalizer(NormalizerConfig(
        decimal_reading="cardinal", dollar_name="đô la Mỹ",
        unit_overrides={"USD": "đô la", "bao": "bao hàng"},
    ))
    assert n.normalize("83,75 USD/bao") == "tám mươi ba phẩy bảy mươi lăm đô la trên bao hàng"
    n = Normalizer(NormalizerConfig(unit_overrides={"EUR/kiện": "ơ rô mỗi kiện"}))
    assert n.normalize("2 EUR/kiện") == "hai ơ rô mỗi kiện"


def test_alphanumeric_override_respects_token_and_protected_boundaries():
    # A marked reading proves the override matched only the whole token "E4";
    # E40, XE4, E4X and E4-01 use the ordinary alphanumeric reader instead.
    n = Normalizer(NormalizerConfig(enabled_domains=[], abbreviation_overrides={"E4": "ê bốn riêng"}))
    source = "Các nước E4; E40; XE4; E4X; E4-01; e4; [E4]; `E4`; https://example.vn/E4"
    expected = "Các nước ê bốn riêng; e bốn mươi; X E bốn; e bốn ích; e bốn không một; e4; [E4]; `E4`; https://example.vn/E4"
    result = n.normalize_with_trace(source)
    assert result.text == expected
    assert result.text.count("ê bốn riêng") == 1
    assert n.normalize(expected) == expected
    span = next(s for s in result.spans if s.source == "E4" and s.status == "expanded")
    assert span.kind == "compound"
    assert result.source[span.start:span.end] == "E4"


def test_news_profile_on_excerpt():
    path = Path(__file__).resolve().parents[1] / "profiles/text07.json"
    n = Normalizer(NormalizerConfig(**json.loads(path.read_text(encoding="utf-8"))))
    source = ("Brent xuống 83,75–83,88 USD/thùng và WTI xuống 80,87–81,15 USD/thùng. "
              "Các nước E4 (Anh, Pháp, Đức, Ý).")
    expected = ("Brent xuống tám mươi ba phẩy bảy mươi lăm đến tám mươi ba phẩy tám mươi tám đô la Mỹ trên thùng "
                "và vê kép tê i xuống tám mươi phẩy tám mươi bảy đến tám mươi mốt phẩy mười lăm đô la Mỹ trên thùng. "
                "Các nước e bốn (Anh, Pháp, Đức, Ý).")
    assert n.normalize(source) == expected
    assert n.normalize(expected) == expected


@pytest.mark.parametrize("source, expected", [
    ("USD/thùng", "đô la Mỹ trên thùng"),
    ("EUR / kiện", "ơ rô trên kiện"),
    ("$/chai", "đô la trên chai"),
    ("đ/hộp", "đồng trên hộp"),
    ("kg/bao/ngày", "ki lô gam trên bao trên ngày"),
    ("m²/người", "mét vuông trên người"),
    ("kg/m³", "ki lô gam trên mét khối"),
    ("mg/dL", "mi li gam trên đề xi lít"),
    ("Đơn vị: USD / thùng.", "Đơn vị: đô la Mỹ trên thùng."),
])
def test_standalone_composite_units(source, expected):
    n = Normalizer()
    assert n.normalize(source) == expected
    assert n.normalize(expected) == expected


@pytest.mark.parametrize("source", [
    "USD/thùng / unknown", "USD / VND", "kg / unknown", "USD/thùngX",
    "USD/thùng^2", "USD/thùng/unknown", "ABC/DEF",
    "[USD/thùng]", "`USD/thùng`", "https://example.vn/USD/thùng",
])
def test_standalone_units_keep_unknown_or_protected_structures(source):
    assert Normalizer().normalize(source) == source
