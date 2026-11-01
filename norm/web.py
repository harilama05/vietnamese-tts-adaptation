"""Spoken domain names (link_mode="domain", the default): chinhphu.vn -> chính phủ chấm vi en.

A bare domain in running text, such as a source or a photo credit, is read aloud. Each label
is read, in this order:
1. as a known site name (vnexpress);
2. as Vietnamese words when it is Vietnamese written without diacritics (chinhphu, dichvucong,
   quangninh), split into dictionary words and given back their diacritics;
3. as toneless Vietnamese syllables when every part is a valid syllable (tinhte -> tinh te);
4. as a word when it is pronounceable (google, info);
5. letter by letter otherwise (vtv, qdnd).
Digits in a label are read as a number (kenh14). An author or photographer credit after the
domain (Ảnh: chinhphu.vn/TG) is not read. Full URLs (scheme, path, query) and e-mail
addresses keep link_mode's protection.
"""

import re
import unicodedata
from functools import lru_cache

from .acronyms import is_pronounceable
from .lexicon import latin_letters
from .numbers import read_digits, read_integer
from . import vi_abbreviations as vi

TLDS = "com|net|org|vn|io|edu|gov|info|dev|ai"
# A bare domain, optionally followed by a credit of capitals: chinhphu.vn, dantri.com.vn, chinhphu.vn/TG.
BARE_DOMAIN = re.compile(rf"(?i:((?:www\.)?(?:[a-z0-9-]+\.)+(?:{TLDS})))(?:/[A-ZĐ]{{1,6}})?")
SUFFIXES = {"vn": "vi en", "com": "com", "net": "nét", "edu": "e đu", "www": "vê kép vê kép vê kép"}
SITES = {
    "vnexpress": "vi en express", "vietnamnet": "việt nam nét", "vietnamplus": "việt nam plus",
    "zingnews": "zing news", "baomoi": "báo mới", "cafef": "ca phê ép", "cafebiz": "ca phê biz",
    "tphcm": "thành phố hồ chí minh", "hochiminhcity": "hồ chí minh city",
}
# Vietnamese words and phrases that site and portal names are made of (comma separated); a name is
# split into these and given back its diacritics. Two- and three-word runs of the abbreviation
# readings add the official terms (tư pháp, công thương, dịch vụ công trực tuyến).
WORDS = """
báo, tin, tin tức, mới, tin mới, thời báo, tạp chí, điện tử, trực tuyến, đài, truyền hình, phát thanh, tiếng nói,
thông tấn, thông tin, cổng, cổng thông tin, dân trí, dân việt, tuổi trẻ, thanh niên, tiền phong, nhân dân, lao động,
người lao động, pháp luật, sức khỏe, đời sống, giáo dục, thời đại, kinh tế, đô thị, an ninh, thủ đô, phụ nữ,
gia đình, văn hóa, thể thao, du lịch, giải trí, công lý, đại đoàn kết, nông thôn, nông nghiệp, môi trường, khoa học,
công nghệ, doanh nghiệp, doanh nhân, đầu tư, chứng khoán, tài chính, ngân hàng, bất động sản, xây dựng, giao thông,
hải quan, thuế, kho bạc, bảo hiểm, xã hội, dịch vụ công, chính phủ, quốc hội, công an, quân đội, biên phòng,
hải quân, bộ, sở, tỉnh, thành phố, huyện, quận, việt nam, hà nội mới, sài gòn, giải phóng, kênh, cẩm nang, mua sắm,
nhà đất, an giang, bà rịa vũng tàu, bắc giang, bắc kạn, bạc liêu, bắc ninh, bến tre, bình định, bình dương,
bình phước, bình thuận, cà mau, cần thơ, cao bằng, đà nẵng, đắk lắk, đắk nông, điện biên, đồng nai, đồng tháp,
gia lai, hà giang, hà nam, hà nội, hà tĩnh, hải dương, hải phòng, hậu giang, hòa bình, hưng yên, khánh hòa,
kiên giang, kon tum, lai châu, lâm đồng, lạng sơn, lào cai, long an, nam định, nghệ an, ninh bình, ninh thuận,
phú thọ, phú yên, quảng bình, quảng nam, quảng ngãi, quảng ninh, quảng trị, sóc trăng, sơn la, tây ninh,
thái bình, thái nguyên, thanh hóa, thừa thiên huế, huế, tiền giang, hồ chí minh, trà vinh, tuyên quang,
vĩnh long, vĩnh phúc, yên bái, thư viện, pháp lý, thế giới, nhịp sống, người đưa tin, đưa tin, bóng đá, người việt,
việt báo, ô tô, xe, nhà, đất, kiểm toán, thanh tra, tòa án, viện kiểm sát, điện lực, dầu khí, hàng không, đường sắt,
bưu điện, viễn thông, y tế, thời sự, thời tiết, sân khấu, điện ảnh, âm nhạc, nghệ thuật, phim, sách, học, đại học,
học viện, trường, ngoại ngữ, tuyển sinh, việc làm, tuyển dụng, nhân lực, chợ, giá, vàng, xăng dầu, điện, nước
"""
# English words and brand names common in site names, read as written (net as Vietnamese say it).
ENGLISH = {word: word for word in """online news plus express times today life city group media tech shop store bank
info global world digital live star zing portal gov youtube facebook google tiktok zalo shopee lazada tiki sendo momo
openai apple microsoft amazon netflix twitter instagram grab vinfast viettel vinamilk vietjet vietcombank techcombank
vpbank mbbank""".split()}
ENGLISH["net"] = "nét"


def unaccent(text: str) -> str:
    """chính phủ -> chinhphu: no diacritics, no spaces, đ -> d, lower case."""
    decomposed = unicodedata.normalize("NFD", text.replace("đ", "d").replace("Đ", "D"))
    return re.sub(r"[^a-z0-9]", "", "".join(c for c in decomposed if not unicodedata.combining(c)).lower())


@lru_cache(maxsize=1)
def _dictionary() -> dict:
    """Unaccented key -> reading; a key with two different readings is left out."""
    entries = [entry.strip() for entry in WORDS.replace("\n", " ").split(",") if entry.strip()]
    for reading in {*vi.ALWAYS.values(), *vi.SECTORS.values()}:
        words = re.findall(r"[^\W\d_]+", reading.lower())
        entries += [" ".join(words[i:i + n]) for n in (2, 3) for i in range(len(words) - n + 1)]
    readings = {}
    for entry in entries:
        key = unaccent(entry)
        if len(key) >= 2:
            readings.setdefault(key, set()).add(entry.lower())
    dictionary = {key: next(iter(values)) for key, values in readings.items() if len(values) == 1}
    dictionary.update(ENGLISH)
    return dictionary


_ONSET = r"(?:ngh|ng|nh|ch|gh|gi|kh|ph|qu|th|tr|[bcdghklmnprstvx])?"
_RHYME = (r"(?:uyen|uyet|uynh|uych|uong|uoc|uoi|uon|uot|ieng|ieu|iem|ien|iep|iet|yeu|yen|yet|oanh|oang|oach|"
          r"oai|oan|oat|oay|oac|oen|oet|anh|ang|ach|ai|ao|au|ay|an|ac|am|ap|at|eo|en|eng|em|ep|et|ec|inh|ich|ia|iu|"
          r"in|im|ip|it|ong|oc|oi|on|om|op|ot|oa|oe|ung|uc|ua|uan|uat|uay|ue|ui|um|un|up|ut|uy|a|e|i|o|u|y)")
_SYLLABLE = re.compile(rf"{_ONSET}{_RHYME}")


def _split(label: str, piece_reading):
    """Cheapest split of `label`; piece_reading(piece) gives (cost, reading) or None."""
    best = [None] * (len(label) + 1)
    best[0] = (0, [])
    for end in range(1, len(label) + 1):
        for start in range(max(0, end - 24), end):
            if best[start] is None:
                continue
            piece = piece_reading(label[start:end])
            if piece is not None and (best[end] is None or best[start][0] + piece[0] < best[end][0]):
                best[end] = (best[start][0] + piece[0], best[start][1] + [piece[1]])
    return best[-1][1] if best[-1] else None


def _segment(label: str, dictionary: dict):
    """Vietnamese words of a label written without diacritics, or None.

    Dictionary words only: chinhphu -> chính phủ, baochinhphu -> báo chính phủ. Otherwise
    multi-word dictionary entries mixed with toneless syllables read as written
    (thuvienphapluat -> thư viện pháp luật, tinhte -> tinh te); a toneless syllable has at
    least two letters and the split needs a consonant onset, so English names (openai,
    youtube) are not cut into Vietnamese syllables.
    """
    words = _split(label, lambda piece: (1, dictionary[piece]) if piece in dictionary else None)
    if words:
        return words

    def mixed(piece):
        if piece in dictionary and " " in dictionary[piece]:
            return 1, dictionary[piece]
        return (2, piece) if len(piece) >= 2 and _SYLLABLE.fullmatch(piece) else None

    words = _split(label, mixed)
    if words and len(words) > 1 and any(" " in word or re.match(r"[bcdghklmnpqrstvx]", word) for word in words):
        return words
    return None


def read_label(label: str) -> str:
    """One label of a domain name."""
    lower = label.lower()
    if lower in SITES:
        return SITES[lower]
    parts = re.findall(r"[a-z]+|[0-9]+", lower)
    if len(parts) > 1 or (parts and parts[0].isdigit()):
        return " ".join(read_label(part) if part.isalpha() else
                        (read_integer(part) if len(part) <= 3 else read_digits(part)) for part in parts)
    words = _segment(lower, _dictionary())
    if words:
        reading = " ".join(words)
        return label if reading == lower else reading  # YouTube, America stay as written
    if len(lower) > 2 and is_pronounceable(lower.upper()):
        return label
    return latin_letters(lower)


def read_domain(raw: str):
    """The spoken form of a bare domain (credit dropped), or None for anything else."""
    match = BARE_DOMAIN.fullmatch(raw)
    if match is None:
        return None
    labels = match[1].split(".")
    spoken = [SUFFIXES.get(label.lower()) or read_label(label) if index or label.lower() == "www"
              else read_label(label) for index, label in enumerate(labels)]
    return " chấm ".join(part for part in spoken)
