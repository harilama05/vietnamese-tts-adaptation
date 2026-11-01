# Thành phần bên ngoài

- [G-OmniVoice](https://huggingface.co/g-group-ai-lab/g-omnivoice): initialization checkpoint, phát hành bởi G-Group AI Lab. Repo này chứa quy trình fine-tune tiếp của chủ dự án, không phát hành lại model weights.
- [OmniVoice](https://github.com/k2-fsa/OmniVoice): model runtime, audio token extraction và training loop, Apache-2.0. Source được tải riêng vào thư mục bị Git ignore.
- Codec đi kèm model chịu điều kiện Higgs Audio 2 riêng, như nêu trong model card; repo không sao chép weights codec.
- [Vietnamese normalizer](norm/README.md): khôi phục từ snapshot trong thí nghiệm, gồm provenance của ZeroTTS và bảng viết tắt soe-vinorm. Giữ nguyên [NOTICE](norm/data/NOTICE.md) và [MIT license của bảng viết tắt](norm/data/LICENSE.soe-vinorm).
- Whisper/faster-whisper, TorchMetrics NISQA/DNSMOS và WavLM được dùng khi đánh giá; model weights do các công cụ tương ứng tải riêng.

Chưa có giấy phép tổng thể cho mã dự án trong tài liệu ban đầu. Việc chọn giấy phép công bố mã của chủ dự án chưa được tự quyết định trong lần tổ chức này; các giấy phép/thông báo có sẵn của thành phần bên ngoài vẫn được giữ nguyên.
