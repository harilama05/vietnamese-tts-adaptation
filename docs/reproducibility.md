# Nguồn gốc, giới hạn và kiểm chứng

## Phạm vi đã chọn

Theo quyết định của chủ dự án: tập trung nhánh **G-OmniVoice full fine-tune** và kết thúc ở **checkpoint 17.500**. Các nhánh LoRA, model khác, crawl notebook và thử nghiệm ngoài điểm kết thúc này không thuộc nội dung repo. Thư mục lưu trữ gốc và vùng làm việc tạm đã được xóa khỏi thư mục dự án sau khi chủ dự án xác nhận có bản sao riêng.

| Thành phần | Nguồn trong thư mục ban đầu |
| --- | --- |
| Prepare/tokenize/config/train runner | `Month3/Day1-2/g_omnivoice_full_finetune_v2.zip` |
| Evaluation scripts và 17 văn bản | `eval17/` trong bundle trên |
| Normalizer 0.13.3 | `code_snapshot/norm/` trong kết quả đánh giá 17.500 |
| 101 chunk chuẩn, summary, per-case metrics | Kết quả đánh giá 17.500 trong `Month3/Day1-2/` |
| Manual review | Hai workbook 17.500 trong `Month3/Day1-2/`, xuất cached cell values sang CSV |

[source_map.json](../reports/source_map.json) ghi đường dẫn nguồn tương đối và SHA256 trước khi tổ chức. Các đường dẫn Month3 và prefix `.repo_work/` là vị trí lịch sử trước khi dọn thư mục, không phải đường dẫn còn tồn tại hoặc dependency để chạy repo. Mã vận hành đã chỉnh đường dẫn, step mặc định và kiểm tra lỗi; hash nguồn là hash trước các chỉnh sửa đó.

## Những gì chưa có

- CSV `combined_train_shuffled.csv` và corpus audio đầy đủ.
- Script/log chứng minh cách tạo chính xác CSV cuối từ các nguồn trước đó.
- Frozen train config, data config, launcher log, optimizer/scheduler state của run 17.500.
- Bản sao upstream Git và lockfile môi trường đúng tại thời điểm train.
- Full checkpoint directory đầy đủ. File `model.safetensors` rời trong bản lưu trữ chưa đủ metadata để xác nhận độc lập step và resume.
- Reference WAV gốc chưa được xác nhận trong tập file đã tổ chức; transcript/hash được giữ trong metadata đánh giá.

Không tự gán dataset size, số giờ, GPU train, số epoch hoặc danh tính checkpoint cho weights rời khi chưa có bằng chứng. Các file riêng vẫn có thể được chủ dự án bổ sung sau bằng đường dẫn cấu hình.

## Đã thay đổi khi tổ chức repo

- Mặc định đích train và eval thành 17.500, giữ recipe còn lưu nhưng ghi rõ giới hạn chứng cứ.
- Thay đường dẫn máy cũ bằng project root và `configs/local.env`.
- Giữ nguyên logic chunking, normalization 0.13.3 và generation benchmark.
- Prepare từ chối ghi đè output, kiểm tra partition size và encode ID an toàn cho shard.
- Token cache phụ thuộc nội dung manifest và tokenizer; xác minh shard tồn tại và đủ số dòng, không công bố master list khi build bị ngắt.
- Ghi Hub commit khi tải initialization mới; setup lưu môi trường cho lần chạy mới.
- Bỏ qua dữ liệu riêng, cookie, model weights, cache và các output lớn bằng Git ignore.

## Kiểm tra

`python -m unittest discover -s tests -v` kiểm tra dữ liệu giả có cấu trúc thực, manifest failure, duplicate IDs, config 17.500, token cache và tái tạo **toàn bộ 101 chunk** từ văn bản gốc. Tokenizer GPU được mock trong bài cache; bài này chứng minh orchestration và kiểm tra metadata, chưa chứng minh codec chạy trên GPU.

`python scripts/check_repo.py` đọc danh sách file Git theo ignore hiện tại để kiểm tra cú pháp Python, kích thước và vài định dạng token phổ biến. Đây không phải bằng chứng phát hiện mọi loại bí mật. Dữ liệu gốc không được in hoặc sao chép vào repo để quét cookie.

Snapshot `norm/tests/` có các test cũ tham chiếu fixture của repo upstream không được lưu trong archive. CI chỉ chạy acceptance suite 0.13.3 độc lập và test pipeline mới; không khẳng định toàn bộ historical test suite chạy được.

Huấn luyện GPU, tải gated checkpoint và end-to-end synthesis/scoring cần môi trường CUDA cùng dữ liệu riêng. Chúng chưa được chạy lại khi tổ chức repo. CI đề xuất chạy Python 3.10/3.12 trên Linux; Python 3.12 là lựa chọn cho môi trường GPU.

Kết quả kiểm tra cục bộ ngày 2026-11-01 trên Windows/Python 3.13.11: **9 test pipeline và 118 test acceptance normalizer 0.13.3 đều đạt**. Git Bash kiểm tra cú pháp tất cả runner và hai lệnh help hoạt động khi chưa cài upstream/GPU. Các ma trận Linux/Python trong CI chưa chạy trên GitHub ở thời điểm bàn giao.

## Nguồn đối chiếu

- [OmniVoice training config tại commit đã ghi nhận](https://github.com/k2-fsa/OmniVoice/blob/08be0b4ccbac3e13e374e86fbfead4b4cac343e2/omnivoice/training/config.py).
- [Audio token extractor tại cùng commit](https://github.com/k2-fsa/OmniVoice/blob/08be0b4ccbac3e13e374e86fbfead4b4cac343e2/omnivoice/scripts/extract_audio_tokens.py).
- [Model card G-OmniVoice](https://huggingface.co/g-group-ai-lab/g-omnivoice).

Các link dùng để xác minh API/cài đặt, không dùng để thay thế số liệu thực nghiệm của dự án.
