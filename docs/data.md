# Dữ liệu cho nhánh G-OmniVoice

Đầu vào trực tiếp được xác nhận trong bundle full fine-tune v2 là `combined_train_shuffled.csv`. Repo không có CSV đó hoặc toàn bộ audio huấn luyện. Không có đủ bằng chứng để khẳng định CSV này là kết quả ghép chính xác từ các pipeline HTV/Podcast trước đó, vì vậy repo không tự dựng lại bước crawl/clean/merge.

## Schema CSV

| Cột | Bắt buộc | Ý nghĩa |
| --- | --- | --- |
| `dataset` | Có | Nguồn; trường rỗng được ghi là `unknown` |
| `segment_id` | Có | ID gốc; dòng có cùng segment ID vẫn được giữ riêng |
| `audio_path` | Có | File audio có thật trên máy chạy |
| `text` | Có | Nội dung transcript đã chuẩn bị; không được rỗng |
| `wer` | Không | Metadata, không dùng làm bộ lọc |

ID train kết hợp dataset, segment ID và số thứ tự dòng CSV. Ký tự phân cách đường dẫn trong ID được percent-encode để không tạo đường dẫn con trong token shard.

Manifest output:

```text
data/g_omnivoice/manifests/
├── train.jsonl
├── smoke.jsonl
├── manifest_report.json
└── parts/
    ├── train/part-00000.jsonl
    └── smoke/part-00000.jsonl
```

Mỗi dòng JSONL có `id`, `audio_path`, `text`, `language_id="vi"`, `dataset`, `segment_id`, `source_row` và có thể có `wer`.

`manifest_report.json` ghi SHA256 CSV, số dòng theo nguồn, cách resolve audio và lỗi. Bước prepare kiểm tra file tồn tại; nó chưa chứng minh audio khớp transcript hoặc file giải mã được. Tokenizer đọc audio thật ở bước sau.

## Chính sách phục hồi từ mã gốc

- Dùng toàn bộ CSV; không tạo dev split hoặc trọng số nguồn riêng.
- Không lọc theo WER, không tự sửa transcript và không normalize thêm.
- Audio: thử đường dẫn literal, sau đó vị trí tương đối với CSV/CWD/home; mount fallback giữ suffix `ai-data-02/...` theo logic gốc.
- Nếu có dòng rỗng hoặc thiếu audio, không xuất bản thư mục manifest cuối; report nằm trong thư mục `.tmp.<pid>` để kiểm tra.
- Prepare từ chối ghi đè output đã tồn tại. Tái sử dụng manifest cũ khi không đổi dữ liệu, hoặc chọn `WORK_ROOT` mới khi đổi CSV.
- Mỗi phần tokenize mặc định có tối đa 50.000 dòng. Cache kiểm tra hash manifest, nội dung tokenizer, các shard và số dòng trước khi bỏ qua một phần.

Đường dẫn output token và các shard không được chứa khoảng trắng vì upstream dùng định dạng `data.lst` tách bằng whitespace. Trên Linux hãy đặt `BASE_DIR` ở một đường dẫn phù hợp. Dùng ổ lưu trữ đủ chỗ; repo không chứa token shard mẫu.

Các phép so sánh chất lượng của dự án là benchmark nhỏ, không thay thế tập validation độc lập. Không suy ra khả năng tổng quát hóa chỉ từ loss train hoặc 17 văn bản này.
