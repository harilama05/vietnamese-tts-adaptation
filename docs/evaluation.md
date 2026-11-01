# Đánh giá checkpoint 17.500

## Quy trình

1. Parse 17 khối `Văn bản N:` trong [benchmark](../benchmarks/danhgia_tts.txt).
2. Chia theo logic gốc: raw target 330 ký tự, normalized maximum 430.
3. Normalize bằng snapshot `norm` phiên bản 0.13.3, lưu trace và các cảnh báo.
4. Dùng cùng reference voice/transcript, seed 42, 32 generation steps; truyền `normalize_text=False` vào model để tránh normalize lần hai.
5. Sinh 101 WAV, ghép từng văn bản với khoảng lặng 0,25 giây.
6. Whisper large-v3 chép từng chunk độc lập, tính WER/CER.
7. NISQA, DNSMOS, WavLM và signal metrics; tạo CSV, bảng tổng hợp theo văn bản và trang nghe HTML.

[Snapshot 101 chunk](../benchmarks/expected_shared_chunks.json) có content SHA256 `0879980c0099d1f448b416691ab1261ba1c3fc10c86098c8889962fb14c9bfe3`. Test CPU so sánh toàn bộ nội dung chunk, không chỉ số lượng.

## Kết quả được lưu

Nguồn dữ liệu: [thư mục checkpoint-17500](../reports/checkpoint-17500/). Các đường dẫn tuyệt đối HPC trong run config và prepare config được giữ như metadata lịch sử; runner mới không dùng các đường dẫn đó làm mặc định.

| Nhóm | File | Diễn giải |
| --- | --- | --- |
| Generation | [summary.json](../reports/checkpoint-17500/summary.json) | 101 chunk, 79,91 giây sinh / 1.391,53 giây audio; RTF tính bằng tổng thời gian chia tổng audio |
| Nội dung | [whisper_summary.json](../reports/checkpoint-17500/whisper_summary.json) | Mean WER 0,090160, mean CER 0,067603; trung bình theo chunk |
| Chất lượng | [objective_summary.json](../reports/checkpoint-17500/objective_summary.json) | Mean NISQA MOS 4,666840; DNSMOS OVRL 3,433894; speaker similarity 0,951994 |
| Screening | [audit_summary.json](../reports/checkpoint-17500/audit_summary.json) | 18 NORM_REVIEW, 49 MODEL_OR_ASR_REVIEW, 34 AUTO_OK_UNVERIFIED |
| Review thủ công | [manual-review](../reports/manual-review/) | Hai bảng Excel gốc chuyển thành CSV; candidate không đồng nghĩa lỗi đã nghe xác nhận |

Không dùng kết quả này để khẳng định tốt hơn model gốc khi chưa có paired baseline trên cùng text, reference và điều kiện chạy. Không có thông tin GPU đánh giá đầy đủ trong summary, nên RTF chỉ phản ánh lần chạy đã ghi nhận.

## Reference và checkpoint riêng

Audio reference và full checkpoint không đưa vào Git. Dùng transcript chính xác của reference để tạo voice prompt. Hash reference trong kết quả gốc là `1887504551ca86cd18dee44acfcc45ed8333aaddab2813169a76ae3a5274f604`; dùng file khác sẽ là một điều kiện đánh giá mới.

Đặt `FULL_MODEL`, `REF_AUDIO`, `REF_TEXT_FILE` và `EVAL_RESULT_ROOT` trong cấu hình. Dùng result root mới khi đổi checkpoint/reference/text; giữ nguyên root chỉ khi tiếp tục cùng một đánh giá bị ngắt. Evaluator kiểm tra cấu hình generation trước khi tái sử dụng WAV đã có.

`score-all` phải chạy sau khi đủ 101 chunk. Các metric có thể tải thêm weights NISQA/DNSMOS/WavLM/Whisper ở lần đầu. Chạy `whisper-score` riêng nếu mới cần ASR; chạy `report` sau khi đã có kết quả ASR để tổng hợp mà không bắt buộc tính lại quality metrics.

Khi nghe review: normalized text sai → lỗi normalization; text đúng nhưng WAV sai → lỗi model; WAV đúng nhưng Whisper khác → lỗi ASR. Cờ tự động chỉ là danh sách cần kiểm tra.
