# Dependency layout

| File | Purpose |
| --- | --- |
| [../requirements.txt](../requirements.txt) | Entry point for training and evaluation dependencies |
| [torch-cu128.txt](torch-cu128.txt) | Matching PyTorch 2.8.0 and torchaudio CUDA 12.8 wheels |
| [training.txt](training.txt) | Transformers, Accelerate, tokenization, data loading, checkpoint and logging dependencies |
| [evaluation.txt](evaluation.txt) | Additional Whisper, NISQA/DNSMOS, speaker similarity and audio metric dependencies |
| [dev.txt](dev.txt) | Pytest for CPU acceptance tests |

Use `bash scripts/setup.sh` from the repository root for the GPU environment. It creates a virtual environment, checks out the pinned OmniVoice source, and installs the dependency entry point, upstream runtime and local normalizer together. Run it on Linux or WSL2 with a compatible NVIDIA GPU/driver; it does not install the driver or system programs such as FFmpeg.

Installing `requirements.txt` alone installs dependencies. The application also needs the OmniVoice source checkout and local normalizer, which the setup script installs as editable packages. This supports a custom `OMNIVOICE_REPO` path without changing the requirements files.

`dev.txt` is intentionally small: it provides test tools and does not install CUDA, model weights or the GPU training stack. The normalizer and pipeline CPU tests can run separately from that environment.

Direct dependencies are listed explicitly even when upstream would bring them in transitively. Gradio and pydub are declared by the pinned OmniVoice distribution; this repository does not currently provide its own web demo. PEFT/LoRA packages are not required for the full-parameter training path.

These files describe a reconstructed environment, not the original run's complete lockfile. PyTorch/torchaudio and upstream source are pinned; other dependencies may resolve differently over time. Setup records the resolved environment in `outputs/environment.freeze.txt`. A GPU installation and training run have not been repeated as part of repository preparation.
