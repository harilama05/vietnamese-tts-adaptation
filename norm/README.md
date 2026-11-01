# Vietnamese TTS normalizer 0.13.3

Bộ normalize tiếng Việt dùng chung cho OmniVoice, ZeroTTS và ứng dụng TTS khác.
Chỉ dùng thư viện chuẩn Python; import package không tải model, PyTorch, ONNX,
không truy cập mạng và không phụ thuộc working directory.

## Sử dụng

Sau khi cài package từ thư mục `norm`:

```python
from vietnamese_tts_normalizer import normalize_vi_text

text = normalize_vi_text("Ngày 18/9/2026 lúc 9h30, mua 0.5kg với giá 50.000đ.")
```

Cài package độc lập, ví dụ trong môi trường ZeroTTS:

```bash
python -m pip install /path/to/OmniVoice/norm
```

Sau đó gọi `normalize_vi_text(text)` trước synthesis. Không gọi thêm normalizer
cũ lên kết quả này. API có cùng tên với ZeroTTS để dễ thay import tại adapter.
Checkout ZeroTTS không bị chỉnh sửa trong lần tích hợp OmniVoice này.

CLI từ root repo OmniVoice:

```bash
python -m vietnamese_tts_normalizer --explain 'Mua 0.5kg với giá 50.000đ!'
python -m vietnamese_tts_normalizer --locale vi 'Giá 1.234 đồng'
echo 'OTP 004215' | python -m vietnamese_tts_normalizer
```

Sau khi cài package độc lập, lệnh `vi-normalize` có cùng các tham số.

## Tích hợp OmniVoice

Đường inference có sẵn `generate(..., language="vi", normalize_text=True)` sử
dụng package này. Các tên `vie`, `vi-VN`, `Vietnamese`, `tiếng Việt` cũng được
nhận diện bởi `omnivoice.utils.text.normalize_text`. Không tự bật normalize khi
`normalize_text=False`; không tự suy luận ngôn ngữ tiếng Việt nếu bỏ language.

Các API `scripts.text_normalize.Replacer.replace_all`, `normalizer.replace_all`,
`split_text`, `split_text_comma`, `chunk_words`, `read_number`, `number_replacer`
được giữ dưới dạng wrapper. Các phương thức xử lý regex nội bộ cũ không còn là
API dùng chung. Wrapper không cần `num2words` hay `vietnam_number`, không in thông
báo khi import, không đọc `./utils/acronyms` từ working directory.

`split_text` giữ chữ hoa, `?!` và đếm Unicode characters. `min_char` là mục tiêu
mềm, `max_char` được áp dụng trừ trường hợp một token đơn lẻ đã dài hơn giới hạn
(ví dụ URL). Quy ước thêm khoảng trắng/dấu câu ở đầu chunk của script cũ được
giữ. Normalizer chính không tự chia đoạn hay lowercase.

## Cấu hình cách đọc

```python
from vietnamese_tts_normalizer import Normalizer, NormalizerConfig

normalizer = Normalizer(NormalizerConfig(
    zero_tens="lẻ",                 # hoặc linh
    thousand="nghìn",               # hoặc ngàn
    four_after_zero="bốn",          # 104; hoặc tư
    decimal_reading="auto",         # 12,25 -> ... hai mươi lăm; 0,05/3,14159 từng chữ số; digits | cardinal
    number_locale="auto",           # hoặc vi/en khi biết định dạng nguồn
    ambiguous_number="infer",       # 1.234/1,234: infer (mặc định) | vi | en | preserve
    abbreviation_policy="common",   # common (mặc định) | extended (từ điển 0.9.x) | none
    acronym_mode="latin",           # viết tắt ngoài bảng: latin (mặc định, G D P) | spell (tên chữ cái tiếng Việt) | preserve
    link_mode="domain",             # domain (mặc định: đọc tên miền trơn) | preserve | speak
    duration_format="clock",       # hoặc mm:ss / hh:mm cho nguồn thời lượng
    max_expression_chars=2048,      # giới hạn vùng biểu thức, kể cả khoảng trắng
    max_token_chars=512,            # giới hạn token cấu trúc không có khoảng trắng
    datetime_mode="speak",          # hoặc preserve cho timestamp ISO
    normalize_fullwidth_numbers=True, # ０．５ -> 0.5, ngoài URL/code/control tags
    fraction_word="trên",           # hoặc phần
    range_prefix="từ",              # "20%-30%" -> từ ... đến ...; "" để bỏ chữ "từ"
    abbreviation_overrides={"BS": "bác sĩ", "AI": "ây ai"},
    unit_overrides={"kg": "ki lô gam"},
))
print(normalizer.normalize("BS An kiểm tra 5kg."))
```

Giữ một instance nếu xử lý nhiều câu. Cấu hình được đóng băng và sao chép các
override để caller không vô tình đổi một instance đang dùng. `--config path.json`
nhận cùng các trường; giá trị file ghi đè lựa chọn trên CLI.

`number_locale="auto"` nhận diện các dạng nhất quán `1.234,56`, `1,234.56`, `1.000.000`,
`1,000,000`, `3.14`, `12,25`, `0.005`. Dạng mơ hồ `1.234`/`1,234` được quyết định bởi
`ambiguous_number`. Mặc định `infer` xét bằng chứng trong chính văn bản (`6,23`,
`1.234.567` → kiểu Việt; `1,234,567`, `1,234.5` → kiểu Anh) và dùng quy ước Việt khi
không có bằng chứng: `4.265 USD` → bốn nghìn hai trăm sáu mươi lăm đô la,
`42,195 km` → bốn mươi hai phẩy một chín năm ki lô mét. Đặt `"preserve"` để giữ
hành vi 0.9.x. `number_locale="vi"`/`"en"` tường minh vẫn có ưu tiên cao nhất. Dạng sai
cấu trúc không được đoán lại.

Chữ viết tắt (từ 0.11.0): chỉ một bảng nhỏ các dạng phổ biến nhất được mở rộng hoặc đọc
theo cách quen của người Việt (`UBND` → Ủy ban nhân dân, `NATO` → na tô; xem
`COMMON_ABBREVIATIONS`). Thuật ngữ nước ngoài không được phiên âm: viết tắt đọc từng chữ
được tách thành **chữ cái Latin in hoa** để model TTS tự đọc (`GDP` → G D P, `WHO` → W H O),
còn viết tắt 2 chữ (`AI`, `LG`, `EU`) và viết tắt đọc được như một từ (`BRICS`, `JAMSTEC`,
`WIPO`) được giữ nguyên. Không đánh vần tên viết tắt có dấu chấm
(`J. R. R.`), số La Mã, từ tiếng Việt viết hoa (`TIN NÓNG`). Chi tiết ở mục 0.11.0 bên dưới.
`acronym_mode="spell"` dùng lại cách đọc bằng tên chữ cái tiếng Việt của 0.10.0;
`acronym_mode="preserve"` giữ nguyên; `abbreviation_policy="extended"` bật lại từ điển
soe-vinorm của 0.9.x; `abbreviation_overrides` luôn có ưu tiên cao nhất. Tên đơn vị phân
biệt hoa/thường: `mW` khác `MW`, `MB` khác `Mb`.

Từ 0.12.0, **viết tắt tiếng Việt được đọc theo nghĩa** (`TTXVN` → Thông tấn xã Việt Nam,
`VH-TT-DL`/`VH,TT&DL`/`VHTTDL` → Văn hóa, Thể thao và Du lịch), còn dạng ngắn nhiều nghĩa chỉ
được đọc khi ngữ cảnh và lĩnh vực của câu xác định nghĩa (`CT UBND` → chủ tịch, `chụp CT` giữ
nguyên). Xem `vi_abbreviations.py` và mục 0.12.0 bên dưới.

## Nhóm được xử lý

- Số nguyên, số âm, thập phân, nhóm hàng nghìn, số tiền; số 0 sau dấu phẩy.
- Phép toán có kiểm tra cú pháp và ngoặc lồng nhau, số mũ Unicode và ký hiệu
  khoa học `1e-3`. Chỉ chuyển cách đọc, không tính giá trị biểu thức.
- Ngày D/M/YYYY, D-M-YYYY, D.M.YYYY, ISO YYYY-MM-DD, tháng/năm; kiểm tra lịch
  và năm nhuận. D/M là ngày khi có dấu hiệu ngày/thứ, khi ngày > tháng (`25/9`) hoặc khi nằm trong
  danh sách ngày; còn lại là phân số (`3/4`, `chiếm 1/3`).
- Giờ `15h30`, `9g45`, `15:30`, `15:30:20`, AM/PM, khoảng giờ; kiểm tra giới hạn
  giờ/phút. `03:15 PM` đọc theo hệ 24 giờ; `24h` là thời lượng. Dạng `25h30`
  cần từ khóa thời lượng như “trong”, “kéo dài”.
- Khoảng ngày có ngữ cảnh, ngày viết gộp `3-5/4/2026`, timestamp ISO đầy đủ
  cùng giây thập phân và múi giờ (`Z`, `+07:00`, `+0700`). Không đổi múi giờ.
- Phân số Unicode `½`, `⅓`, hỗn số `3½kg`, kể cả dấu âm.
- Phân số, phần trăm, tỷ lệ/tỷ số có từ khóa; khoảng số có đơn vị/ngữ cảnh.
- Đơn vị độ dài, diện tích/thể tích, khối lượng, nhiệt độ, điện, dữ liệu, áp suất,
  đơn vị ghép và alias số mũ `m2`/`m²`/`m^2`. Đơn vị ghép được phân tích theo
  thành phần: `đ/kg`, `VND/người`, `mg/kg/ngày`, `m²/người/ngày`; override đơn
  vị áp dụng được cho cả thành phần hoặc nguyên cụm. `USD/VND` được bảo vệ.
- Điện thoại Việt và số quốc tế có định dạng rõ, gồm mã vùng trong ngoặc;
  OTP/CCCD/tài khoản theo từ khóa; giữ số 0 đầu. Đơn vị tiền/lượng có ưu tiên
  hơn hình dạng tổng đài: `19001234 đồng` là một số tiền.
- Mã có tiền tố chữ, biển số và mã văn bản; địa chỉ có dấu hiệu ngữ cảnh. Mã
  nhiều thành phần có từ khóa (`mã đơn AB12-CD34`, `ID 123VN`) đọc từng chữ cái
  và chữ số để tránh biến chữ trong mã thành tên tổ chức/quốc gia.
- La Mã có ngữ cảnh và cú pháp hợp lệ, bao gồm I/V/X/XXI.
- Phiên bản, IPv4 có từ khóa, CamelCase gắn acronym (`ChatGPT` -> `Chat gi pi ti`).
- NFC và các khoảng trắng đặc biệt; bảo vệ URL/email, control tags `[...]`,
  code trong backticks và markup; giữ chữ hoa và dấu câu mặc định.

## Giới hạn có chủ đích

Không có bộ regex nào giải quyết mọi nghĩa từ hình thức viết. Ngày sai, số sai
định dạng, ngày hai chữ số năm, timestamp ISO không hợp lệ,
công thức hóa học và mã chưa có ngữ cảnh được giữ nguyên khi nhận diện được cả
cụm. Mã chữ-số có chữ in hoa được đọc theo thành phần: `G20` → gờ hai mươi, `5G` → năm gờ,
`CVE-2026-65660` → xê vê e hai không hai sáu sáu năm sáu sáu không.
Số dài không tự động trở thành điện thoại: có ngữ cảnh tiền/lượng thì đọc
số lượng, có từ khóa mã thì đọc từng chữ số. Một chuỗi số dài không có từ khóa
và không giống số điện thoại được đọc như số lượng. Khi khoảng ngày chỉ ghi
năm ở một đầu, chỉ dùng năm đó nếu thứ tự ngày hợp lệ; không tự suy luận năm
trước/năm sau. `H. vừa đến.` không bị đổi thành “huyện vừa đến”.

`5g` đọc gam; `9g45` đọc giờ. `3-5` đứng riêng còn mơ hồ nên được giữ, còn
`3-5 kg` và `từ 3-5` đọc khoảng. `3/0` được giữ nguyên. Từ 0.13.0, tên miền trơn được đọc
(`link_mode="domain"`, mặc định): `chinhphu.vn` → chính phủ chấm vi en; URL đầy đủ và email
vẫn giữ nguyên. Có thể đọc cả URL/email thành lời bằng `link_mode="speak"`; chế độ này phát
âm các ký hiệu có nghĩa, không đảm bảo model phát âm đúng mọi tên miền/từ ngoại ngữ.
`link_mode="preserve"` giữ nguyên mọi link như trước 0.13.0.

Các lựa chọn `acronym_mode`, dấu câu và cách đọc số cần được nghe thử trên model
và giọng thực tế. Kiểm tra văn bản không thay thế đánh giá chất lượng âm thanh.

## Giải thích kết quả

```python
result = normalizer.normalize_with_trace("0.5kg, ngày 31/02/2024")
print(result.text)
for span in result.spans:
    print(span.kind, span.status, span.source, "->", span.spoken)
```

Trace có thêm `reason` cho các ca giới hạn tài nguyên (`resource_limit`),
phiên bản có hậu tố chưa hỗ trợ (`unsupported_version_suffix`), đơn vị chưa
hỗ trợ/sai cú pháp (`unsupported_or_invalid_unit`) và số nguyên rất dài
được đọc từng chữ số (`long_integer_digits`). Các trường hợp khác có thể
để `reason=None`; đây chưa phải hệ thống giải thích đầy đủ mọi quyết định.

Trace ghi vị trí trong `result.source` sau NFC/chuẩn hóa khoảng trắng và chữ số fullwidth theo cấu hình, loại quy
tắc và trạng thái `expanded`/`preserved`. Nó không gán xác suất tin cậy. Mỗi span
nguồn chỉ qua một reader; chữ đã sinh không bị đưa lại vào các regex khác trong
cùng lượt.

## Kiểm tra và nguồn gốc

```bash
PYTHONPATH=. python -m pytest tests/test_vi_normalizer.py tests/test_vi_normalizer_generalization.py tests/test_vi_normalizer_p0.py tests/test_vi_normalizer_stage_ab.py -q
```

Bộ test kiểm tra đầu ra mong đợi, vùng không được đổi, tính ổn định khi chạy lại,
cấu hình, Unicode, trace và tích hợp. Dữ liệu từ viết tắt đi kèm giấy phép MIT
của soe-vinorm; xem `data/NOTICE.md` và `data/LICENSE.soe-vinorm`.


## Thay đổi từ 0.1.0

- Tách parser biểu thức và parser đơn vị ghép thành module riêng; không gọi
  nối nhiều lượt normalize lên văn bản đã sinh.
- Sửa nhầm PM thành “phần mềm”, số tiền thành tổng đài, thập phân có khoảng
  trắng nhóm nghìn, dấu âm của hỗn số và số mũ sai bị đọc từng mảnh.
- ISO timestamp hợp lệ nay được đọc mặc định; đặt `datetime_mode="preserve"`
  để giữ hành vi cũ. Nhãn định danh đã biết như CCCD được mở rộng đầy đủ.
- Chuẩn hóa chữ số fullwidth ở vùng văn bản thường; đặt
  `normalize_fullwidth_numbers=False` nếu muốn giữ nguyên dạng này.
- Giữ các tiền tố một chữ cái trước tên riêng khi chưa rõ là đơn vị hành chính;
  override tường minh vẫn có ưu tiên cao hơn quy tắc mặc định.
- Thêm kiểm tra lịch độc lập bằng thư viện chuẩn, đối chiếu đầu ra mong đợi,
  ghép câu từ nhiều miền, đọc đồng thời trên một instance, CLI và wheel độc lập.

Bảng so sánh của lượt nâng cấp này nằm tại
[`docs/vi_normalization_results_2026-09-21.json`](../docs/vi_normalization_results_2026-09-21.json).

## Thay đổi từ 0.2.0

- Ngày có ngữ cảnh và khoảng trắng quanh dấu (`Ngày 03 / 04 / 2026`) được
  nhận diện trước phép toán; ngày sai hoặc năm hai chữ số vẫn giữ nguyên.
  Khoảng ngày có thể dùng dấu gạch, khoảng trắng và hai năm ghi rõ.
- Alias `MST` được nhận diện cùng mã ngay ở lượt đầu; không cần normalize hai lần.
- Đọc `.5`, `-.05`, `.5kg`, `-.5kg` và dạng kết hợp trong biểu thức/khoảng; khoảng tiền `1.000–2.000đ`, khoảng giờ
  `8h30–17h30`/`8:30–17:30` và thời lượng `1h 30p`/`25h 30p 15s`.
- `ExpressionQuantity` giữ biểu thức và đơn vị trong cùng đối tượng, nên
  `10 ± 0,5 mm`, `(2+3)*5kg`, `Kích thước 10x20x30cm` được đọc trọn cụm.
- Parser đơn vị hỗ trợ tích `·`/`*` và số mũ: `N·m`, `kg·m/s²`, `m⁻²`,
  `m^-2`. Không tính giá trị hay đổi đơn vị. Bổ sung alias `µmol`/`μmol`,
  `dB`, `KiB`/`MiB`/`GiB`, `lít`, `vòng`, danh từ mẫu số `lượt`.
- `v1.2.3-beta.1` và phiên bản có build metadata được giữ nguyên cả cụm;
  chưa cung cấp cách đọc chuyên biệt cho hậu tố phiên bản.
- Sửa ranh giới regex URL/email để tránh dò lại từ từng vị trí trong token dài.

`max_token_chars` mặc định **512**, nhận số nguyên từ **64 đến 4096**. Token
không có khoảng trắng dài hơn giới hạn được giữ nguyên như một vùng có trace,
trong khi phần văn bản xung quanh vẫn được normalize. URL/code/control tags đã
nhận diện có ưu tiên bảo vệ riêng. Chuỗi chỉ gồm chữ số ASCII dài vẫn được đọc
từng chữ số qua đường xử lý trực tiếp như trước. Đây là giới hạn token, không
phải giới hạn tổng độ dài tài liệu hay cam kết timeout cho mọi văn bản có thể có.

Một thay đổi có chủ đích: token cấu trúc rất dài trước đây có thể bị đọc từng
mảnh, nay được giữ nguyên. `link_mode="speak"` vẫn áp dụng cho URL/email được
nhận diện; không dùng giới hạn token để tự cắt các vùng code đã được bảo vệ.

Các policy mơ hồ như `01:30`, ngoặc vuông/SSML, tiếng lóng thương mại và phát âm
tên riêng chưa được thay đổi trong đợt này. Cấu hình/override hiện có vẫn áp dụng;
ZeroTTS dùng wheel chung qua adapter, checkout ZeroTTS chưa bị chỉnh sửa.

Kiểm chứng đợt này: **397 test đạt**, gồm kiểm thử giới hạn tài nguyên và các
phản ví dụ. Xem [báo cáo 0.3.0](../docs/vi_normalization_release_0_3_0.md)
và [đối chiếu JSON](../docs/vi_normalization_results_0_3_0_2026-09-21.json).
Chưa đánh giá audio hoặc độ chính xác trên bộ holdout độc lập.

## Kế hoạch tiếp theo

Xem [kế hoạch sau 0.3.0](../docs/vi_normalization_next_plan.md) để theo dõi các
đợt sửa ranh giới cấu trúc, mở rộng ngữ cảnh, profile nguồn và đánh giá độc lập.
Các mục chưa hoàn tất trong kế hoạch vẫn là đề xuất; tùy chọn đã triển khai được mô tả theo từng phiên bản bên dưới.

## Lịch sử 0.4.0: đợt A–B

Phần giữ nguyên đơn vị có ngoặc dưới đây mô tả 0.4.0; bản 0.5.0 đã mở rộng theo mục mới ở cuối tài liệu.

- Giữ nguyên cả đơn vị có ngoặc chưa hỗ trợ như `5 kg/(m·s²)` với
  `reason="unsupported_unit_group"`. Nếu thiếu ngoặc đóng, giữ phần còn lại
  tới ranh giới mệnh đề/dòng; phần văn bản sau đó vẫn được xử lý.
- Thêm `max_expression_chars=2048` (64–65536), giới hạn vùng ký hiệu/số/phép
  toán liền nhau kể cả khoảng trắng ngang. Vùng quá dài được giữ nguyên và
  ghi `resource_limit`; không phải giới hạn tổng độ dài tài liệu hay timeout
  cho mọi cú pháp có thể có.
- Địa chỉ có cue nhận hậu tố một chữ cái ở mỗi thành phần: `Số nhà 12A/3B`.
  Giữ số 0 đầu, tôn trọng `acronym_mode`; chuỗi không có cue và hậu tố nhiều
  chữ cái chưa hỗ trợ được giữ nguyên.
- Máy lẻ theo sau số điện thoại được đọc từng chữ số, gồm `máy lẻ`, `ext`,
  `ext.`, `extension`. Không tự áp dụng cho một chuỗi số bất kỳ đứng riêng.
- Cue `Màn hình 16:9` đọc tỷ lệ; `Trận đấu kết thúc 3:2` đọc tỷ số. Các cue
  mới không được mang qua dấu câu hoặc xuống dòng.

### Cấu hình thời lượng

`duration_format="clock"` là mặc định tương thích 0.3.0. Với nguồn thời lượng,
chọn `"mm:ss"` hoặc `"hh:mm"`; hai chế độ này yêu cầu đúng hai thành phần,
thành phần thứ hai hai chữ số từ 00 đến 59. Phần đầu tối đa sáu chữ số.
Dạng sai/ba thành phần được giữ nguyên theo profile; timestamp ISO và giờ AM/PM
vẫn được xử lý bằng rule riêng. Khoảng có chung hậu tố AM/PM chưa xác định được
cả hai đầu được giữ nguyên cả cụm.

```python
from vietnamese_tts_normalizer import Normalizer, NormalizerConfig
normalizer = Normalizer(NormalizerConfig(duration_format="mm:ss"))
normalizer.normalize("Video dài 01:30")  # Video dài một phút ba mươi giây
normalizer.normalize("Hẹn lúc 01:30")    # Hẹn lúc một giờ ba mươi phút
```

Cue giờ hẹn tường minh (`lúc`, `hẹn`, `hẹn vào`, `giờ hẹn`) sát trước chuỗi giờ
ưu tiên hơn profile thời lượng. Đây là tập cue được hỗ trợ, không phải bộ hiểu
mọi cách diễn đạt thời gian. `reason` phân biệt `configured_duration`,
`explicit_clock_context` và `invalid_time` ở rule thời gian theo profile.

```bash
python -m vietnamese_tts_normalizer --duration-format mm:ss 'Video dài 01:30'
```

Cấu hình JSON trong `--config` ghi đè các cờ CLI. Trong API, trường cấu hình
caller cung cấp ghi đè mặc định; override đơn vị/từ tắt giữ ưu tiên hiện tại.
Adapter OmniVoice hỗ trợ cùng cấu hình:

```python
from omnivoice.utils.text import normalize_text
config = NormalizerConfig(duration_format="mm:ss")
text = normalize_text("[laughter] Video dài 01:30", "vi", vi_config=config)
```

`vi_config` chỉ dành cho tiếng Việt. `generate()` vẫn dùng mặc định khi bật
normalize như trước; nếu cần profile tùy chỉnh, chuẩn hóa trước rồi gọi synthesis
với `normalize_text=False`, tránh chạy thêm một normalizer lên kết quả.

### Bộ đánh giá

[Schema](../tests/data/vi_normalizer/schema.json) và [54 fixture A–B](../tests/data/vi_normalizer/stage_ab.json)
lưu config, các cách đọc chấp nhận được, span nguồn, lý do và trạng thái duyệt.
Tất cả mẫu hiện là **nhãn đề xuất**, chưa phải gold/holdout đã duyệt độc lập.

```bash
python scripts/evaluate_vi_normalizer.py tests/data/vi_normalizer/stage_ab.json \
  --output /tmp/vi-stage-ab-result.json
```

Bộ chấm báo riêng kết quả theo nhóm, trường hợp bị đọc sai khi cần giữ nguyên,
trường hợp bỏ sót và tính ổn định. `--require-reviewed` từ chối mẫu chưa được
đánh dấu duyệt; điểm khớp fixture không được gọi là accuracy production.

Kiểm chứng 0.4.0: **480 test đạt**. Xem [báo cáo đợt A–B](../docs/vi_normalization_release_0_4_0.md).
Chưa đánh giá audio hoặc bộ holdout độc lập.

## Mới trong 0.5.0: đơn vị có cây cấu trúc

Đọc đơn vị lồng nhau qua cây có kiểu, không tính giá trị biểu thức hoặc đổi
đơn vị. Ví dụ:

```python
from vietnamese_tts_normalizer import Normalizer, __version__
n = Normalizer()
n.normalize("5 kg/(m·s²)")
# năm ki lô gam trên mở ngoặc mét nhân giây bình phương đóng ngoặc
n.normalize("2–3 kg/(m·s²)")
# hai đến ba ki lô gam trên mở ngoặc mét nhân giây bình phương đóng ngoặc
n.normalize("(2+3) kg/(m·s²)")
# mở ngoặc hai cộng ba đóng ngoặc ki lô gam trên mở ngoặc mét nhân giây bình phương đóng ngoặc
```

Hỗ trợ `*`, `·`, `/`, nhóm `(...)`, số mũ `^2`, `²`, `⁻²`, số mũ của cả
nhóm và khoảng giá trị. Đọc rõ “mở ngoặc/đóng ngoặc” để bảo toàn phạm vi;
chưa có chế độ rút gọn cách đọc ngoặc. Các phép nhân/chia cùng cấp kết hợp
từ trái sang phải. Nhân ngầm và số mũ phân số chưa được hỗ trợ.

Parser giới hạn **16 cấp nhóm, 64 node, số mũ nguyên từ -99 tới 99**,
kèm `max_expression_chars`. Cụm sai, đơn vị lạ, giá trị mơ hồ hoặc vượt giới
hạn được giữ nguyên; trace giải thích bằng `invalid_unit_syntax`,
`unknown_unit`, `invalid_or_ambiguous_magnitude`, `unsupported_unit_exponent`
hoặc `resource_limit`. Nhóm tiền tệ chưa được diễn giải tự động.
`unit_overrides` có thể khai báo cách đọc nguyên cụm, ưu tiên trước grammar.

Trace thêm `rule_id` và `rule_version`; các trường cũ vẫn giữ nguyên. Offset
vẫn trỏ vào `result.source` đã NFC/chuyển fullwidth, **chưa ánh xạ về chuỗi
gốc trước bước chuẩn bị**. API có `__version__`, CLI có `--version`.

Văn bản không chứa ký tự số Unicode dùng scanner rút gọn, vẫn xử lý chữ tắt,
số La Mã có cue, liên kết và vùng bảo vệ. Phân số Unicode, số mũ và chỉ số
vẫn dùng scanner đầy đủ. Gọi `normalize()` không tạo danh sách trace; đầu ra
được kiểm tra bằng `normalize_with_trace(...).text`.

**553 test đạt** trong đợt phát hành này. Ba nhãn A–B về đơn vị hợp lệ đã đổi
có chủ đích từ giữ nguyên sang đọc toàn cụm; nhãn 0.4.0 được lưu ở
[baseline lịch sử](../docs/normalization_baselines/stage_ab_0_4_0.json).
Có thêm [fixture C](../tests/data/vi_normalizer/stage_c.json), đều là nhãn đề xuất,
chưa phải dữ liệu đã duyệt độc lập. Xem [báo cáo 0.5.0](../docs/vi_normalization_release_0_5_0.md).

```bash
python -m vietnamese_tts_normalizer --version
python -m vietnamese_tts_normalizer --explain '5 kg/(m·s²)'
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python -m pytest \
  tests/test_vi_normalizer.py tests/test_vi_normalizer_generalization.py \
  tests/test_vi_normalizer_p0.py tests/test_vi_normalizer_stage_ab.py \
  tests/test_vi_normalizer_stage_c.py -q -p no:cacheprovider
```

Các phần còn lại: resolver ngữ cảnh dùng chung, ánh xạ offset về input gốc,
profile Markdown/HTML/SSML, batch và đánh giá audio/holdout.

## Mới trong 0.6.0: tám lĩnh vực có ngữ cảnh

Bản này bổ sung 14 rule có cue trong tám nhóm. Tất cả bật mặc định; một rule
chỉ áp dụng khi gặp đúng hình thức/ngữ cảnh được hỗ trợ. Không phân loại chủ đề
của cả tài liệu và không tự mở rộng mọi chữ viết tắt trong một lĩnh vực.

| Tên cấu hình | Phạm vi mới | Ví dụ |
|---|---|---|
| `commerce` | Giá viết tắt, đơn giá theo đơn vị | `Giá 20k/ly`, `giá thuê 2tr/tháng` |
| `education` | Năm học, niên khóa, mã lớp, điểm | `năm học 2025-2026`, `lớp 12A1`, `điểm 9,5/10` |
| `transport` | Quốc lộ/đường tỉnh, lý trình, mã chuyến | `QL1A`, `lý trình Km12+500`, `chuyến bay VN0123` |
| `technology` | Độ phân giải, tốc độ khung hình | `độ phân giải 1920x1080px`, `video 59,94fps` |
| `sports` | Tỷ số hiệp/set, vòng loại | `tỷ số hiệp 1: 2-0`, `vòng 1/8` |
| `housing` | Phòng ngủ, vệ sinh, phòng khách | `căn hộ 2PN+1WC`, `căn hộ 2pn 1wc` |
| `administration` | Số mục/khoản/điều dạng phân cấp | `Điều 5.2`, `tiểu mục 1.2.10` |
| `lifestyle` | Đơn vị và phân số trong nấu ăn | `thêm 1 1/2 cup`, `đong 1/2 tsp` |

```python
from vietnamese_tts_normalizer import Normalizer, NormalizerConfig
n = Normalizer()
n.normalize("Giá 20k/ly")  # Giá hai mươi nghìn đồng trên ly
n.normalize("căn hộ 2PN+1WC")  # căn hộ hai phòng ngủ và một nhà vệ sinh
n.normalize("chuyến bay VN0123")  # chuyến bay vê nờ không một hai ba

# Chỉ bật quy tắc mới của hai nhóm; các chức năng cũ vẫn hoạt động.
n = Normalizer(NormalizerConfig(enabled_domains=["commerce", "education"]))
# Tắt toàn bộ các rule mới để dùng hành vi trước đợt domain.
legacy = Normalizer(NormalizerConfig(enabled_domains=[]))
```

`enabled_domains` nhận list/tuple, từ chối tên lạ/trùng, lưu tuple bất biến.
Thứ tự tên caller đưa vào không thay đổi ưu tiên rule. Cấu hình này cũng được
adapter OmniVoice nhận qua `vi_config`. Tắt một nhóm không tắt các rule số,
ngày, đơn vị hay chữ tắt đã có từ trước.

```bash
python -m vietnamese_tts_normalizer --domains commerce,education 'Giá 20k; lớp 12A1'
python -m vietnamese_tts_normalizer --domains '' 'Giá 20k'
```

JSON `--config` có ưu tiên hơn cờ `--domains`. Trace dùng `vi.domain_*`, lý do
`context_<domain>`, `invalid_or_ambiguous_<rule>` hoặc `resource_limit`.

Các giới hạn cần biết:

- Giá `k/tr` cần cue thương mại; không tự đoán locale của `1.234k`. Mã/ký hiệu
  ngoại tệ sau giá viết tắt được giữ nguyên để tránh tự gán tiền đồng.
- `năm học` yêu cầu hai năm liền nhau; `niên khóa` cho phép nhiều năm theo thứ
  tự tăng. Mã lớp chỉ hỗ trợ khối 1–12 + một chữ cái + tối đa hai chữ số.
- `QL/ĐT` phải viết hoa; chữ và số mã chuyến được đọc theo định danh, giữ số 0.
  Đây không phải tra cứu tuyến đường/chuyến bay có tồn tại hay không.
- Video chưa tự suy ra `fps` cho chuỗi không có cue. Độ phân giải hiện hai chiều.
- `PN/WC/PK` chỉ được mở rộng theo cue nhà ở; `tsp/tbsp/cup` cần cue nấu ăn,
  không tự chuyển đổi thành thể tích. Từ tiếng Anh ngoài tập này không tự dịch.
- `vòng 1/8` là tập ký hiệu vòng loại được hỗ trợ, không phải suy luận toàn bộ
  luật thể thao. Số mục chỉ đọc cấu trúc, không diễn giải nội dung pháp lý.
- Cue không vượt qua xuống dòng/dấu kết thúc câu. Vùng code/control tags/URL
  tiếp tục theo chính sách bảo vệ hiện hành.

**706 test đạt**, gồm 135 mẫu đề xuất chia theo tám nhóm, kiểm tra ghép nhiều
lĩnh vực, cấu hình, CLI/adapter và đầu vào dài. Mẫu này chưa được duyệt độc lập;
không coi kết quả khớp fixture là accuracy production. Xem
[báo cáo 0.6.0](../docs/vi_normalization_release_0_6_0.md) và
[dữ liệu đa lĩnh vực](../tests/data/vi_normalizer/domains.json).

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python -m pytest \
  tests/test_vi_normalizer.py tests/test_vi_normalizer_generalization.py \
  tests/test_vi_normalizer_p0.py tests/test_vi_normalizer_stage_ab.py \
  tests/test_vi_normalizer_stage_c.py tests/test_vi_normalizer_domains.py \
  -q -p no:cacheprovider
python scripts/evaluate_vi_normalizer.py tests/data/vi_normalizer/domains.json \
  --output /tmp/vi-domains-result.json
```

0.6.0 chưa hoàn tất toàn bộ đợt D trong lộ trình: Markdown/HTML/SSML,
batch/JSONL, ánh xạ source gốc và đánh giá audio/holdout còn tiếp tục.

Scanner ngữ cảnh chạy riêng và giữ ứng viên kế tiếp; vùng bảo vệ/định danh
được chọn trước khi xét ứng viên nằm bên trong. Không quét lại toàn bộ đuôi
văn bản cho từng từ. Có kiểm thử riêng trên đoạn dài hơn 100.000 ký tự.

## Mới trong 0.7.0: cấu trúc kết hợp, văn bản thường và JSONL

Thêm tám rule, nâng registry từ 14 lên 22 rule trong tám domain hiện có:

- Giá khoảng: `Giá 20-30k/ly`, `giá 800k–1tr`. Thiếu hậu tố ở đầu trái thì
  dùng hậu tố được ghi ở đầu phải; không tự đoán hai đầu có đơn vị khác nhau.
- Giá ghép: `Giá 1tr200k`. Phần triệu là số nguyên; phần nghìn nhỏ hơn 1.000.
  Từ chối khoảng đảo chiều và mã ngoại tệ; so sánh giá không dùng float và
  không phụ thuộc độ chính xác Decimal của ứng dụng.
- Lịch học/lịch chạy/mở cửa: `lịch học T2,T4,T6`, `mở cửa T2-CN`.
  Chỉ nhận `T2`–`T7`, `CN`; không suy ra ngày tháng, lịch nghỉ hay giờ mở cửa.
- Mã sản phẩm: `SKU AB-001/02`, `mã model RTX4090`, `mã thiết bị A1_B2`.
  Đọc chữ và chữ số định danh, giữ số 0 đầu; `SKU` cần khoảng trắng hoặc dấu hai chấm.
- Kích thước đất: `lô đất 5x20m`; chỉ hai chiều dương, đơn vị `m/cm/mm`,
  không tự tính diện tích.
- Khoảng số mục: `mục 2.1–2.3`; đọc cấu trúc, không suy luận thứ tự pháp lý.
- Khoảng định lượng nấu ăn: `thêm 1–2tbsp`, `đong 0,5–1 tsp`.

### Chọn nội dung trong ngoặc vuông

`content_profile="omnivoice"` là mặc định tương thích: giữ nguyên nội dung
ngoặc vuông. `plain_text` coi ngoặc vuông là dấu câu của văn bản thường:

```python
from vietnamese_tts_normalizer import Normalizer, NormalizerConfig
n = Normalizer(NormalizerConfig(content_profile="plain_text"))
n.normalize("[Giá 20k]")  # [Giá hai mươi nghìn đồng]
```

Code fences, inline code, URL và bản thân thẻ markup vẫn được bảo vệ. Đây
**chưa phải parser Markdown/HTML/SSML**. Không dùng `plain_text` cho dữ liệu
cần bảo toàn mọi control token của backend. Adapter OmniVoice tôn trọng lựa
chọn tường minh này qua `vi_config`; nếu không truyền thì hành vi cũ giữ nguyên.

### Nhiều câu và JSONL

```python
n = Normalizer()
for text in n.normalize_many(["Giá 20-30k", "mở cửa CN"]):
    print(text)
for result in n.normalize_many(["SKU AB-001"], with_trace=True):
    print(result.text, result.spans)
```

API trả iterator, xử lý từng phần tử theo thứ tự và cùng cấu hình. Lỗi phần tử
sẽ phát sinh khi duyệt iterator; API không tự bỏ qua lỗi. Một chuỗi đơn hoặc
mapping không được coi là tập câu.

```bash
python -m vietnamese_tts_normalizer --jsonl --explain < input.jsonl > output.jsonl
python -m vietnamese_tts_normalizer --jsonl --content-profile plain_text < input.jsonl
```

Mỗi dòng đầu vào là `{"id":"a","text":"Giá 20-30k"}`; `id` tùy chọn. Đầu ra
có `line`, `id` nếu có, `version`, `config`, `text`; `--explain` thêm source và
spans. Dòng trống được bỏ qua. Dòng lỗi sinh một record có `error`, các dòng
sau vẫn được xử lý, và exit code cuối là 1 nếu có lỗi. Chỉ nhận trường `id/text`;
config dùng chung qua CLI/`--config`, chưa hỗ trợ config riêng trong từng record.

**789 test đạt**; 65/65 mẫu mới và 135/135 mẫu domain trước đó khớp nhãn đề xuất.
Không coi các nhãn này là gold hoặc accuracy production. Xem
[báo cáo 0.7.0](../docs/vi_normalization_release_0_7_0.md),
[test mở rộng](../tests/test_vi_normalizer_expansion.py) và
[dữ liệu mới](../tests/data/vi_normalizer/expansion_0_7.json).

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python -m pytest \
  tests/test_vi_normalizer.py tests/test_vi_normalizer_generalization.py \
  tests/test_vi_normalizer_p0.py tests/test_vi_normalizer_stage_ab.py \
  tests/test_vi_normalizer_stage_c.py tests/test_vi_normalizer_domains.py \
  tests/test_vi_normalizer_expansion.py -q -p no:cacheprovider
```

## Đơn vị ghép và cách đọc tiền tệ

Đơn vị được đọc theo từng thành phần, dùng chung từ điển cho số đơn, khoảng số,
biểu thức và giá thương mại. Các đơn vị đếm như `thùng`, `chai`, `hộp`, `bao`,
`kiện`, `gói`, `ly` kết hợp được với tiền tệ hoặc đơn vị đo; không có rule riêng
cho từng chuỗi như `USD/thùng`.

```python
normalize_vi_text("83,75–83,88 USD/thùng")
# tám mươi ba phẩy bảy năm đến tám mươi ba phẩy tám tám đô la trên thùng
normalize_vi_text("2–3 EUR/kiện")  # hai đến ba ơ rô trên kiện
normalize_vi_text("5 kg / bao / ngày")  # năm ki lô gam trên bao trên ngày
```

`USD` và `$` trong số tiền cùng dùng `dollar_name` (mặc định `"đô la"`). Đặt
`dollar_name="đô la Mỹ"` để chọn cách đọc đầy đủ; `unit_overrides` vẫn có ưu tiên
cao hơn và áp dụng được cho thành phần hoặc nguyên cụm. Đơn vị chưa biết và tỷ
giá như `USD/VND` vẫn được giữ nguyên. Cụm đơn vị có phép chia/nhân đứng riêng
cũng được đọc qua cùng parser: `USD/thùng` → `đô la trên thùng`, `kg/bao/ngày`
→ `ki lô gam trên bao trên ngày`. Các chữ viết tắt đơn lẻ vẫn theo chính sách
từ điển viết tắt; URL/code/control tag tiếp tục được bảo vệ.

`abbreviation_overrides` hỗ trợ cả mã chữ–số khớp nguyên token, ví dụ
`{"E4": "e bốn"}`; không thay `E40` hoặc nội dung trong URL/code/control tag.
[profiles/text07.json](profiles/text07.json) chỉ chọn cách đọc tên viết tắt trong
bản tin mẫu, không chứa xử lý đơn vị riêng. Sau khi cài package:

```bash
vi-normalize --config /path/to/norm/profiles/text07.json < input.txt > output.txt
```

## Mới trong 0.8.0: tin tức và thời sự

Domain `news` bổ sung 13 rule, bật mặc định cùng tám domain trước. Các quy tắc
đọc cấu trúc và thuật ngữ đã đăng ký; không tra cứu sự kiện, không đoán chủ đề
của cả tài liệu, không tính hoặc quy đổi các số liệu.

| Nhóm | Ví dụ | Cách xử lý |
|---|---|---|
| Kinh tế, ngân sách | `12–25 tỷ USD`, `800 triệu–1 tỷ đồng` | Giữ bậc số ở từng đầu; đọc khoảng |
| Đơn giá | `USD 80–85/thùng`, `2,5 triệu USD/tấn` | Tiền tệ trước/sau số dùng cùng parser đơn vị |
| Sản lượng, thống kê | `1–2 triệu cổ phiếu`, `10–20 bệnh nhân` | Số lượng và đơn vị đếm có ngữ cảnh rõ |
| Lãi suất | `lãi suất giảm 25 bps`, `0,25 điểm %` | Điểm cơ bản / điểm phần trăm; không đổi thành phần trăm |
| Thời gian | `tháng 6–8/2026`, `quý I–II/2026`, `nhiệm kỳ 2026–2031` | Kiểm tra miền tháng/quý, năm bốn chữ số và thứ tự |
| Khí tượng | `gió cấp 6–7`, `100–200 mm/24h` | Khoảng cấp gió; mẫu số có số lượng |
| Môi trường, y tế | `PM2.5`, `COVID-19`, `H5N1` | Nhận dạng thuật ngữ thay vì tách thành số/mã rời |
| Quốc tế | `nhóm G7`, `các nước E4`, `hội nghị COP30` | Đọc mã theo cue; giữ mã không được hỗ trợ |
| Thị trường | `VN-Index`, `HNX-Index`, `UPCoM-Index`, `VN30` | Giữ tên chỉ số trong một span để không mở rộng nhầm `VN` |
| Thuật ngữ | `GDP`, `CPI`, `FDI`, `WHO`, `IMF`, `EU`, `NATO`, … | Từ điển news tường minh; override của caller ưu tiên |

Cơ chế đơn vị dùng chung bổ sung `tấn`, `tạ`, `yến`, `lượng`, `chỉ`, `bbl`,
`oz` và mẫu số có hệ số dương như `/24h`, `/100kg`. Không tự suy ra ounce troy,
đơn vị vật lý hoặc tỷ giá. Chuỗi địa chỉ mơ hồ như `12A/3B` vẫn giữ nguyên;
`5 m/2h` có khoảng trắng phân biệt số lượng với mã/địa chỉ dạng viết liền.

```python
from vietnamese_tts_normalizer import Normalizer, NormalizerConfig

# Mặc định vẫn dùng number_locale="auto".
n = Normalizer()
print(n.normalize("Lãi suất giảm 25 bps; vốn FDI đạt 12–25 tỷ USD."))

# Dùng khi biết nguồn tuân theo định dạng số tiếng Việt: 1.234 = 1234.
news = Normalizer(NormalizerConfig(number_locale="vi"))
print(news.normalize("1.234 người; USD 83,75/thùng"))

# Chỉ bật domain news; các parser số/ngày/đơn vị cơ bản vẫn hoạt động.
news_only = Normalizer(NormalizerConfig(enabled_domains=["news"]))
```

[profiles/news.json](profiles/news.json) chỉ chọn locale `vi`; cấu hình mặc định
vẫn bảo vệ chuỗi mơ hồ `1.234`. Không bật locale này cho dữ liệu dùng dấu chấm
thập phân kiểu Anh. `abbreviation_overrides` và `unit_overrides` tiếp tục áp dụng;
có thể chọn cách đọc ngắn/phát âm riêng mà không sửa parser.

```bash
vi-normalize --locale vi 'GDP tăng; lãi suất giảm 25 bps; nhóm G7'
vi-normalize --domains news --explain 'USD 80–85/thùng; quý I–II/2026'
vi-normalize --config /path/to/norm/profiles/news.json < input.txt > output.txt
```

Các ranh giới được giữ rõ:

- `bps` chỉ đọc **điểm cơ bản** khi có cue lãi suất được hỗ trợ; trong băng thông
  vẫn là **bít trên giây**. Không tự suy luận ngữ cảnh từ câu trước.
- Các mã nhóm G/E yêu cầu cue như `nhóm`, `các nước`, `hội nghị`; không đọc mọi
  mã chữ–số thành nhóm quốc gia. Ngày/quý sai hoặc khoảng đảo chiều giữ nguyên.
- Chữ tắt news chỉ mở rộng khi bật `news`. `AI`, `CP`, `BS`, mã sản phẩm, URL,
  code và control tag vẫn theo chính sách bảo toàn/override hiện có.
- Cách đọc tên riêng, chỉ số và bệnh là lựa chọn văn bản có thể override;
  chưa đánh giá phát âm bằng audio. Đây không phải bộ hiểu ngữ nghĩa mọi bản tin.

Bộ đánh giá mới ở [tests/data/news.json](tests/data/news.json), gồm 148 mẫu
đề xuất tự tạo, có ví dụ nhiều câu và phản ví dụ. Các nhãn được viết trước khi
chạy bộ chấm; chưa phải holdout được duyệt độc lập. Báo cáo đối chiếu nằm tại
[reports/news_evaluation_0_8_0.json](reports/news_evaluation_0_8_0.json).

## Nâng cấp 0.9.0: quy tắc tổng quát từ bộ lỗi đánh giá

Bộ lỗi `danhgia/norm_errors_final.csv` dùng để xác định nhóm lỗi và kiểm thử hồi
quy. Normalizer không đọc CSV, không so khớp câu mẫu, không gắn quy tắc với giá
trị tiền, ngày, năm hoặc tên người cụ thể.

- **Giá tiền trên đơn vị:** nhận số nguyên, số thập phân, dấu âm và khoảng giá;
  tiền tệ đứng trước hoặc sau số; `/` nối các đơn vị được đọc là `trên`.
  Cùng một grammar xử lý `$44/thùng`, `$57,8/thùng`, `123,45 USD/Thùng`,
  `EUR 12–15/kg`, `6,23 USD/gallon` và `$4,47/100 gallon/ngày`.
  `gallon`/`gal` được thêm vào từ điển đơn vị, không đổi sang lít.
  Cấu trúc tiền tệ cơ bản hoạt động cả khi tắt domain `news`.
- **Hoa/thường:** tên đơn vị viết bằng chữ như `thùng`, `Thùng`, `THÙNG`,
  `gallon`, `Gallon` dùng chung cách đọc. Ký hiệu SI và mã tiền vẫn phân biệt
  hoa/thường, ví dụ `mW` khác `MW`; không tự đổi `usd` thành `USD`.
- **Ngày tháng:** nhận khoảng ngày chung tháng bằng chữ, chung tháng/năm bằng
  `/`, hai ngày đầy đủ và khoảng ngày đặt trong ngoặc. Kiểm tra lịch thật, năm
  nhuận, thứ tự đầu/cuối; nhận khoảng trắng/tab và xuống dòng quanh dấu phân
  cách của khoảng ngày đầy đủ. Ngoặc của khoảng ngày được giữ làm dấu câu,
  không phát âm `mở ngoặc`. Phép tính có cue `tính`, `biểu thức`, `phép tính`
  hoặc nằm trong biểu thức dài hơn tiếp tục dùng cách đọc toán học.
- **Nhóm nghìn:** số có nhóm ba chữ số sau dấu chấm gắn với đơn vị đo/danh từ
  đếm đã biết dùng cách đọc hàng nghìn của tiếng Việt. Cấu hình locale rõ ràng
  luôn được ưu tiên; `1.000 km²` với locale `en` vẫn là số thập phân.
- **Chunk tên người:** nhận cấu trúc tên có chữ cái viết tắt; không cắt câu tại
  dấu chấm của `Donald J. Trump`, `Samuel A. Alito`, `J. R. R. Tolkien`.
  Wrapper chia theo từ giữ cả tên khi tên nằm trong giới hạn `max_char`.
- **Giữ cấu trúc chưa rõ:** ngày không hợp lệ, đơn vị lạ, tỷ giá `USD/VND`,
  URL/code/control tag vẫn được bảo vệ; không chỉ normalize nửa đầu đơn vị
  như `44 USD/thùng / unknown`.

Các chữ số cụ thể trong ví dụ không tham gia lựa chọn quy tắc. Bộ kiểm thử
[tests/test_evaluation_regressions.py](tests/test_evaluation_regressions.py)
bao gồm toàn văn gốc (có dấu `/` bị xuống dòng), CSV, kiểm tra đối chiếu phép
chia/phân số/địa chỉ/điểm số, 7.200 biến thể giá tiền được sinh từ seed cố định,
150 khoảng ngày sinh tự động và lịch tháng của cả năm nhuận/năm thường.

Chạy kiểm thử mã nguồn trong checkout sau khi cài editable:

```bash
python -m pip install --no-deps -e ./norm
python -m pytest tests/test_vi_normalizer*.py norm/tests -q
```

Kết quả normalize toàn văn nằm trong
[reports/danhgia_normalized_0_9_0.txt](reports/danhgia_normalized_0_9_0.txt);
[reports/danhgia_evaluation_0_9_0.json](reports/danhgia_evaluation_0_9_0.json)
ghi kết quả các đoạn lỗi, hash đầu vào và các span còn giữ chữ số. Đây là kiểm
tra văn bản/quy tắc, chưa phải đánh giá âm thanh TTS hoặc cam kết chính xác
cho mọi câu tiếng Việt.

## Kiểm tra chéo và bản sửa 0.9.1

Lượt kiểm tra chéo sau 0.9.0 phát hiện thêm các nhóm lỗi ngoài bộ biến thể số
ban đầu. [tests/test_crosscheck.py](tests/test_crosscheck.py) kiểm tra 55 ca
tham số hóa, gồm các thay đổi về cấu trúc và ngữ cảnh:

- Khoảng giá lặp tiền tệ ở hai đầu (`$40–$50/thùng`, `€5–EUR7/kg`) dùng cùng
  ngữ pháp khoảng giá. Hai đầu khác tiền tệ hoặc khoảng đảo chiều được giữ
  nguyên; không suy đoán tỷ giá.
- Ngày đơn có xuống dòng quanh dấu phân cách vẫn giữ đầy đủ ngày, tháng và
  năm. Reader kiểm tra toàn bộ chuỗi thay vì chỉ đọc đến cuối dòng đầu tiên.
- Cue toán học áp dụng cho toàn biểu thức (`tính 6/2 - 3/1`); quan hệ rõ ràng
  như `6/8/2026=1` ưu tiên cách đọc toán. Biểu thức kèm nhóm đơn vị giữ nguyên
  phạm vi nhóm. Ngày tháng không có tín hiệu toán vẫn được đọc theo lịch.
- Tên có chữ cái viết tắt nhận một lần xuống dòng, và nhận nhiều chữ cái viết
  tắt sau từ thường. Cue chỉ nhãn như `Mục A.`, `Phần B.`, `Chọn A.` tiếp tục
  cho phép ngắt câu. Đây là nhận diện theo cấu trúc/ngữ cảnh, không phải nhận
  diện thực thể tên người hoàn chỉnh.
- Đơn vị đếm có lũy thừa không được chuẩn hóa một phần khi số mũ có khoảng
  trắng, ví dụ `$44/thùng ^ 2`.

**1.345 test đạt**, gồm toàn bộ kiểm thử cũ và 55 ca kiểm tra chéo mới. Số test
đạt chứng minh các cấu trúc đã kiểm tra, không chứng minh mọi câu tiếng Việt
đều đúng. Chưa kiểm tra chất lượng âm thanh TTS.

## Nâng cấp 0.10.0: viết tắt phổ biến, số theo văn bản, ngày/khoảng và mã

Bản này sửa các lỗi normalize được ghi lại khi nghe ba bộ đánh giá TTS trong
[`danhgia/`](danhgia/): 15 lỗi của `danhgia_tts_02` và `danhgia_tts_03` (tái hiện
y hệt trên 0.9.1) cùng các lỗi cùng nhóm còn sót trong toàn văn. Quy tắc dựa trên
hình thức và ngữ cảnh; normalizer không đọc các file đánh giá và không so khớp
câu mẫu. Các mục "Mới trong 0.x" và "Nâng cấp 0.9.0" ở trên là lịch sử phát hành;
khi mô tả khác mục này (ví dụ `AI`/`CP`/`BS` được giữ nguyên, chuỗi mơ hồ `1.234`
được bảo vệ) thì hành vi mặc định hiện hành là hành vi ghi ở đây.

| Nhóm | Thay đổi |
|---|---|
| Chữ viết tắt | Thứ tự quyết định cho token in hoa: `abbreviation_overrides` → bảng nhỏ `COMMON_ABBREVIATIONS` → đánh vần từng chữ cái (`acronym_mode="spell"`) → giữ nguyên. Mục "đọc như từ" (`NATO`, `AI`, `GPT`, `COVID`) áp dụng cả trong mã (`GPT-6` → gi pi ti sáu); mục mở rộng (`UBND`, `VN`) chỉ áp dụng khi đứng riêng. Chữ `O` trong bảng chữ cái đọc là "ô" (`ODA` → ô đê a) |
| Điều kiện đánh vần | Chỉ gồm `A–Z`, `Đ`, dài từ 2 chữ; không dấu chấm (`J.R.R.`), không nguyên âm mang dấu tiếng Việt (`NÓNG`), không phải số La Mã I/V/X; tối đa 4 chữ nếu có nguyên âm, 8 chữ nếu không. Từ in hoa liền kề một từ tiếng Việt in hoa (`TIN NÓNG`, `VIỆT NAM`) được giữ nguyên |
| Số mơ hồ `1.234`/`1,234` | `ambiguous_number` chỉ tác động khi `number_locale="auto"` và chỉ với dạng một dấu phân cách + đúng ba chữ số. `infer` đếm bằng chứng trong chính văn bản đang xử lý (`1.234.567`, `1.234,5`, `6,23` là kiểu Việt; `1,234,567`, `1,234.5` là kiểu Anh), chọn kiểu Anh chỉ khi bằng chứng Anh nhiều hơn. `3.14`, `1.234.567`, `0.005` giữ cách đọc cũ |
| Ngày | D/M không có từ khóa là ngày khi có cue thứ/dịp (`thứ Sáu (25/9)`), khi ngày > tháng (`25/9`) hoặc khi nằm trong danh sách ngày (`16/10 và 10/11`); `3/4`, `chiếm 1/3`, `gấp 5/3 lần` vẫn là phân số. `tối 27.9` (có cue) là ngày, còn `27.9%` và `27.95` thì không |
| Khoảng | `ngày 24-25` → hai mươi tư đến hai mươi lăm (`ngày 3-5` vẫn là ngày 3 tháng 5, quy ước báo chí Việt). Khoảng năm không cue: `2026-2030`, `2027–2029`, `2027-28`; không áp dụng sau cue toán (`tính …`) hay trong timestamp ISO. `Thế chiến II` → Thế chiến hai |
| Ký hiệu, đơn vị | `+` và `&` đứng riêng giữa hai khoảng trắng đọc "cộng" và "và". `2K`, `4K`, `8K` liền đọc "… ca" (`300 K` có khoảng trắng vẫn là kelvin). Thêm `mAh`, `MP`, `nit`/`nits`, `euro` |
| Mã chữ-số | Mã có chữ in hoa đọc theo thành phần: số tới 3 chữ số không có số 0 đầu đọc như số đếm (`G20` → gờ hai mươi), số dài hơn hoặc có số 0 đầu đọc từng chữ số (`RTX4090`, `CVE-2026-65660`). Chữ thường (`20k`, `60fps`, `3tsp`) do rule đơn vị xử lý như trước |
| Ngoặc mở | `(` không cân bằng trước số/đơn vị (`(40% đến 2026`) không còn làm mất cách đọc phần còn lại |

Một số ví dụ, đầu ra thực tế của hai phiên bản với mặc định:

| Đầu vào | 0.9.1 | 0.10.0 |
|---|---|---|
| `năm học 2027-28` | giữ nguyên | năm học hai nghìn không trăm hai mươi bảy đến hai nghìn không trăm hai mươi tám |
| `Tập đoàn SK` | Tập đoàn sân khấu | Tập đoàn ét ca |
| `chuyến thăm của BTS` | chuyến thăm của Ban tuyển sinh | chuyến thăm của bê tê ét |
| `pin 7.000mAh` | giữ nguyên | pin bảy nghìn mi li am pe giờ |
| `quanh 4.265 USD một ounce` | giữ nguyên | quanh bốn nghìn hai trăm sáu mươi lăm đô la một ounce |
| `Washington ngày 24-25. Hai bên` | giữ nguyên | Washington ngày hai mươi tư đến hai mươi lăm. Hai bên |
| `hôm thứ Sáu (25/9)` | hôm thứ Sáu (hai mươi lăm trên chín) | hôm thứ Sáu (hai mươi lăm tháng chín) |
| `Tới tối 27.9` | Tới tối hai mươi bảy phẩy chín | Tới tối hai mươi bảy tháng chín |
| `SharePoint CVE-2026-65660` | giữ nguyên | SharePoint xê vê e hai không hai sáu sáu năm sáu sáu không |
| `RAIBO2 đã chạy 42,195 km` | giữ nguyên | RAIBO hai đã chạy bốn mươi hai phẩy một chín năm ki lô mét |

### Cấu hình và tương thích ngược

| Trường | Hành vi 0.9.1 | Mặc định 0.10.0 |
|---|---|---|
| `abbreviation_policy` | (chưa có; tương đương `"extended"`) | `"common"` (hoặc `"extended"`, `"none"`) |
| `acronym_mode` | `"preserve"` | `"spell"` |
| `ambiguous_number` | (chưa có; tương đương `"preserve"`) | `"infer"` (hoặc `"vi"`, `"en"`, `"preserve"`) |

Tái tạo hành vi 0.9.x cho phần viết tắt và số mơ hồ:

```python
legacy = Normalizer(NormalizerConfig(
    abbreviation_policy="extended", acronym_mode="preserve", ambiguous_number="preserve",
))
legacy.normalize("Tập đoàn SK; giá 4.265 USD")  # Tập đoàn sân khấu; giá 4.265 USD
```

Các sửa lỗi về ngày, khoảng, mã, ký hiệu và đơn vị luôn được bật. CLI có thêm
`--abbreviations {common,extended,none}` và `--ambiguous-number {infer,vi,en,preserve}`;
`--acronyms` không còn mặc định riêng. Cờ không được truyền sẽ không ghi đè mặc định
của `NormalizerConfig`, nên CLI luôn khớp API. `COMMON_ABBREVIATIONS` được export từ package.

```bash
python -m vietnamese_tts_normalizer 'Tập đoàn SK; giá 4.265 USD; ngày 25/9'
# Tập đoàn ét ca; giá bốn nghìn hai trăm sáu mươi lăm đô la; ngày hai mươi lăm tháng chín
python -m vietnamese_tts_normalizer --abbreviations extended --acronyms preserve \
  --ambiguous-number preserve 'Tập đoàn SK; giá 4.265 USD'
# Tập đoàn sân khấu; giá 4.265 USD
```

### Kiểm chứng

**1.480 test đạt**: 1.345 test của 0.9.1, 133 test mới ở
[tests/test_upgrade_0_10_0.py](tests/test_upgrade_0_10_0.py) (bảng nghiệm thu, chính sách
viết tắt, ổn định hai lượt `N(N(x)) == N(x)`, CLI) và 2 ca tham số thêm khi cập nhật test cũ.
100 test cũ đổi có chủ đích vì mặc định đã đổi: các test về tính mơ hồ của số được ghim
bằng `ambiguous_number="preserve"`, còn lại được cập nhật sang cách đọc mới theo
Phụ lục A của tài liệu kế hoạch.

Kết quả normalize toàn văn của ba bộ đánh giá nằm trong
[reports/danhgia_normalized_0_10_0.txt](reports/danhgia_normalized_0_10_0.txt);
[reports/danhgia_evaluation_0_10_0.json](reports/danhgia_evaluation_0_10_0.json) ghi bảng
nghiệm thu, hash đầu vào/mã nguồn, token còn chữ số hoặc ký hiệu và thời gian. Chi tiết thiết
kế, các bất biến và các quyết định cần nghe thử nằm trong
[kế hoạch nâng cấp 0.10.0](../docs/vi_normalization_upgrade_plan_0_10_0.md).

Đây là kiểm tra văn bản, **chưa phải đánh giá âm thanh**. Cách đọc `AI` → ây ai,
`H` → hắt hay `LG` → lờ gờ là lựa chọn có thể đổi bằng `abbreviation_overrides`; cần tạo
lại audio bằng đúng pipeline TTS và nghe lại các chunk đã báo lỗi trước khi coi là đạt.

## Nâng cấp 0.11.0: viết tắt kiểu Latin, ký hiệu văn bản, khoảng "từ … đến", số La Mã và tiền tệ

Bản này thực hiện review nghe thử `danhgia_tts_02` → `danhgia_tts_05` (model
`g-omnivoice`) và các quyết định đi kèm. Mỗi quy tắc được viết cho **cả một nhóm hình thức**
(kiểm tra bằng nhóm test G trong
[tests/test_upgrade_0_11_0.py](tests/test_upgrade_0_11_0.py)), không so khớp câu mẫu.

| Nhóm | Hành vi 0.11.0 |
|---|---|
| Viết tắt (`acronym_mode="latin"`, mặc định) | `override` → bảng `COMMON_ABBREVIATIONS` → tiêu đề in hoa tiếng Việt giữ nguyên → `classify_acronym`: 2 chữ giữ nguyên (`AI`, `LG`, `EU`, `SK`) trừ khi trùng một âm tiết tiếng Việt (`IT`, `UN`, `IP`, `XE` → tách chữ, vì model sẽ đọc thành từ); 3 chữ tách chữ Latin (`GDP` → G D P, `CEO` → C E O); ≥ 4 chữ giữ nguyên nếu đọc được như một từ tiếng Anh (`BRICS`, `JAMSTEC`, `POWERR ASIA`, `WIPO`), ngược lại tách chữ (`OECD`, `CSIS`, `EVFTA`). Có `Đ` thì tách (`ĐH` → Đ H). Ngoại lệ ngắn: `IMEI`, `ICAO` luôn tách; `NVIDIA`, `TOP`, `HOT`, `NEW`, `NEWS`… luôn giữ |
| Bảng `COMMON` | Bỏ `AI`, `IT`, `CEO`, `GPT`, `ID`, `BRICS` (chuyển sang `LEGACY_SAY`, chỉ dùng ở `acronym_mode="spell"`). Giữ `NATO` → na tô, `ASEAN`, `NASA`, `COVID`, `TV`, `OK`… |
| Mã chữ-số | Mã chỉ có chữ cái đơn giữ tên chữ cái tiếng Việt (`G7` → gờ bảy, `F-16` → ép mười sáu, `H5N1`, `lớp 12A1`). Mã có cụm ≥ 2 chữ đọc theo chính sách Latin (`C4ISR` → C bốn I S R, `RTX4090` → R T X bốn không chín không). Số trong mã có gạch: ≤ 2 chữ số hoặc số tròn trăm đọc như số đếm (`S-400` → ét bốn trăm), còn lại đọc từng chữ số |
| Ký hiệu văn bản | `02/NQ-CP` → không hai N Q C P; `57-NQ/TW` → năm mươi bảy N Q T W; `15/2020/NĐ-CP` → mười lăm năm hai nghìn không trăm hai mươi N Đ C P; `15/QĐ-TTg`, `36/2024/QH15`, `NĐ-CP` đứng riêng |
| Mã kỹ thuật | `AN/APX-127(V)1` → A N A P X một hai bảy V một; `AN/TPY-2`, `F/A-18E/F`. Cặp chỉ có chữ (`USD/VND`, `KM/H`, `ABC/DEF`) giữ nguyên |
| `&` và số nhiều | `M&A` → M và A, `AT&T` → A T và T; `CEOs` → C E O |
| Khoảng số | Khoảng có gạch đọc **"từ A đến B"** trừ khi đã có từ khung đứng trước (`khoảng`, `từ`, `trong`, `giai đoạn`, `cấp`, `Điều`, `năm học`…): `(20%-30%)` → (từ hai mươi phần trăm đến ba mươi phần trăm), `khoảng 20-30%` → khoảng hai mươi đến ba mươi phần trăm. `range_prefix=""` tắt chữ "từ". Đơn vị ở cả hai đầu (`5kg-10kg`, `5°C-10°C`), khoảng trong ngoặc (`(2024-2033)`), khoảng số nhỏ trước danh từ (`mất 4-5 ngày`) đều được đọc. Tỉ số trận đấu (`thắng 2-1`, `Việt Nam 3-1 Thái Lan`) và `3-5` đứng trơ trọi vẫn giữ nguyên vì mơ hồ |
| Thứ tự, quý, tháng | `thứ 1` → thứ nhất, `thứ 4` → thứ tư, `thứ 4-5` → thứ tư đến thứ năm, `tháng 4-5` → tháng tư đến tháng năm, `quý I–II/2026` → quý một đến quý hai năm … |
| Số La Mã | Thêm cue `cấp`, `mục`, `tập`, `giai đoạn`, `hạng`, `nhóm`, `bậc`, `phụ lục`, `vùng`, `hồi`, `khu vực`, `điều`; dãy nối lặp lại cue (`quý I và II` → quý một và quý hai, `chương I-III` → chương một đến chương ba); tên vua/giáo hoàng (`Elizabeth II` → Elizabeth đệ nhị, `Leo XIV` → Leo mười bốn); tiêu đề đầu dòng (`II. Nội dung`). `loại C`, `phần D` là nhãn chữ, không còn đọc thành 100/500 |
| Ký hiệu đầu dòng | `❶`, `①`, `⑴`, `(i)`, `(II)` (ở đầu dòng hoặc sau `:`/`;`) → một, hai… kèm dấu phẩy; `⒈` → một.; `Ⅱ` → hai |
| Tiền tệ | `USD` → đô la Mỹ; `US$`, `HK$`, `S$`, `A$`, `C$`, `NZ$`, `NT$`, `¥`, `₩`, `₹`, `₽`, `฿` và mã `AUD`, `SGD`, `HKD`, `TWD`, `THB`, `INR`, `RUB`… đọc theo nghĩa. `$` vẫn là `dollar_name` ("đô la"). `CAD` chỉ là tiền tệ khi đứng sau số |
| Tên phiên âm | Gạch nối trong chuỗi bắt đầu bằng âm tiết viết hoa đổi thành khoảng trắng: `Ả Rập Xê-út` → Xê út, `Bô-li-vi-a`, `Kim Jong-un`. `Hàn-Mỹ`, `quốc phòng-an ninh`, `drop-in` giữ nguyên |
| Chia câu OmniVoice | `G D P. Năm nay` được chia câu bình thường (không còn bị coi là tên viết tắt như `J. Trump`) |

### Cấu hình và tương thích ngược

| Trường | 0.10.0 | Mặc định 0.11.0 |
|---|---|---|
| `acronym_mode` | `"spell"` | `"latin"` (hoặc `"spell"`, `"preserve"`) |
| `range_prefix` | (chưa có) | `"từ"` (hoặc `""`) |
| Đọc `USD` | `dollar_name` ("đô la") | "đô la Mỹ" (`unit_overrides={"USD": "đô la"}` để giữ cách cũ) |

```python
legacy = Normalizer(NormalizerConfig(acronym_mode="spell", range_prefix="", unit_overrides={"USD": "đô la"}))
legacy.normalize("GDP tăng 20%-30%; 5 USD")  # gờ đê pê tăng hai mươi phần trăm đến ba mươi phần trăm; năm đô la
```

`acronym_mode="spell"` giữ nguyên cách đọc viết tắt của 0.10.0; các sửa lỗi khác (ký hiệu
văn bản, khoảng, số La Mã, ký hiệu đầu dòng, tiền tệ) vẫn bật với tên chữ cái tiếng Việt.
`acronym_mode="preserve"` giữ ký hiệu văn bản và mã kỹ thuật như 0.10.0. CLI:
`--acronyms {latin,spell,preserve}`.

### Kiểm chứng

**1.769 test đạt**: 1.480 test của 0.10.0 (cập nhật expected có chủ đích theo kế hoạch) và
289 test mới. Ổn định hai lượt `N(N(x)) == N(x)` được fuzz với 12 seed trên 7 cấu hình (mặc
định, spell, preserve, extended, `range_prefix=""`, không domain, `number_locale="vi"`):
không còn ca nào (0.10.0 có 6–62 ca mỗi cấu hình với cùng bộ fuzz); riêng
`preserve_case=False` còn lỗi `KM/H` có từ 0.10.0. Thời gian normalize toàn văn năm bộ đánh
giá tăng khoảng 3%. Chi tiết, bất biến và các quyết định cần nghe thử nằm trong
[kế hoạch nâng cấp 0.11.0](../docs/vi_normalization_upgrade_plan_0_11_0.md).

Đây là kiểm tra văn bản, **chưa phải đánh giá âm thanh**: cách model đọc `G D P`, `AI`, `Đ`
và chữ "từ" trước khoảng cần được nghe lại bằng đúng pipeline TTS.

## Nâng cấp 0.12.0: viết tắt tiếng Việt theo nghĩa, cụm viết tắt và lĩnh vực

Bản này thực hiện review ngày 2026-10-02 (`Bộ trưởng VH-TT-DL` → Bộ trưởng Văn hóa, Thể thao
và Du lịch; `T T X V N` → Thông tấn xã Việt Nam; `Mát xcơ va` → Mát cơ va) và yêu cầu mở rộng
tổng quát cho viết tắt tiếng Việt, **phân biệt ngữ cảnh và ngành nghề** ("lỡ đâu là PET/CT
thì sao"). Từ điển và ngữ cảnh nằm trong [vi_abbreviations.py](vi_abbreviations.py); test ở
[tests/test_upgrade_0_12_0.py](tests/test_upgrade_0_12_0.py).

| Nhóm | Hành vi 0.12.0 |
|---|---|
| Viết tắt một nghĩa (`ALWAYS`: 387 cách viết, 353 khóa) | Đọc ở mọi nơi trừ trong ký hiệu văn bản/mã: `TTXVN`, `HTX`, `ĐHĐCĐ`, `UBCKNN`, `NHNN`, `TCTD`, `LNST`, `BCTC`, `CCHC`, `THADS`, `TANDTC`, `BHXHVN`, `TLĐLĐVN`, `CSCĐ`, `ĐBSH`… Dạng là mã chứng khoán hoặc tên nước ngoài (`HSG`, `KDC`, `NCT`, `HSV`, `BTS`, `SK`) không có trong bảng |
| Cụm viết tắt | Mọi cách viết của một cụm có chung một khóa (bỏ `-`, `&`, `,`, khoảng trắng): `VH-TT-DL` = `VH,TT&DL` = `VHTTDL` = `VH - TT - DL`; `GD & ĐT`, `LĐ-TB&XH`, `KH&CN`, `NN&PTNT`, `TN-MT`, `NN&MT`, `DT&TG`, `BR-VT`, `ĐHQG-HCM`, `CNH-HĐH`. Cụm chưa có trong bảng được đọc từng phần khi mỗi phần chỉ có một nghĩa: `KT-XH-QP-AN` → kinh tế - xã hội - quốc phòng - an ninh, `UBND, HĐND & MTTQ` |
| Bộ, Sở, Phòng, ngành | Sau `Bộ`/`Sở`/`Phòng`/`ngành`, tên lĩnh vực ngắn được đọc: `Bộ TC` → Bộ Tài chính, `Sở TP` → Sở Tư pháp (không còn "Sở thành phố"), `Bộ CT` → Bộ Công Thương, `Bộ CA`, `Bộ QP`, `Sở YT`, `ngành GD`. Tiền tố B/S ghép với lĩnh vực: `BGDĐT` → Bộ Giáo dục và Đào tạo, `SKHĐT` → Sở Kế hoạch và Đầu tư. `BTC`, `BCT` mơ hồ nên không ghép |
| Dạng ngắn theo ngữ cảnh (`CONTEXTUAL`: 60 dạng, 111 nghĩa) | Đọc khi từ đứng cạnh xác định nghĩa: `BV Bạch Mai`, `BN 123`, `3 HCV`, `các HS`, `200 TS` (thí sinh), `TS Nguyễn Văn A` (tiến sĩ, sau là họ người Việt), `năm 111 TCN`, `TK XX`, `ĐH XIII` (Đại hội), `thi ĐH, CĐ`, `Thứ 2 - CN`, `Chủ tịch QH`, `CA tỉnh`, `QL 1A`, `ĐT 741`, `ĐT: 0912…` (điện thoại), `ĐT Việt Nam` (đội tuyển), `TNHH MTV`, `THPT QG`, `CT UBND` (chủ tịch), `Công ty CP`, `NĐ 100/2019`. Không có ngữ cảnh thì **không đoán**: giữ chính sách viết tắt như 0.11.0 |
| Lĩnh vực của câu | Từ khóa của 15 lĩnh vực (y tế, pháp luật, liệt sĩ, thể thao, hành chính, tài chính, tuyển sinh, đại học, năng lượng, du lịch, tuyển dụng, lao động, hải quan, đoàn thanh niên, ngân hàng) chọn nghĩa hoặc chặn nghĩa: `chụp CT 64 lát cắt`, `PET/CT`, `MRI và CT` giữ `CT`; `mộ LS …` → liệt sĩ, `LS … bào chữa` → luật sư; `tấm pin PV` giữ `PV`, `PV Gas` giữ, `PV Nguyễn Hà` → phóng viên; `phát hành TP doanh nghiệp` → trái phiếu, `TP Hà Nội` → thành phố; `mã HS 8471` giữ, `nộp HS` → hồ sơ; `các GV đại học` → giảng viên; `các NV xét tuyển` → nguyện vọng; `KS 5 sao` → khách sạn |
| Chú thích trong ngoặc | Viết tắt trong ngoặc ngay sau chính tên đầy đủ của nó được bỏ khi đọc: `Ủy ban nhân dân (UBND) tỉnh` → Ủy ban nhân dân tỉnh. `Hà Nội (TTXVN)` vẫn đọc; viết tắt nước ngoài `(WHO)` giữ như 0.11.0; `acronym_mode="preserve"` giữ chú thích |
| Dạng đặc biệt | `v.v.` → vân vân, `v/v` → về việc, `Đ/c` → đồng chí, `K/g` → kính gửi, `Cty`/`CTy` → công ty, `Tp HCM`/`Tp.HCM` → thành phố, `VD:`/`ĐC:`/`SL:` → ví dụ/địa chỉ/số lượng; chức danh có chấm `GS.TSKH`, `ThS.BS`, `BS.CKII` |
| Số hiệu văn bản | `Nghị định 100/2019`, `QĐ số 15/2020`, `Nghị định 12/2020` → số + "năm" + năm (trước đây đọc như phân số hoặc tháng). Ký hiệu đầy đủ (`15/2020/NĐ-CP`) giữ cách đọc 0.11.0 |
| Sửa lỗi | `UBND năm 2020`, `HĐND năm nay`, `BHXH một tháng` không còn bị đánh vần (trước đây bị coi như mã trước số); luật đường `ĐT` không còn nuốt số điện thoại (`ĐT: 0912 345 678`) |
| Tên phiên âm | Cụm phụ âm đầu âm tiết sau `x` bỏ `x`: `Mát-xcơ-va`, `Mátxcơva` → Mát cơ va; `Ô-xtrây-li-a` → Ô trây li a; `Xtốc-khôm` → Tốc khôm; `Kadắcxtan` → Ka dắc tan. Chỉ áp dụng cho từ có chữ cái tiếng Việt (`Xbox`, `X-quang`, `Pakixtan` giữ) |

Tính ổn định hai lượt được giữ bằng hai bất biến: (1) một viết tắt chỉ là từ khóa của một lĩnh
vực khi **mọi** nghĩa nó có thể được đọc đều thuộc lĩnh vực đó (tự suy từ từ điển: `BV` là từ
khóa y tế, `BS` thì không vì có thể là "biển số"); (2) lĩnh vực được xét trong câu, với ranh
giới câu không đổi qua các lượt (dấu chấm của `TP.`, `Q.`, `TS.` không phải ranh giới).

### Cấu hình và tương thích ngược

Không có trường cấu hình mới. Từ điển và ngữ cảnh mới chỉ dùng với `abbreviation_policy="common"`
(mặc định); `"extended"` và `"none"` giữ cách đọc viết tắt của 0.11.0. Quy tắc tên phiên âm áp
dụng cho mọi cấu hình. `abbreviation_overrides` vẫn có ưu tiên cao nhất.

### Kiểm chứng

**2.226 test đạt**: 1.769 test của 0.11.0 (3 expected đổi có chủ đích: `ĐH`/`CĐ`/`BCĐ` trong
G05, `Mát cơ va` trong G25, `UNESCO` → u nét cô) và 457 test mới. Ổn định hai lượt: 53.340
câu (mọi dạng trong từ điển × 15 khung câu × 7 cấu hình), fuzz 4 seed × 7 cấu hình và fuzz mở
rộng 50.400 câu có dấu chấm câu: 0 ca. Năm bộ đánh giá chỉ đổi đúng 3 chỗ được review
(`TTXVN`, `VH-TT-DL`, `Mát xcơ va`); thời gian normalize toàn văn tăng khoảng 3%.

## Nâng cấp 0.13.0: mã sản phẩm, mác xăng dầu và tên miền

Review ngày 2026-10-02: `TEI-TF6000` → T E I T F sáu ngàn, `xăng E5RON 92` → xăng e năm ron
chín hai, `chinhphu.vn/TG` → chính phủ chấm vi en. Test:
[tests/test_upgrade_0_13_0.py](tests/test_upgrade_0_13_0.py).

| Nhóm | Hành vi 0.13.0 |
|---|---|
| Mã chữ-số | Cụm 2 chữ trong mã được tách chữ như cụm 3 chữ (`TF6000` → T F…, `MQ-9` → M Q chín, `MH370`, `Su-30MK2` → M K hai). Số tròn nghìn đọc như số đếm (`6000` → sáu nghìn, `10000` → mười nghìn, theo `thousand`); số khác ≥ 4 chữ số vẫn đọc từng chữ số (`4090`, `9300`). Cấp La Mã sau số là số (`RON95-III` → … ba); `95-III` không còn bị coi là ký hiệu văn bản |
| Mác xăng dầu | `RON` đọc "ron"; số sau `RON` đọc kiểu nói tắt (`92` → chín hai, `95` → chín lăm, `97` → chín bảy); `E5RON92`, `E10RON 95`, `RON 95-III`, `E5 RON92-II`; `xăng A95` → xăng a chín lăm (không có "xăng" thì giữ cách đọc cũ); `dầu DO 0,05S-II` → dầu đê ô không phẩy không năm ét hai; `dầu FO 3,5S` |
| Số và đơn vị còn sót | Khoảng số có dấu phân cách nghìn (`khoảng 14.000–17.000 feet` → khoảng mười bốn nghìn đến mười bảy nghìn phít, `3.000–5.000 đơn vị`); tiền tệ viết bằng chữ (`5.150 riel/lít`, `baht`, `kíp`, `yên`, `won`, `rúp`, `ringgit`, `rupiah`, `rupee`, `peso`) đọc số theo kiểu Việt như `đồng`; đơn vị `feet`/`ft` → phít, `dặm`; cặp mã nối `/` (`5G/6G` → năm gờ, sáu gờ; `4G/LTE` → bốn gờ, L T E; `USD/VND` giữ). Luật số điện thoại không còn nuốt chữ số đứng sát chữ cái (`điện thoại 4G/LTE`) và được xét trước đơn vị ghép (`0912345678 KM/H`) |
| Tên miền | Tên miền trơn được đọc: nhãn tiếng Việt không dấu được tách từ và trả dấu (`chinhphu` → chính phủ, `dichvucong`, `thuvienphapluat`, tên 63 tỉnh thành), tên trang quen thuộc theo bảng (`vnexpress`), nhãn tiếng Anh/thương hiệu giữ nguyên (`google`, `YouTube`), còn lại tách chữ (`vtv`). Đuôi `vn` → vi en, `com`, `net` → nét. Chữ ký tắt sau dấu `/` trong chú thích (`chinhphu.vn/TG`) không đọc. URL có scheme/đường dẫn/tham số, email, nội dung trong `[...]` và code giữ nguyên |

Cấu hình: `link_mode` thêm giá trị `"domain"` và dùng làm mặc định; `"preserve"` cho lại hành vi
0.12.0. Kiểm chứng: **2.390 test đạt** (2.226 của 0.12.0, 8 expected đổi có chủ đích do tách
chữ cụm 2 chữ trong mã, và 164 test mới); fuzz 4 seed × 7 cấu hình và fuzz có dấu câu: 0 ca lỗi
(cấu hình chữ thường còn lỗi `KM/H` có từ 0.10.0); năm bộ đánh giá đổi 31 chỗ, đều thuộc các nhóm
trên, và không còn chữ số/ký hiệu sót (kể cả các văn bản mới thêm vào `danhgia_tts_05`).

## Bản sửa 0.13.1: tỷ giá, số trước ngoặc, số viết lại bằng chữ, thứ/tháng và từ ghép kiểu mã

Review ngày 2026-10-05 trên `danhgia_tts_06`: tỷ giá `25.338 đồng/USD`, `26.060-26.470 VND/USD`
bị giữ nguyên chữ số; `localStorage` model không đọc được. Test:
[tests/test_upgrade_0_13_1.py](tests/test_upgrade_0_13_1.py).

| Nhóm | Hành vi 0.13.1 |
|---|---|
| Tỷ giá | Số tiền + `đồng`/`VND`/`VNĐ`/`đ` `/` ngoại tệ đọc "đồng trên …": `25.338 đồng/USD` → hai mươi lăm nghìn ba trăm ba mươi tám đồng trên đô la Mỹ; khoảng và số thập phân (`24.071,1-26.604,9 VND/USD`, `34.457,37-35.920,12 VND/GBP`). Cặp khác (`5 USD/VND`, `1,08 EUR/USD`) và cặp không có số (`tỷ giá VND/USD`) giữ nguyên vì phụ thuộc quy ước niêm yết |
| Số trước ngoặc | Khi không cách đọc nào bao trọn cả cụm, số được đọc riêng và phần trong ngoặc được đọc như văn bản thường: `giai đoạn 1 (300 MW)` → giai đoạn một (ba trăm mê ga oát), `Điều 5 (khoản 2)`, `giai đoạn 2 (2026-2030)`, `mục 4 (b)`. Ngoặc phải chứa số hoặc một chữ cái; `2(3+4)`, `1 (2 + 3) kg`, `5 (kgm/s)` giữ nguyên. Ngoặc đứng trước dấu phẩy liệt kê được tách khỏi số tiền sau nó (`(2026-2030), 26.000 VND/1 USD`) |
| Số viết lại bằng chữ | Kiểu văn bản hành chính đọc một lần: `05 (năm) ngày` → năm ngày, `02 (hai) bản`, `15 (mười lăm) ngày`, `1.500.000 (một triệu năm trăm nghìn) đồng` (so khớp cả `linh/lẻ`, `nghìn/ngàn`, `tư/bốn`, `mốt/một`, `lăm/năm`). Chữ không khớp số thì giữ sau số: `10 (năm)` → mười (năm) |
| Thứ, tháng, quý, ngày | `thứ 05` → thứ năm, `thứ 04` → thứ tư, `tháng 4` → tháng tư (như `tháng 4-5`, `ngày 3/4`), `tháng 05` → tháng năm, `quý 01` → quý một, `ngày 05` → ngày năm. `mỗi/hằng tháng 4 buổi` vẫn là bốn; `phòng số 05`, `năm 05` vẫn đọc từng chữ số. Ngữ cảnh thứ trong tuần nhận cả dạng số (`thứ 5 (3/4)` → ba tháng tư, `thứ 04 và CN` → chủ nhật) |
| Từ ghép kiểu mã | Từ tiếng Anh viết liền bắt đầu bằng chữ thường được tách: `localStorage` → local Storage, `getElementsByClassName`, `useState`, `onClick`. Thương hiệu và đơn vị giữ nguyên (`YouTube`, `MacBook`, `iPhone`, `eBay`, `McDonald`, `kWh`, `mmHg`); từ kết thúc bằng `Id`/`Otp`/`Version`… không tách vì sẽ biến số sau nó thành mã |
| Khoảng số | `quanh`, `xấp xỉ` đóng vai như `khoảng`: `quanh 26.250-26.280 VND/USD` không thêm "từ" |

Cấu hình: không có trường mới; `split_camel_case=False` tắt việc tách từ ghép. Kiểm chứng: **2.568
test đạt** (2.390 của 0.13.0 không đổi, 178 test mới); fuzz 4 seed × 7 cấu hình, fuzz có dấu câu
và 53.550 câu trên toàn bộ từ điển: 0 ca không ổn định mới so với 0.13.0; sáu bộ đánh giá đổi 13
chỗ (12 trong `danhgia_tts_06`, `tháng 4` → tháng tư trong `danhgia_tts_05`), không còn chữ
số/ký hiệu sót; thời gian tăng khoảng 2%.

## Bản sửa 0.13.2: phần thập phân hai chữ số đọc như số

Review ngày 2026-10-05: `34.457,37-35.920,12` → "phẩy ba mươi bảy", "phẩy mười hai" (0.13.1 đọc "phẩy ba
bảy", "phẩy một hai"). Test: [tests/test_upgrade_0_13_2.py](tests/test_upgrade_0_13_2.py).

| Nhóm | Hành vi 0.13.2 |
|---|---|
| Thập phân | `decimal_reading="auto"` (mặc định mới): phần thập phân đúng hai chữ số, không bắt đầu bằng 0, đọc như số: `3,75%` → ba phẩy bảy mươi lăm phần trăm, `1,75 m`, `2,50 USD` → hai phẩy năm mươi, `3,14` → ba phẩy mười bốn, `59,94fps`. Có 0 đứng đầu hoặc từ ba chữ số trở lên vẫn đọc từng chữ số: `0,05` → không phẩy không năm, `3,05`, `1,125`, `3,14159`. `"digits"` cho lại cách đọc 0.13.1, `"cardinal"` đọc mọi phần thập phân như số |
| Đơn vị | `ounce`/`ounces` → ao xơ như `oz`: `2.650 USD/ounce` |

Kiểm chứng: **2.618 test đạt** (2.568 của 0.13.1, 21 expected đổi đúng phần thập phân; 50 test mới); fuzz
4 seed × 7 cấu hình, fuzz có dấu câu và 53.550 câu từ điển: 0 ca không ổn định mới so với 0.13.1; sáu bộ
đánh giá đổi 13 chỗ, đều là phần thập phân hai chữ số; thời gian không đổi.

## Bản sửa 0.13.3: ki lô lít, đơn vị sau "mỗi", CEO, chữ T sau số, địa danh, số đếm kiểu Anh

Review ngày 2026-10-05 trên `danhgia_tts_06`. Test: [tests/test_upgrade_0_13_3.py](tests/test_upgrade_0_13_3.py).

| Nhóm | Hành vi 0.13.3 |
|---|---|
| Đơn vị | `kl`/`kL`, `kilolitre(s)`, `kiloliter(s)`, `kilolít` → ki lô lít; `litre(s)`, `liter(s)` → lít. Đơn vị đứng sau `mỗi` mà không có số cũng được đọc: `$1.100 mỗi kl` → … mỗi ki lô lít, `mỗi kg`, `mỗi km`, `mỗi ha`, `mỗi MW` (đơn vị một chữ cái như `m`, `T` thì không) |
| Chức danh | `CEO` → xi i ô (model đọc `C E O` thành "cê e ô"); cùng họ: `CFO` → xi ép ô, `CTO` → xi ti ô, `COO` → xi ô ô, `CMO` → xi em ô. Các viết tắt nước ngoài khác vẫn theo quy tắc Latin (`G D P`, `AI`) |
| Chữ T sau số | `T` là tét la chỉ khi có ngữ cảnh từ trường (`MRI 3T`, `nam châm 1,5T`, `từ trường`), là tấn khi nói về xe/trọng tải (`xe tải 5T`), còn lại đọc là chữ "tê" như `800G` → tám trăm gờ: `mô-đun 1,6T` → một phẩy sáu tê, `dầu nhớt 4T` → bốn tê |
| Địa danh viết kiểu Anh | Thủ đô và thành phố lớn có tên Việt quen dùng (`norm/places.py`): `Moscow` → Mát cơ va, `Kyiv`/`Kiev` → Ki ép, `Washington` → Oa sinh tơn, `London` → Luân Đôn, `Paris` → Pa ri, `Berlin`, `Rome`, `Geneva`, `Brussels`, `Tehran`, `Tokyo`, `Seoul`, `Bangkok`, `Singapore` → Xin ga po, `Manila`, …; thành phố Trung Quốc viết pinyin đọc tên Hán Việt (`Beijing` → Bắc Kinh, `Taipei` → Đài Bắc, `Changzhou` → Thường Châu). `SGD` đọc "đô la Xin ga po" để hai lượt cho cùng kết quả. Tắt bằng `abbreviation_policy="none"` |
| Số đếm kiểu Anh | Trước danh từ đếm (`điểm`, `người`, `lượt`, `hộ`, …), số có nhóm ba chữ số sau dấu phẩy là hàng nghìn: `quanh 1,850 điểm` → một nghìn tám trăm năm mươi điểm (0.13.2: "một phẩy tám năm không"), `1,750-1,800 điểm`, `1,845 người`. `1,5 điểm`, `8,25 điểm` vẫn là thập phân; đơn vị đo (`1,845 km`) giữ cách đọc cũ |

Kiểm chứng: **2.736 test đạt** (2.618 của 0.13.2, 7 expected đổi có chủ đích: `CEO` và `Washington`,
`đô la Singapore`; 118 test mới); fuzz 4 seed × 7 cấu hình (61.180 câu, 0 lỗi), fuzz có dấu câu và
53.550 câu từ điển: 0 ca không ổn định mới so với 0.13.2; thời gian không đổi.
