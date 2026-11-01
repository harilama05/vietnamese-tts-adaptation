"""News expectations and interactions; examples are synthetic, not factual news."""

import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

from vietnamese_tts_normalizer import Normalizer, NormalizerConfig
from vietnamese_tts_normalizer.config import DOMAIN_NAMES

ROOT = Path(__file__).resolve().parents[1]
CASES = json.loads((ROOT / 'tests/data/news.json').read_text(encoding='utf-8'))['cases']


@pytest.mark.parametrize('case', CASES, ids=lambda row: row['id'])
def test_news_fixture(case):
    n = Normalizer(NormalizerConfig(**case['config']))
    result = n.normalize_with_trace(case['input'])
    assert result.text in case['accepted_readings']
    assert n.normalize(case['input']) == result.text
    assert n.normalize(result.text) == result.text
    end, parts = 0, []
    for span in result.spans:
        assert result.source[span.start:span.end] == span.source
        assert span.start >= end
        parts += [result.source[end:span.start], span.spoken]
        end = span.end
    parts.append(result.source[end:])
    assert ''.join(parts) == result.text


def test_news_can_be_disabled_or_used_alone():
    source = 'nhóm G7; GDP; PM2.5; Giá 20k'
    n = Normalizer(NormalizerConfig(enabled_domains=['news']))
    assert n.normalize(source) == 'nhóm gờ bảy; G D P; pê mờ hai chấm năm; Giá 20k'
    disabled = Normalizer(NormalizerConfig(enabled_domains=[d for d in DOMAIN_NAMES if d != 'news']))
    assert disabled.normalize(source) == 'nhóm gờ bảy; G D P; P M hai chấm năm; Giá hai mươi nghìn đồng'


@pytest.mark.parametrize('cue, body', [
    ('nhóm', 'G7'), ('tháng', '6–8/2026'), ('quý', 'I–II/2026'),
    ('nhiệm kỳ', '2026–2031'), ('gió cấp', '6–7'), ('lãi suất giảm', '25 bps'),
])
@pytest.mark.parametrize('separator', ['. ', '; ', '\n'])
def test_news_context_stays_inside_a_clause(cue, body, separator):
    result = Normalizer().normalize_with_trace(cue + separator + body)
    assert not any(s.kind.startswith('domain_news_') for s in result.spans)


def test_identifier_and_control_spans_win_over_news_tokens():
    n = Normalizer()
    source = 'mã sản phẩm VN30; `USD 20/thùng`; [GDP]; PM2.5'
    result = n.normalize_with_trace(source)
    assert result.text == 'mã sản phẩm V N ba không; `USD 20/thùng`; [GDP]; pê mờ hai chấm năm'
    assert [s.source for s in result.spans if s.kind.startswith('domain_news_')] == ['PM2.5']


def test_news_profile_locale_is_explicit():
    config = NormalizerConfig(**json.loads((ROOT / 'profiles/news.json').read_text(encoding='utf-8')))
    assert Normalizer(config).normalize('1.234 người; USD 1.234/thùng') == (
        'một nghìn hai trăm ba mươi tư người; một nghìn hai trăm ba mươi tư đô la Mỹ trên thùng'
    )
    assert Normalizer().normalize('1.234 người') == 'một nghìn hai trăm ba mươi tư người'
    assert Normalizer(NormalizerConfig(ambiguous_number='preserve')).normalize('USD 1.234/thùng') == 'USD 1.234/thùng'
    assert Normalizer().normalize('USD 1.234/thùng') == 'một nghìn hai trăm ba mươi tư đô la Mỹ trên thùng'


def test_cli_news_config_and_trace():
    proc = subprocess.run([sys.executable, '-m', 'vietnamese_tts_normalizer', '--domains', 'news',
                           '--explain', 'nhóm G7; USD 20/thùng'], capture_output=True, text=True, check=True)
    result = json.loads(proc.stdout)
    assert result['text'] == 'nhóm gờ bảy; hai mươi đô la Mỹ trên thùng'
    assert all(s['reason'] == 'context_news' for s in result['spans'])


def test_mixed_news_is_stable_across_reading_policies():
    rng = random.Random(23092026)
    atoms = [r['input'] for r in CASES]
    for cfg in (NormalizerConfig(), NormalizerConfig(number_locale='vi'),
                NormalizerConfig(acronym_mode='spell'), NormalizerConfig(enabled_domains=[])):
        n = Normalizer(cfg)
        for _ in range(70):
            raw = '; '.join(rng.sample(atoms, 4))
            result = n.normalize(raw)
            assert n.normalize(result) == result, (cfg, raw, result, n.normalize(result))


def test_news_resource_limits_and_long_plain_text():
    code = '''from vietnamese_tts_normalizer import Normalizer
n=Normalizer()
for raw in ['USD '+('1'*50000)+'/thùng', 'nhóm G'+('7'*50000), 'nhiệm kỳ '+('1'*50000)+'–2026']:
    result=n.normalize_with_trace(raw)
    assert result.text==raw
    assert result.spans[0].reason=='resource_limit'
text=('Bản tin thời sự. '*6000)+'nhóm G7'
assert n.normalize(text).endswith('nhóm gờ bảy')
'''
    subprocess.run([sys.executable, '-c', code], capture_output=True, text=True, check=True, timeout=20)


@pytest.mark.parametrize('source, expected', [
    ('GDP năm 2026', 'G D P năm hai nghìn không trăm hai mươi sáu'),
    ('CPI một tháng', 'C P I một tháng'),
    ('GDP-123', 'G D P một hai ba'),
    ('WHO-01', 'W H O không một'),
])
def test_news_terms_and_code_prefixes_have_distinct_readings(source, expected):
    n = Normalizer()
    assert n.normalize(source) == expected
    assert n.normalize(expected) == expected


@pytest.mark.parametrize('source, expected', [
    ('GDP năm 2026', 'tổng sản phẩm trong nước năm hai nghìn không trăm hai mươi sáu'),
    ('CPI một tháng', 'chỉ số giá tiêu dùng một tháng'),
    ('tổ chức WHO', 'tổ chức Y tế Thế giới'),
])
def test_news_dictionary_readings_remain_available_with_legacy_policy(source, expected):
    # abbreviation_policy="extended" restores the 0.9.x soe-vinorm + news dictionary coverage.
    n = Normalizer(NormalizerConfig(abbreviation_policy='extended', acronym_mode='preserve'))
    assert n.normalize(source) == expected
    assert n.normalize(expected) == expected
