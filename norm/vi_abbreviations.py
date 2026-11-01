"""Vietnamese abbreviations read by meaning, the way a newsreader says them aloud.

A Vietnamese initialism is expanded (TTXVN -> Thông tấn xã Việt Nam), and a
cluster of them is read as the name it abbreviates, whatever the separators:
VH-TT-DL, VH,TT&DL and VHTTDL all read "Văn hóa, Thể thao và Du lịch".
Short forms are ambiguous on their own (TC, BN, HS), so they are read only in a
context that fixes their meaning:

    SECTORS     ministry/department names after Bộ, Sở, Phòng, ngành (Bộ TC -> Bộ Tài chính),
                and with a B/S prefix (BGDĐT -> Bộ Giáo dục và Đào tạo)
    ALWAYS      wherever the token stands alone (never inside a document symbol or code)
    CONTEXTUAL  ordered (context, reading) pairs: BV Bạch Mai, BN 123, 3 HCV, các HS
    COMPONENTS  cluster parts with one meaning, for unlisted clusters (KT-XH-QP-AN)

Foreign acronyms (GDP, CEO, BTS, SK) are not listed; they keep the latin policy. Forms that
are also stock tickers or foreign names (HSG, KDC, NCT, HSV) are left out on purpose.
Readings contain no digits and no runs of capitals, so a second pass leaves them alone.
"""

import bisect
import re

from .acronyms import VIETNAMESE

UPPER = "A-ZĐÀÁẢÃẠĂẰẮẲẴẶÂẦẤẨẪẬÈÉẺẼẸÊỀẾỂỄỆÌÍỈĨỊÒÓỎÕỌÔỒỐỔỖỘƠỜỚỞỠỢÙÚỦŨỤƯỪỨỬỮỰỲÝỶỸỴ"
# Separators inside a cluster: VH-TT-DL, VH,TT&DL, GD & ĐT, CNH, HĐH.
CLUSTER_SEPARATORS = re.compile(r"[ \t]*[&+][ \t]*|[ \t]*[,;][ \t]*|[ \t]*[-–][ \t]*|[ \t]+")


def cluster_key(form: str) -> str:
    """Letters only: every separator variant of a cluster shares one key."""
    return CLUSTER_SEPARATORS.sub("", form)


def _table(text: str) -> dict:
    """'FORM | FORM = reading' lines; '#' starts a comment."""
    table = {}
    for line in text.splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        forms, reading = (part.strip() for part in line.split("=", 1))
        for form in forms.split("|"):
            table[form.strip()] = reading
    return table


# Ministries and departments. After a head word (Bộ, Sở, Phòng, ngành) every
# entry applies; standalone, only keys of four letters or more (TNMT, GDĐT).
SECTORS = _table("""
VH-TT-DL | VH,TT&DL | VHTT&DL | VH-TT&DL | VHTTDL = Văn hóa, Thể thao và Du lịch
VH&TT | VHTT = Văn hóa và Thể thao
GD&ĐT | GD-ĐT | GDĐT = Giáo dục và Đào tạo
KH&CN | KH-CN = Khoa học và Công nghệ
KH&ĐT | KH-ĐT | KHĐT = Kế hoạch và Đầu tư
TT&TT | TT-TT | TTTT = Thông tin và Truyền thông
TN&MT | TN-MT | TNMT = Tài nguyên và Môi trường
NN&PTNT | NN-PTNT | NNPTNT = Nông nghiệp và Phát triển nông thôn
NN&MT | NN-MT | NNMT = Nông nghiệp và Môi trường
LĐ-TB&XH | LĐTB&XH | LĐ-TBXH | LĐ-TB-XH | LĐTBXH = Lao động - Thương binh và Xã hội
DT&TG | DT-TG | DTTG = Dân tộc và Tôn giáo
GTVT = Giao thông vận tải
KHCN = Khoa học và Công nghệ
TC = Tài chính
CT = Công Thương
XD = Xây dựng
YT = Y tế
TP = Tư pháp
QP = Quốc phòng
CA = Công an
NG = Ngoại giao
NV = Nội vụ
GD = Giáo dục
VH = Văn hóa
NN = Nông nghiệp
LĐ = Lao động
DL = Du lịch
""")
# Bộ/Sở + a sector of two letters is listed explicitly; BTC (Ban tổ chức, bitcoin)
# and BCT (Bộ Chính trị, Bộ Công Thương) are ambiguous and stay spelled.
_HEADED = _table("""
BYT = Bộ Y tế
SYT = Sở Y tế
BXD = Bộ Xây dựng
SXD = Sở Xây dựng
BQP = Bộ Quốc phòng
BCA = Bộ Công an
BNG = Bộ Ngoại giao
BTP = Bộ Tư pháp
STP = Sở Tư pháp
BNV = Bộ Nội vụ
SCT = Sở Công Thương
STC = Sở Tài chính
""")

ALWAYS = dict(VIETNAMESE)
ALWAYS.update(_HEADED)
ALWAYS.update(_table("""
# Đảng, Nhà nước, Mặt trận, đoàn thể
BCH = Ban Chấp hành
BCHTW | BCHTƯ = Ban Chấp hành Trung ương
UVBCH = Ủy viên Ban Chấp hành
UVTW | UVTƯ = Ủy viên Trung ương
UVBCT = Ủy viên Bộ Chính trị
UVBTV = Ủy viên Ban Thường vụ
UBKT = Ủy ban Kiểm tra
UBKTTW | UBKTTƯ = Ủy ban Kiểm tra Trung ương
BCĐ = Ban Chỉ đạo
BCĐTW | BCĐTƯ = Ban Chỉ đạo Trung ương
BTGTW | BTGTƯ = Ban Tuyên giáo Trung ương
BTCTW | BTCTƯ = Ban Tổ chức Trung ương
BNCTW | BNCTƯ = Ban Nội chính Trung ương
BDVTW | BDVTƯ = Ban Dân vận Trung ương
BĐNTW | BĐNTƯ = Ban Đối ngoại Trung ương
ĐCSVN = Đảng Cộng sản Việt Nam
ĐCS = Đảng Cộng sản
ĐCSTQ = Đảng Cộng sản Trung Quốc
CSVN = Cộng sản Việt Nam
VPQH = Văn phòng Quốc hội
VPCP = Văn phòng Chính phủ
VPCTN = Văn phòng Chủ tịch nước
TTCP = Thanh tra Chính phủ
UBDT = Ủy ban Dân tộc
MTTQVN = Mặt trận Tổ quốc Việt Nam
UBMTTQVN = Ủy ban Mặt trận Tổ quốc Việt Nam
HĐBA = Hội đồng Bảo an
HĐBALHQ = Hội đồng Bảo an Liên Hợp Quốc
CHXHCNVN = Cộng hòa xã hội chủ nghĩa Việt Nam
CHDCND = Cộng hòa Dân chủ Nhân dân
CHND = Cộng hòa Nhân dân
CHLB = Cộng hòa Liên bang
CNXH = chủ nghĩa xã hội
CNH = công nghiệp hóa
HĐH = hiện đại hóa
CNH-HĐH | CNH, HĐH = công nghiệp hóa, hiện đại hóa
KT-XH | KTXH = kinh tế - xã hội
QP-AN | QPAN = quốc phòng - an ninh
AN-QP | ANQP = an ninh - quốc phòng
ANTT = an ninh trật tự
ANQG = an ninh quốc gia
TTATXH = trật tự an toàn xã hội
TTATGT = trật tự an toàn giao thông
VSATTP = vệ sinh an toàn thực phẩm
ATVSTP = an toàn vệ sinh thực phẩm
ATVSLĐ = an toàn vệ sinh lao động
ATLĐ = an toàn lao động
CNCH = cứu nạn cứu hộ
PCCC&CNCH = phòng cháy chữa cháy và cứu nạn cứu hộ
TKCN = tìm kiếm cứu nạn
PCTT = phòng chống thiên tai
PCTT&TKCN = phòng chống thiên tai và tìm kiếm cứu nạn
PCLB = phòng chống lụt bão
CCHC = cải cách hành chính
TTHC = thủ tục hành chính
DVCTT = dịch vụ công trực tuyến
CĐS = chuyển đổi số
CSDL = cơ sở dữ liệu
NTM = nông thôn mới
XĐGN = xóa đói giảm nghèo
GNBV = giảm nghèo bền vững
BĐKH = biến đổi khí hậu
ASXH = an sinh xã hội
CSXH = chính sách xã hội
LĐLĐ = Liên đoàn Lao động
TLĐLĐVN = Tổng Liên đoàn Lao động Việt Nam
LHPN = Liên hiệp Phụ nữ
HLHPN = Hội Liên hiệp Phụ nữ
HLHPNVN = Hội Liên hiệp Phụ nữ Việt Nam
ĐTN = Đoàn Thanh niên
ĐTNCS = Đoàn Thanh niên Cộng sản
TNCS = Thanh niên Cộng sản
TNTP = Thiếu niên Tiền phong
HCCB = Hội Cựu chiến binh
CCB = cựu chiến binh
ĐVTN = đoàn viên thanh niên
TNXP = thanh niên xung phong
TNV = tình nguyện viên
CTĐ = Chữ thập đỏ
NKT = người khuyết tật
NLĐ = người lao động
NSDLĐ = người sử dụng lao động
HĐLĐ = hợp đồng lao động
XKLĐ = xuất khẩu lao động
CBCC = cán bộ, công chức
CBCCVC = cán bộ, công chức, viên chức
CBCNV = cán bộ công nhân viên
CBNV = cán bộ nhân viên
CNVC = công nhân viên chức
CNVCLĐ = công nhân viên chức lao động
HKTT = hộ khẩu thường trú
GCN = giấy chứng nhận
GCNQSDĐ = giấy chứng nhận quyền sử dụng đất
QSDĐ = quyền sử dụng đất
VBQPPL = văn bản quy phạm pháp luật
BHXHVN = Bảo hiểm Xã hội Việt Nam
# Kinh tế, doanh nghiệp, tài chính
KCX = khu chế xuất
KKT = khu kinh tế
CCN = cụm công nghiệp
KCNC = khu công nghệ cao
KĐT = khu đô thị
TĐC = tái định cư
GPMB = giải phóng mặt bằng
BQL = Ban Quản lý
BQLDA = Ban Quản lý dự án
BGĐ = Ban Giám đốc
BGH = Ban Giám hiệu
BGK = Ban Giám khảo
ĐHĐCĐ = Đại hội đồng cổ đông
HĐTV = hội đồng thành viên
TGĐ = tổng giám đốc
PTGĐ = phó tổng giám đốc
GĐ = giám đốc
PGĐ = phó giám đốc
KTT = kế toán trưởng
CTHĐQT = chủ tịch hội đồng quản trị
DNNN = doanh nghiệp nhà nước
DNTN = doanh nghiệp tư nhân
DNNVV = doanh nghiệp nhỏ và vừa
DNVVN = doanh nghiệp vừa và nhỏ
HTX = hợp tác xã
NHNN = Ngân hàng Nhà nước
NHTM = ngân hàng thương mại
NHTMCP = ngân hàng thương mại cổ phần
TMCP = thương mại cổ phần
NHCSXH = Ngân hàng Chính sách xã hội
TCTD = tổ chức tín dụng
UBCKNN = Ủy ban Chứng khoán Nhà nước
TTCK = thị trường chứng khoán
CTCK = công ty chứng khoán
SGDCK = Sở Giao dịch Chứng khoán
KBNN = Kho bạc Nhà nước
NSNN = ngân sách nhà nước
TPCP = trái phiếu chính phủ
TPDN = trái phiếu doanh nghiệp
BCTC = báo cáo tài chính
LNST = lợi nhuận sau thuế
LNTT = lợi nhuận trước thuế
VCSH = vốn chủ sở hữu
VĐL = vốn điều lệ
GTGT = giá trị gia tăng
TNDN = thu nhập doanh nghiệp
TNCN = thu nhập cá nhân
TTĐB = tiêu thụ đặc biệt
XNK = xuất nhập khẩu
SXKD = sản xuất kinh doanh
ĐKKD = đăng ký kinh doanh
GPKD = giấy phép kinh doanh
NĐT = nhà đầu tư
TMĐT = thương mại điện tử
XTTM = xúc tiến thương mại
QLTT = quản lý thị trường
NTD = người tiêu dùng
NDT = nhân dân tệ
# Giao thông, báo chí, văn hóa, thể thao
ĐSVN = Đường sắt Việt Nam
HKVN = Hàng không Việt Nam
HKDD = hàng không dân dụng
TNGT = tai nạn giao thông
TTXVN = Thông tấn xã Việt Nam
TTX = thông tấn xã
CTV = cộng tác viên
PTV = phát thanh viên
BLV = bình luận viên
NGND = nhà giáo nhân dân
NGƯT = nhà giáo ưu tú
TTND = thầy thuốc nhân dân
TTƯT = thầy thuốc ưu tú
NNND = nghệ nhân nhân dân
NNƯT = nghệ nhân ưu tú
AHLĐ = anh hùng lao động
AHLLVTND = anh hùng lực lượng vũ trang nhân dân
LLVT = lực lượng vũ trang
LLVTND = lực lượng vũ trang nhân dân
VHNT = văn học nghệ thuật
DSVH = di sản văn hóa
TDTT = thể dục thể thao
LHP = liên hoan phim
VĐQG = vô địch quốc gia
VCK = vòng chung kết
ĐKVĐ = đương kim vô địch
HCĐ = huy chương đồng
# Giáo dục, khoa học
THPTQG = trung học phổ thông quốc gia
ĐH-CĐ = đại học - cao đẳng
ĐHQGHN = Đại học Quốc gia Hà Nội
ĐHQG-HCM | ĐHQGHCM | ĐHQG-TPHCM = Đại học Quốc gia Thành phố Hồ Chí Minh
ĐHBK = Đại học Bách khoa
ĐHBKHN = Đại học Bách khoa Hà Nội
ĐHSP = Đại học Sư phạm
ĐHKTQD = Đại học Kinh tế Quốc dân
ĐHKHTN = Đại học Khoa học Tự nhiên
ĐHKHXH&NV | ĐHKHXHNV = Đại học Khoa học Xã hội và Nhân văn
KHXH&NV | KHXHNV = Khoa học Xã hội và Nhân văn
KHXH = khoa học xã hội
KHTN = khoa học tự nhiên
GDTX = giáo dục thường xuyên
GDNN = giáo dục nghề nghiệp
GDMN = giáo dục mầm non
GDPT = giáo dục phổ thông
GDCD = giáo dục công dân
GDĐH = giáo dục đại học
SGK = sách giáo khoa
GVCN = giáo viên chủ nhiệm
PHHS = phụ huynh học sinh
HSSV = học sinh, sinh viên
ĐGNL = đánh giá năng lực
ĐGTD = đánh giá tư duy
SBD = số báo danh
NCS = nghiên cứu sinh
NCKH = nghiên cứu khoa học
KTX = ký túc xá
TSKH = tiến sĩ khoa học
KTS = kiến trúc sư
# Y tế
BVĐK = bệnh viện đa khoa
BVTW | BVTƯ = bệnh viện trung ương
TTYT = trung tâm y tế
KCB = khám chữa bệnh
YHCT = y học cổ truyền
SXH = sốt xuất huyết
ĐTĐ = đái tháo đường
HSCC = hồi sức cấp cứu
TTBYT = trang thiết bị y tế
CKI | CK1 = chuyên khoa một
CKII | CK2 = chuyên khoa hai
BSCKI = bác sĩ chuyên khoa một
BSCKII = bác sĩ chuyên khoa hai
# Pháp luật, công an, quân đội
VKSNDTC = Viện kiểm sát nhân dân tối cao
TANDTC = Tòa án nhân dân tối cao
VKS = Viện kiểm sát
HĐXX = hội đồng xét xử
THADS = thi hành án dân sự
BLHS = Bộ luật Hình sự
BLDS = Bộ luật Dân sự
BLTTHS = Bộ luật Tố tụng hình sự
BLTTDS = Bộ luật Tố tụng dân sự
BLLĐ = Bộ luật Lao động
VPHC = vi phạm hành chính
CQĐT = cơ quan điều tra
CQCSĐT = cơ quan cảnh sát điều tra
CSCĐ = cảnh sát cơ động
CSHS = cảnh sát hình sự
CSKT = cảnh sát kinh tế
CSND = cảnh sát nhân dân
CSPCCC = cảnh sát phòng cháy chữa cháy
CATP = Công an thành phố
QĐNDVN = Quân đội nhân dân Việt Nam
BĐBP = Bộ đội Biên phòng
BCHQS = Bộ Chỉ huy Quân sự
PKKQ = phòng không - không quân
# Địa danh, vùng
ĐBSH = đồng bằng sông Hồng
ĐNB = Đông Nam Bộ
TNB = Tây Nam Bộ
BTB = Bắc Trung Bộ
DHMT = duyên hải miền Trung
TDMNPB = trung du và miền núi phía Bắc
ĐNA | ĐNÁ = Đông Nam Á
BR-VT | BRVT = Bà Rịa - Vũng Tàu
TP-HCM | TP.HCM = Thành phố Hồ Chí Minh
TPHN = Thành phố Hà Nội
# Khác
STT = số thứ tự
ĐVT = đơn vị tính
"""))
for _key, _name in SECTORS.items():
    if len(cluster_key(_key)) >= 4 and _key != "KHCN":
        ALWAYS.setdefault(_key, _name)


# Context primitives. `before` is matched at the end of the preceding source text and
# `after` at the start of the following text. `within`/`unless` are field cues searched
# in the same sentence, so a short form is read with the meaning it has in that field:
# CT is a scan in "chụp CT 64 lát cắt", the chairman in "CT UBND tỉnh", a directive in
# "CT 05/CT-TTg". Cues match both the written and the normalized form of a cue
# (UBND / ủy ban, MRI / M R I), so a second pass takes the same decision.
KEEP = ""  # reading: no expansion; the token follows the acronym policy (PV in "tấm pin PV")
LOWER = "a-zđàáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ"
# Sentence ends. The dot of TP., Q., TS. is removed by its reading (TP. Hà Nội -> thành phố
# Hà Nội), so it is not an end: a sentence has the same bounds before and after a pass.
_BOUNDARY = re.compile(r"[.!?…;]+[\"”’)\]]*(?=\s|\Z)|\n")
_PREFIX_DOT = re.compile(r"(?<![^\W\d_])(?:PGS\.TS|GS\.TS|ThS|TS|BS|TP|Tp|TX|TT|Q|P|H)\Z")


def sentence_bounds(text: str) -> tuple:
    """Start and end offsets of the sentence boundaries in `text`."""
    starts, ends = [], []
    for match in _BOUNDARY.finditer(text):
        if match.group() == "." and _PREFIX_DOT.search(text, max(0, match.start() - 8), match.start()):
            continue
        starts.append(match.start())
        ends.append(match.end())
    return starts, ends


def sentence_around(text: str, bounds: tuple, start: int, end: int) -> str:
    """The sentence that holds text[start:end], without that token."""
    starts, ends = bounds
    left = bisect.bisect_right(ends, start)
    right = bisect.bisect_left(starts, end)
    return (text[ends[left - 1] if left else 0:start] + " ¦ "
            + text[end:starts[right] if right < len(starts) else len(text)])


# Joins a cluster written with separators (VH,TT&DL, VH - TT - DL) into its key VHTTDL.
_JOIN = re.compile(r"(?<=[A-ZĐƯ])(?:[ \t]*[&+][ \t]*|[,;]|[ \t]*[-–][ \t]*)(?=[A-ZĐƯ])")


class Field:
    """Cue words of a field (any case) and its abbreviations (exact case).

    `extend` adds the abbreviations whose readings contain a cue word, so a cue is found
    both before and after its own expansion (VH,TT&DL / Du lịch for tourism).
    """

    def __init__(self, words: str, codes: str = ""):
        self.words, self.codes = words, [codes] if codes else []
        self._compile()

    def _compile(self):
        alternatives = "|".join([rf"(?i:{self.words})", *self.codes])
        self.regex = re.compile(rf"(?<![^\W\d_])(?:{alternatives})(?![^\W\d_])")

    def extend(self, keys):
        keys = sorted(set(keys), key=len, reverse=True)
        if keys:
            self.codes.append("|".join(re.escape(key) for key in keys))
            self._compile()

    def search(self, text: str):
        return self.regex.search(text) or self.regex.search(_JOIN.sub("", text))


field = Field


class Context:
    __slots__ = ("before", "after", "within", "unless")

    def __init__(self, before: str = "", after: str = "", within=(), unless=()):
        self.before = re.compile(before + r"\Z") if before else None
        self.after = re.compile(after) if after else None
        self.within = within if isinstance(within, tuple) else (within,)
        self.unless = unless if isinstance(unless, tuple) else (unless,)

    def matches(self, before: str, after: str, sentence=None) -> bool:
        if self.before is not None and not self.before.search(before):
            return False
        if self.after is not None and not self.after.match(after):
            return False
        if self.within or self.unless:
            if sentence is None:
                starts, ends = sentence_bounds(before)
                stop = _BOUNDARY.search(after)
                sentence = before[ends[-1] if ends else 0:] + " ¦ " + (after[:stop.start()] if stop else after)
            if self.within and not any(cue.search(sentence) for cue in self.within):
                return False
            if any(cue.search(sentence) for cue in self.unless):
                return False
        return True


# Fields: what a sentence of that field talks about.
MEDICAL = field(r"bệnh viện|bác sĩ|bệnh nhân|người bệnh|chụp|cắt lớp|phim chụp|x[- ]?quang|siêu âm|nội soi|xét nghiệm|"
                r"chẩn đoán|điều trị|khối u|u não|ung thư|phẫu thuật|lát cắt|dãy đầu thu|cản quang|tổn thương|"
                r"đột quỵ|bệnh lý|sọ não|bức xạ|y tế|y khoa|khám bệnh|chẩn đoán hình ảnh|scan|scanner",
                r"MRI|M R I|PET|P E T|ICU|I C U")
LEGAL = field(r"tòa|tòa án|xét xử|bị cáo|bị hại|vụ án|bào chữa|kháng cáo|phiên tòa|tố tụng|khởi kiện|"
              r"viện kiểm sát|pháp lý|văn phòng luật|đoàn luật sư|thân chủ|tranh chấp")
MEMORIAL = field(r"liệt sĩ|nghĩa trang|mộ|phần mộ|hy sinh|thương binh|tri ân|tưởng niệm|kháng chiến|truy tặng|"
                 r"anh hùng|di hài|hài cốt|chiến sĩ")
SPORTS = field(r"đội tuyển|trận|giải đấu|bàn thắng|ghi bàn|huấn luyện viên|cầu thủ|vận động viên|vô địch|bóng đá|"
               r"vòng loại|vòng bảng|tỷ số|đối thủ|futsal|bóng chuyền|thi đấu|SEA Games")
ADMIN = field(r"thủ tướng|chính phủ|chủ tịch|ủy ban|uỷ ban|hội đồng nhân dân|bộ chính trị|ban bí thư|tỉnh ủy|thành ủy|"
              r"ban hành|triển khai|chỉ đạo|văn bản|quyết định|nghị quyết|công văn|thông tư|chỉ thị|nghị định",
              r"UBND|HĐND")
FINANCE = field(r"cổ phiếu|trái phiếu|chứng khoán|thanh khoản|lãi suất|đáo hạn|phát hành|nhà đầu tư|vốn hóa|"
                r"niêm yết|giao dịch|ngân hàng|tín dụng|lợi nhuận|doanh thu|cổ đông|cổ tức", r"HOSE|HoSE")
ADMISSION = field(r"xét tuyển|tuyển sinh|trúng tuyển|điểm chuẩn|thí sinh|ngành học|đăng ký dự thi")
UNIVERSITY = field(r"đại học|cao đẳng|học viện|sinh viên|giảng dạy|nghiên cứu sinh", r"ĐH|CĐ|ĐHQG|SV")
ENERGY = field(r"điện mặt trời|năng lượng|quang điện|tấm pin|pin|inverter|biến tần|lưới điện|công suất")
TOURISM = field(r"du lịch|du khách|lưu trú|nghỉ dưỡng|phòng nghỉ|khách sạn|resort|homestay|tour")
RECRUIT = field(r"tuyển dụng|ứng viên|ứng tuyển|phỏng vấn|việc làm|hồ sơ xin việc|nhân sự")
LABOR = field(r"nhà máy|xí nghiệp|khu công nghiệp|xưởng|đình công|ngừng việc|tăng ca|tiền lương|lao động|công đoàn")
CUSTOMS = field(r"hải quan|biểu thuế|thuế suất|xuất khẩu|nhập khẩu|hàng hóa|mã số hàng")
YOUTH = field(r"đoàn viên|chi đoàn|đoàn thanh niên|thanh niên|tình nguyện|thiếu nhi")
BANKING = field(r"ngân hàng|chi nhánh|phòng giao dịch|tài khoản|tín dụng|\w*bank")

_GAP = r"[ \t]+"
# Organization head words: Bộ TC, Sở GD-ĐT, Phòng TN&MT, ngành GD.
HEAD = Context(before=r"(?<![^\W\d_])(?:Bộ|Sở|Phòng|ngành|Ngành)" + _GAP)
_LEVEL = r"(?:tỉnh|thành phố|huyện|quận|thị xã|xã|phường|thị trấn|trung ương|đa khoa|quân y|dã chiến)\b"
# A name or another abbreviation follows: BV Bạch Mai, ĐT Việt Nam, BS CKII, BV tỉnh.
_NAME = _GAP + rf"(?:[{UPPER}]|{_LEVEL})"
NAME = Context(after=_NAME)
# A personal name follows: LS Trương Thanh Đức (not an abbreviation or a capitalized headline).
# A Vietnamese family name: an expansion (Ủy ban..., Bộ...) is never taken for a person.
_SURNAMES = ("Nguyễn|Trần|Lê|Phạm|Hoàng|Huỳnh|Phan|Vũ|Võ|Đặng|Bùi|Đỗ|Hồ|Ngô|Dương|Lý|Đinh|Đoàn|Lâm|Mai|Trịnh|"
             "Trương|Tạ|Hà|Lưu|Cao|Chu|Châu|Đào|Lương|Lại|Kiều|Tô|Tôn|Thái|Từ|Quách|La|Mạc|Phùng|Vương|Triệu|"
             "Khổng|Âu|Kim|Lò|Hứa|Nghiêm|Tăng|Tống|Thân|Bạch|Doãn|Giang|Khúc|Lục|Ninh|Phí|Tiêu|Vi|Diệp|Mẫn|"
             "Nông|Quan|Thạch|Ung|Viên|Đàm|Đồng|Hàn|Hầu|Lã|Mã|Nhữ|Phó|Thiều|Tiền|Trình|Ông|Tào|Bế|Ngụy|Khuất|Kha")
_PERSON = _GAP + rf"(?:{_SURNAMES})(?![^\W\d_])"
NUMBER = Context(after=r"[ \t]*(?:số[ \t]+)?[0-9]")
# A document number: CT 05/CT-TTg, TT số 01/2020, CV 123/UBND.
_DOC_NUMBER = r"[ \t]*(?:số[ \t]+)?[0-9]{1,5}[ \t]*/"
# Road, area and century numbers: QL 1A, ĐT.741, KV 2; not "TL 10%" or "TDP 65W" (a CPU rating).
SHORT_NUMBER = Context(after=r"[ \t]*\.?[ \t]*(?:số[ \t]+)?[0-9]{1,4}[A-Z]?(?![\w%‰]|[.,/][0-9])")
WARD_NUMBER = Context(after=r"[ \t]*\.?[ \t]*(?:số[ \t]+)?[0-9]{1,3}(?![\w%‰]|[.,/][0-9])")
CENTURY = Context(after=r"[ \t]*(?:[1-9]|1[0-9]|2[0-2])(?![\w%‰]|[.,/][0-9])")
PHONE = Context(after=r"[ \t]*:?[ \t]*(?:\+84|0)[0-9](?:[ .]?[0-9]){7,}")
PLATE = Context(after=r"[ \t]*:?[ \t]*[0-9]{2}[A-ZĐ][A-Z0-9]?[ \t]*[-.]?[ \t]*[0-9]")
_NUMERAL = (r"[0-9][0-9.,]*|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|mươi|mốt|lăm|trăm|nghìn|ngàn|"
            r"triệu|tỷ|vài|dăm|mấy")
_COUNTED = rf"(?<![^\W\d_])(?:{_NUMERAL}|các|những|mỗi|từng|nhiều|mọi|hàng|cho|của|với|giữa|là|có)" + _GAP
COUNTED = Context(before=_COUNTED)
YEAR_ERA = Context(before=r"(?<![^\W\d_])(?:[0-9]{1,4}|năm|kỷ)" + _GAP)
_WEEKDAY = r"(?i:thứ[ \t]*(?:0?[2-7]|hai|ba|tư|năm|sáu|bảy))|T[2-7]"
SUNDAY = Context(before=rf"(?:{_WEEKDAY})[ \t]*(?:[-–,]|đến|tới|và|hoặc)[ \t]*")
MEDAL = Context(before=r"(?<![^\W\d_])(?:[0-9]+|một|hai|ba|bốn|năm|sáu|bảy|tám|chín|mười|các|những|tấm|chiếc|"
                       r"giành|đoạt|nhận|đeo|mang về)" + _GAP)
# Leaders of a body: CT UBND tỉnh, PCT HĐND, Phó CT nước.
_LEADERSHIP = _GAP + (r"(?:UBND|HĐND|UBMTTQ|MTTQ|Ủy ban|Hội đồng|HĐQT|HĐTV|xã|phường|thị trấn|huyện|quận|thị xã|"
                      r"tỉnh|thành phố|TP|nước|Quốc hội|QH|Công đoàn|Hội|[Tt]hường trực)\b")
_ASSEMBLY = r"(?:Đảng|ĐCS|Đoàn|Công đoàn|Hội|cổ đông|đại biểu|thi đua|lần|khóa|nhiệm kỳ|[IVX]+\b)"
_SCHOOLING = r"(?<![^\W\d_])(?:thi|trường|hệ|bậc|học|tốt nghiệp|tuyển sinh|sinh viên|giảng viên|các|ĐH,|ĐH và)"
_TEAM = _GAP + (r"(?:Việt Nam|Thái Lan|Indonesia|Malaysia|Philippines|Singapore|Myanmar|Lào|Campuchia|Nhật Bản|"
                 r"Hàn Quốc|Trung Quốc|Triều Tiên|Úc|Iraq|Iran|Saudi Arabia|UAE|Qatar|Jordan|Uzbekistan|"
                 r"U[0-9]{2}\b|nữ\b|nam\b|quốc gia|bóng đá|futsal|bóng chuyền|Olympic)")
# PetroVietnam companies: PV Gas, PV Power are names, not "phóng viên".
PV_BRANDS = re.compile(r"[ \t]+(?:Gas|GAS|Oil|OIL|Power|POWER|Drilling|DRILLING|Trans|TRANS|Coating|Bank|Comboank|"
                       r"Combank|Pipe|Chem|Shipyard|EP|Tech)\b")

# Ordered (context, reading) pairs; the first context that matches decides, KEEP
# included. With no match the token keeps its ALWAYS reading or none at all, so an
# unknown context is never given a guessed meaning.
CONTEXTUAL = {
    # Titles before a name.
    "TS": ((Context(after=_PERSON), "tiến sĩ"),
           (Context(after=_GAP + r"(?:ngắn hạn|dài hạn|cố định|bảo đảm|đảm bảo|thế chấp|ròng)\b"), "tài sản"),
           (Context(before=r"(?<![^\W\d_])(?:tổng|giá trị|định giá|khối)" + _GAP), "tài sản"),
           (Context(before=_COUNTED, unless=FINANCE), "thí sinh")),
    "BS": ((PLATE, "biển số"), (NAME, "bác sĩ"), (COUNTED, "bác sĩ")),
    "DS": ((Context(after=_PERSON), "dược sĩ"),),
    "LS": ((Context(after=_PERSON, within=MEMORIAL), "liệt sĩ"), (Context(after=_PERSON), "luật sư")),
    "KS": ((Context(after=r"[ \t]*[1-5][ \t]*sao\b"), "khách sạn"), (Context(after=_PERSON), KEEP),
           (Context(after=_NAME, within=TOURISM), "khách sạn")),
    "GV": ((Context(after=_NAME, within=UNIVERSITY), "giảng viên"), (Context(before=_COUNTED, within=UNIVERSITY), "giảng viên"),
           (NAME, "giáo viên"), (COUNTED, "giáo viên")),
    # Plain nouns after a count or a quantifier.
    "HS": ((Context(before=r"(?<![^\W\d_])(?:mã|nhóm|chương)" + _GAP), KEEP), (Context(within=CUSTOMS), KEEP),
           (Context(before=r"(?<![^\W\d_])(?:nộp|bộ|thành phần|hoàn thiện|tiếp nhận|trả|xét|duyệt|lập)" + _GAP), "hồ sơ"),
           (COUNTED, "học sinh"),
           (Context(after=_GAP + r"(?:lớp|trường|giỏi|tiểu học|THCS|THPT|cấp)\b"), "học sinh")),
    "SV": ((COUNTED, "sinh viên"), (Context(after=_GAP + r"(?:năm|trường|ngành|khóa|ĐH)\b"), "sinh viên")),
    "DN": ((COUNTED, "doanh nghiệp"),
           (Context(after=_GAP + r"(?:Việt|nhà nước|tư nhân|nhỏ|vừa|FDI|xuất khẩu|ngoài|trong nước)\b"), "doanh nghiệp")),
    "BN": ((Context(after=_GAP + r"(?:USD|VND|VNĐ|EUR|đô|đồng|euro)\b"), KEEP),  # 2 BN USD: billion
           (Context(after=r"[ \t]*(?:số[ \t]+)?[0-9]", unless=FINANCE), "bệnh nhân"),
           (Context(before=_COUNTED, unless=FINANCE), "bệnh nhân")),
    "CB": ((Context(after=_GAP + r"(?:thủy sản|nông sản|thực phẩm|gỗ|lâm sản)\b"), "chế biến"), (COUNTED, "cán bộ")),
    "NV": ((Context(before=_COUNTED, within=ADMISSION), "nguyện vọng"), (COUNTED, "nhân viên")),
    "HV": ((NAME, "Học viện"), (COUNTED, "học viên")),
    "ĐV": ((Context(before=_COUNTED, within=YOUTH), "đoàn viên"), (COUNTED, "đơn vị")),
    "KH": ((Context(after=_GAP + r"(?:cá nhân|doanh nghiệp|vay|gửi tiền|thân thiết|tổ chức)\b"), "khách hàng"),
           (Context(before=_COUNTED, within=BANKING), "khách hàng"),
           (Context(after=_DOC_NUMBER), "kế hoạch")),
    "SP": ((Context(before=r"(?<![^\W\d_])(?:ĐH|Đại học|Cao đẳng|CĐ|trường|Trường|ngành|khoa)" + _GAP), "Sư phạm"),
           (Context(after=_GAP + r"(?:mới|chủ lực|OCOP|công nghệ|chính)\b"), "sản phẩm"), (COUNTED, "sản phẩm")),
    "BV": ((NAME, "bệnh viện"), (COUNTED, "bệnh viện")),
    "HCV": ((MEDAL, "huy chương vàng"),),
    "HCB": ((MEDAL, "huy chương bạc"),),
    "TCN": ((YEAR_ERA, "trước Công nguyên"),),
    "SCN": ((YEAR_ERA, "sau Công nguyên"),),
    "CN": ((SUNDAY, "chủ nhật"), (Context(before=r"(?<![^\W\d_])(?:sau|trước)" + _GAP), "Công nguyên"),
           (Context(after=_NAME, within=BANKING), "chi nhánh"), (Context(before=_COUNTED, within=LABOR), "công nhân")),
    "ĐH": ((Context(after=_GAP + _ASSEMBLY), "Đại hội"), (NAME, "Đại học"),
           (Context(before=_SCHOOLING + r"[ \t]*"), "đại học")),
    "CĐ": ((NAME, "Cao đẳng"), (Context(before=_SCHOOLING + r"[ \t]*"), "cao đẳng")),
    # Roads, areas, centuries and contacts by their numbers.
    "ĐT": ((PHONE, "điện thoại"), (SHORT_NUMBER, "đường tỉnh"), (Context(after=_TEAM), "đội tuyển")),
    "QL": ((SHORT_NUMBER, "quốc lộ"),),
    "TL": ((SHORT_NUMBER, "tỉnh lộ"),),
    "HL": ((SHORT_NUMBER, "hương lộ"),),
    "KV": ((SHORT_NUMBER, "khu vực"),),
    "KP": ((WARD_NUMBER, "khu phố"),),
    "TDP": ((WARD_NUMBER, "tổ dân phố"),),
    "TK": ((CENTURY, "thế kỷ"),),
    "BKS": ((PLATE, "biển kiểm soát"), (NUMBER, "biển kiểm soát")),
    # Documents: a number, or a number and a field, fixes the type.
    "NĐ": ((NUMBER, "nghị định"),),
    "QĐ": ((NUMBER, "quyết định"),),
    "NQ": ((NUMBER, "nghị quyết"),),
    "TT": ((Context(after=_DOC_NUMBER), "thông tư"), (Context(after=r"[ \t]*(?:số[ \t]+)?[0-9]", within=(ADMIN, LEGAL)), "thông tư"),
           (Context(after=r"[ \t]*[-–]?[ \t]*Huế\b"), "Thừa Thiên")),
    "CT": ((Context(after=_LEADERSHIP), "chủ tịch"),
           (Context(after=_DOC_NUMBER, unless=MEDICAL), "chỉ thị"),
           (Context(after=r"[ \t]*(?:số[ \t]+)?[0-9]", within=ADMIN, unless=MEDICAL), "chỉ thị")),
    "PCT": ((Context(after=_LEADERSHIP), "phó chủ tịch"),),
    "CV": ((Context(after=_DOC_NUMBER), "công văn"), (Context(after=_GAP + r"số[ \t]+[0-9]"), "công văn")),
    "TB": ((Context(before=r"(?<![^\W\d_])(?:điểm|mức|giá|thu nhập|lương|tuổi thọ|nhiệt độ)" + _GAP), "trung bình"),
           (Context(after=_DOC_NUMBER), "thông báo")),
    # Bodies and fields.
    "CP": ((Context(before=r"(?<![^\W\d_])(?:Cty|CTy|cty|[Cc]ông ty|[Tt]ổng công ty|[Tt]ập đoàn)" + _GAP), "cổ phần"),
           (Context(before=r"(?<![^\W\d_])(?:mã|giá|nhóm|bán|mua|nắm giữ|sở hữu|phát hành|chào bán)" + _GAP), "cổ phiếu"),
           (Context(before=r"(?<![^\W\d_])(?:Thủ tướng|Văn phòng|[Nn]ghị quyết|[Nn]ghị định|[Cc]hỉ thị|[Qq]uyết định|"
                           r"[Tt]hông tư)(?:[ \t]+của)?" + _GAP), "Chính phủ")),
    "BTC": ((Context(after=_GAP + r"(?:giải|[Gg]iải|cuộc thi|chương trình|lễ hội|sự kiện|hội thi|hội diễn|hội thao|"
                                  r"liên hoan|đêm nhạc|SEA Games|Olympic)\b"), "Ban tổ chức"),),
    "CA": ((Context(after=_GAP + r"(?:tỉnh|thành phố|huyện|quận|thị xã|xã|phường|thị trấn|TP|Q\.|P\.)"), "Công an"),),
    "QH": ((Context(before=r"(?<![^\W\d_])(?:Chủ tịch|Phó Chủ tịch|kỳ họp|Kỳ họp|đại biểu|Đại biểu|Văn phòng|"
                           r"phiên họp|Ủy ban Thường vụ)" + _GAP), "Quốc hội"),
           (Context(after=_GAP + r"khóa\b"), "Quốc hội")),
    "MTV": ((Context(before=r"(?:TNHH|trách nhiệm hữu hạn)" + _GAP), "một thành viên"),),
    "QG": ((Context(before=r"(?:THPT|ĐH|ĐT|ĐTQG|VĐ)" + _GAP), "quốc gia"),),
    "TN": ((Context(after=_GAP + r"THPT\b"), "tốt nghiệp"),
           (Context(before=r"(?<![^\W\d_])(?:thi|xét|kỳ thi|bằng)" + _GAP), "tốt nghiệp"),
           (Context(before=r"(?<![^\W\d_])(?:Đoàn|đoàn|Hội|hội|Tháng)" + _GAP), "Thanh niên")),
    "NN": ((Context(before=r"(?<![^\W\d_])(?:vốn|ngân sách|cơ quan|doanh nghiệp|sở hữu|quản lý|kinh tế)" + _GAP), "nhà nước"),
           (Context(before=r"(?<![^\W\d_])(?:trung tâm|học|thi|môn|chứng chỉ|giáo viên)" + _GAP), "ngoại ngữ")),
    "VP": ((NAME, "Văn phòng"),),
    "SL": ((Context(after=r"[ \t]*:"), "số lượng"),),
    "ĐK": ((Context(after=_GAP + r"(?:dự thi|xét tuyển|kinh doanh|thường trú|tạm trú|kết hôn|học|tham gia|nhận)\b"),
            "đăng ký"),),
    "BTL": ((Context(after=_GAP + r"(?:Quân khu|Hải quân|Bộ đội|Cảnh sát|Thủ đô|Vùng|Lăng|Công binh|Đặc công|"
                                  r"Pháo binh|Tăng|Phòng không)"), "Bộ Tư lệnh"),),
    # ALWAYS readings with a different meaning in some fields.
    "TP": ((Context(before=r"(?<![^\W\d_])(?:phát hành|mua|bán|mua lại|lãi suất|đáo hạn|kênh)" + _GAP), "trái phiếu"),
           (Context(after=_GAP + r"(?:doanh nghiệp|chính phủ)\b", within=FINANCE), "trái phiếu")),
    "PV": ((Context(after=PV_BRANDS.pattern), KEEP), (Context(within=ENERGY), KEEP)),
    "BCH": ((Context(after=_GAP + r"(?:[Qq]uân sự|PCTT|[Pp]hòng chống|[Pp]hòng thủ|[Bb]iên phòng)"), "Ban Chỉ huy"),),
    "NTD": ((Context(within=RECRUIT), "nhà tuyển dụng"),),
    "Tp": ((NAME, "thành phố"),),
    # Fuel oils after "dầu": dầu DO, dầu FO.
    "DO": ((Context(before=r"(?<![^\W\d_])[Dd]ầu" + _GAP), "đê ô"),),
    "FO": ((Context(before=r"(?<![^\W\d_])[Dd]ầu" + _GAP), "ép ô"),),
    "VD": ((Context(after=r"[ \t]*:"), "ví dụ"),),
    "ĐC": ((Context(after=r"[ \t]*:"), "địa chỉ"),),
}
# Mixed-case and punctuated shorthand.
SPECIAL = {"v.v": "vân vân", "V.v": "vân vân", "Cty": "công ty", "CTy": "công ty", "cty": "công ty"}
SPECIAL_PAIRS = {"Đ/c": "đồng chí", "đ/c": "đồng chí", "v/v": "về việc", "V/v": "về việc",
                 "K/g": "kính gửi"}
# Personal titles inside dotted chains: ThS.BS, GS.TSKH, BS.CKII, PGS.TS.BS.
TITLES = {"GS": "giáo sư", "PGS": "phó giáo sư", "TS": "tiến sĩ", "TSKH": "tiến sĩ khoa học", "ThS": "thạc sĩ",
          "BS": "bác sĩ", "DS": "dược sĩ", "LS": "luật sư", "KTS": "kiến trúc sư", "CKI": "chuyên khoa một",
          "CKII": "chuyên khoa hai", "CK1": "chuyên khoa một", "CK2": "chuyên khoa hai", "NSND": "nghệ sĩ nhân dân",
          "NSƯT": "nghệ sĩ ưu tú", "NGND": "nhà giáo nhân dân", "NGƯT": "nhà giáo ưu tú",
          "TTND": "thầy thuốc nhân dân", "TTƯT": "thầy thuốc ưu tú"}
# Parts of unlisted clusters that have one meaning there: KT-XH-QP-AN, VH-XH, GD-YT.
COMPONENTS = {"KT": "kinh tế", "XH": "xã hội", "QP": "quốc phòng", "AN": "an ninh", "VH": "văn hóa",
              "GD": "giáo dục", "DL": "du lịch", "YT": "y tế", "MT": "môi trường", "LĐ": "lao động",
              "XD": "xây dựng", "PTNT": "phát triển nông thôn"}
# Keys that join each listing by their key; a separator form wins over a solid one.
ALWAYS_KEYS = {}
for _form, _reading in sorted(ALWAYS.items(), key=lambda item: CLUSTER_SEPARATORS.search(item[0]) is not None):
    ALWAYS_KEYS[cluster_key(_form)] = _reading
SECTOR_KEYS = {}
for _form, _reading in sorted(SECTORS.items(), key=lambda item: CLUSTER_SEPARATORS.search(item[0]) is not None):
    SECTOR_KEYS[cluster_key(_form)] = _reading


def headed(key: str):
    """Bộ/Sở + a sector of three letters or more: BGDĐT, SKHĐT, BVHTTDL, STNMT."""
    if len(key) >= 4 and key[0] in "BS":
        sector = SECTOR_KEYS.get(key[1:])
        if sector:
            return ("Bộ " if key[0] == "B" else "Sở ") + sector
    return None


def lookup(form: str):
    """Context-free reading of a token or cluster, or None."""
    reading = ALWAYS.get(form)
    if reading is None:
        key = cluster_key(form)
        reading = ALWAYS_KEYS.get(key) or headed(key)
    return reading


def contextual(form: str, before: str, after: str, sentence=None):
    """Reading of an ambiguous short form in its context (KEEP: no expansion), or None."""
    for context, reading in CONTEXTUAL.get(form, ()):
        if context.matches(before, after, sentence):
            return reading
    return None


# Close every field under expansion: an abbreviation is a cue of a field when every reading
# it can get belongs to that field (BV is always "bệnh viện"; BS may be "biển số"). A cue
# then holds before and after its own expansion, so a second pass decides the same way.
FIELDS = (MEDICAL, LEGAL, MEMORIAL, SPORTS, ADMIN, FINANCE, ADMISSION, UNIVERSITY, ENERGY, TOURISM, RECRUIT,
          LABOR, CUSTOMS, YOUTH, BANKING)


def _readings_of(form: str) -> set:
    readings = {ALWAYS.get(form), SECTORS.get(form), COMPONENTS.get(form)}
    readings.update(reading for _, reading in CONTEXTUAL.get(form, ()) if reading)
    return readings - {None}


_FORMS = {*ALWAYS, *SECTORS, *CONTEXTUAL}
_COMPOSED = {prefix + key: ("Bộ " if prefix == "B" else "Sở ") + sector
             for key, sector in SECTOR_KEYS.items() if len(key) >= 3 for prefix in "BS"}
for _field in FIELDS:
    _cue_words = re.compile(rf"(?<![^\W\d_])(?:(?i:{_field.words}))(?![^\W\d_])")
    _keys = [cluster_key(form) for form in _FORMS
             if (readings := _readings_of(form)) and all(_cue_words.search(r) for r in readings)]
    _keys += [key for key, reading in _COMPOSED.items() if _cue_words.search(reading)]
    _field.extend(_keys)


def components(form: str):
    """An unlisted cluster read part by part when every part has one meaning (KT-XH-QP-AN)."""
    parts = re.split(r"([ \t]*[&+][ \t]*|[,;][ \t]*|[-–])", form)
    if len(parts) < 3:
        return None
    out = []
    for index, part in enumerate(parts):
        if index % 2:
            separator = part.strip()
            out.append(" và " if separator in "&+" else ", " if separator in ",;" else " - ")
            continue
        reading = COMPONENTS.get(part) or lookup(part)
        if reading is None:
            return None
        out.append(reading)
    return "".join(out)
