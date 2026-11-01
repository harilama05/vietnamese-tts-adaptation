# G-OmniVoice Vietnamese Fine-tuning

Repo tổ chức lại quy trình **full fine-tune `g-group-ai-lab/g-omnivoice` đến checkpoint 17.500**, kèm chuẩn bị manifest, audio tokenization, resume và đánh giá tiếng Việt trên 17 văn bản / 101 chunk.

Đây là dự án fine-tune của người dùng từ checkpoint G-OmniVoice được phát hành sẵn. Mã huấn luyện nền sử dụng [k2-fsa/OmniVoice](https://github.com/k2-fsa/OmniVoice). Phạm vi repo kết thúc tại **`checkpoint-17500`**.

## Kết quả đã lưu

| Chỉ số | Checkpoint 17.500 |
| --- | ---: |
| Văn bản / chunk | 17 / 101 |
| Whisper mean WER ↓ | 9,016% |
| Whisper mean CER ↓ | 6,7603% |
| NISQA MOS dự đoán ↑ | 4,666840 |
| DNSMOS OVRL ↑ | 3,433894 |
| WavLM speaker similarity ↑ | 0,951994 |
| Weighted generation RTF ↓ | 0,057426 |

Số liệu lấy từ [báo cáo gốc](reports/checkpoint-17500/), không phải lần huấn luyện lại khi sắp xếp repo. WER/CER là phép đo qua Whisper; NISQA/DNSMOS là điểm dự đoán, không phải human MOS. Có 18 chunk cần xem lại normalization và 49 chunk cần nghe để tách lỗi TTS khỏi lỗi ASR. Xem [cách đọc kết quả](docs/evaluation.md).

## Cấu trúc

```text
.
├── benchmarks/                 # 17 văn bản + 101 chunk chuẩn để đối chiếu
├── configs/                    # Mẫu cấu hình máy/HPC
├── docs/                       # Dữ liệu, huấn luyện, đánh giá, nguồn gốc
├── norm/                       # Vietnamese TTS Normalizer 0.13.3 từ snapshot
├── reports/                    # Kết quả checkpoint-17500 + review CSV
├── requirements/               # Phụ thuộc đánh giá và kiểm thử
├── scripts/
│   ├── training/               # CSV → JSONL → audio tokens → full fine-tune
│   ├── evaluation/             # Synthesis, Whisper, objective metrics, HTML review
│   ├── setup.sh
│   ├── train.sh
│   ├── evaluate.sh
│   ├── prepare_benchmark.py
│   └── check_repo.py
└── tests/                      # Kiểm tra pipeline chạy trên CPU
```

## Bắt đầu

Huấn luyện và sinh âm thanh dùng **Linux/HPC hoặc WSL2 có NVIDIA CUDA**, Python 3.12, GPU hỗ trợ BF16. Cấu hình dùng PyTorch 2.8.0 / CUDA 12.8. Máy cần Git, `ffmpeg`, `taskset` và `zip`. Chưa xác định được yêu cầu VRAM huấn luyện tối thiểu từ tài liệu lưu trữ; hãy chạy smoke test trên GPU của bạn.

```bash
git clone <URL_REPO_CUA_BAN> g-omnivoice-finetune
cd g-omnivoice-finetune
cp configs/project.env.example configs/local.env
# Sửa configs/local.env: CSV, GPU, reference audio/text, đường dẫn nếu cần.
bash scripts/setup.sh
source .venv/bin/activate
```

Setup tải upstream tại commit `08be0b4ccbac3e13e374e86fbfead4b4cac343e2`, là commit được ghi trong tài liệu tiền xử lý gốc và đã đối chiếu API với mã phục hồi. Đây chưa phải bằng chứng về commit thực sự của run 17.500. Các dependency bậc hai chưa được khóa hoàn toàn; setup lưu `pip freeze` vào thư mục output cho lần chạy mới.

[Model G-OmniVoice](https://huggingface.co/g-group-ai-lab/g-omnivoice) có điều kiện truy cập trên Hugging Face. Đăng nhập bằng tài khoản đã được cấp quyền trước khi tải. Giữ token trong môi trường hoặc kho đăng nhập Hugging Face.

### 1. Dữ liệu

Đặt CSV huấn luyện tại `data/combined_train_shuffled.csv` hoặc khai báo `CSV` trong cấu hình. CSV cần các cột:

```csv
dataset,segment_id,audio_path,text
htv,segment_001,audio/segment_001.wav,"Đây là văn bản huấn luyện đã chuẩn bị."
```

Đường dẫn audio tương đối được tìm theo CSV và các vị trí fallback đã ghi trong manifest report. Mọi dòng hợp lệ đều vào train, không chia dev, không lọc WER, không normalize thêm. Dòng lỗi khiến bước prepare thất bại. Xem [hợp đồng dữ liệu](docs/data.md).

### 2. Full fine-tune

```bash
bash scripts/train.sh check
bash scripts/train.sh download-model
bash scripts/train.sh prepare
bash scripts/train.sh smoke
bash scripts/train.sh tokenize
bash scripts/train.sh start
```

Mặc định: full fine-tune, `use_lora=false`, 17.500 bước, LR `1e-5`, `batch_tokens=8192`, gradient accumulation 1, BF16, FlexAttention, seed 42. Mã cấu hình v2 gốc còn lưu đặt 5.000 bước; repo đã đổi đích mặc định thành 17.500 theo checkpoint bạn chốt. **Frozen config và optimizer state của run gốc chưa có**, nên đây là recipe phục hồi để chạy tiếp dự án, không phải cam kết tái tạo bit-for-bit checkpoint đã lưu.

```bash
bash scripts/train.sh status
tail -f outputs/g_omnivoice_full/launcher.log
bash scripts/train.sh stop
bash scripts/train.sh resume
```

Checkpoint đích: `outputs/g_omnivoice_full/run/checkpoint-17500`. Các lần resume dùng lại cấu hình đã đóng băng khi `start`. Xem [hướng dẫn huấn luyện](docs/training.md).

### 3. Đánh giá checkpoint 17.500

Cần **thư mục checkpoint đầy đủ**, reference WAV và transcript chính xác của nó. Mặc định reference đặt ở `data/reference/ref04.wav` và `data/reference/ref04.txt`; có thể cấu hình đường dẫn riêng.

```bash
bash scripts/evaluate.sh check
bash scripts/evaluate.sh smoke
bash scripts/evaluate.sh start
bash scripts/evaluate.sh status
# Đợi đủ 101/101 chunk rồi chấm điểm:
bash scripts/evaluate.sh score-all
bash scripts/evaluate.sh pack
```

Kết quả mới nằm trong `outputs/eval_checkpoint_17500/`, gồm WAV theo chunk/văn bản, WER/CER, NISQA/DNSMOS, speaker similarity, normalization trace và trang nghe `review.html`.

Chuẩn bị benchmark trên CPU, không tải model:

```bash
python scripts/prepare_benchmark.py --output-dir outputs/benchmark_cpu
```

## Kiểm tra repo

Các lệnh sau chỉ cần Python và Git, chạy được trên Windows:

```bash
python -m unittest discover -s tests -v
python scripts/check_repo.py
```

Kiểm tra acceptance của normalizer 0.13.3:

```bash
python -m pip install -r requirements/dev.txt -e ./norm
python -m pytest norm/tests/test_upgrade_0_13_3.py -q
```

CI kiểm tra CPU, so khớp 101 chunk với snapshot, cú pháp Bash, credential phổ biến và kích thước file. CI không chạy GPU training. Xem [kiểm chứng và giới hạn](docs/reproducibility.md).

## Đưa lên GitHub

Repo hiện giữ mã nguồn, tài liệu, benchmark và bảng kết quả của nhánh G-OmniVoice checkpoint 17.500. Các thư mục lưu trữ Month1/Month2/Month3 và vùng làm việc tạm đã được dọn sau khi chủ dự án xác nhận có bản sao riêng. Dataset, checkpoint, WAV, cookie, môi trường Python và output mới được bỏ qua bởi Git. Kiểm tra trước khi commit:

```bash
python scripts/check_repo.py
git add .
git diff --cached --stat
git commit -m "Organize G-OmniVoice full fine-tuning through checkpoint 17500"
git remote add origin <URL_REPO_CUA_BAN>
git push -u origin main
```

Chỉ đẩy mã nguồn, benchmark và bảng kết quả nhỏ. Model weights nên phát hành riêng nếu bạn có quyền và có đủ metadata. Xem [nguồn gốc và phần thiếu](docs/reproducibility.md) cùng [ghi nhận thành phần bên ngoài](THIRD_PARTY_NOTICES.md).
