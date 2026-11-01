# Vietnamese TTS Adaptation & Evaluation

**Full-Parameter Fine-Tuning of G-OmniVoice for Vietnamese Speech Synthesis**

A Vietnamese text-to-speech project covering training data validation, resumable audio tokenization, full-parameter model adaptation, text normalization, and speech evaluation. The selected experiment ends at **checkpoint 17,500** and is evaluated on **17 documents split into 101 speech segments**.

The pretrained initialization is [G-OmniVoice](https://huggingface.co/g-group-ai-lab/g-omnivoice), and the model architecture and training engine come from [k2-fsa/OmniVoice](https://github.com/k2-fsa/OmniVoice). This repository contains the adaptation workflow, normalization snapshot, benchmark inputs, and recorded evaluation results.

## Project focus

Vietnamese speech synthesis needs more than a training loop: numbers, dates, units, abbreviations, and foreign names affect what the model is asked to pronounce. This project connects model adaptation with a traceable text frontend and an evaluation workflow that distinguishes normalization issues from potential synthesis or ASR errors.

The workflow includes:

- **Training manifests:** validate every CSV row, preserve duplicate source IDs through unique row-based IDs, and reject incomplete manifests.
- **Resumable tokenization:** split data into parts, verify token shards and row counts, and invalidate caches when the manifest or audio tokenizer changes.
- **Full-parameter fine-tuning:** initialize from G-OmniVoice, train with BF16 and FlexAttention, and manage checkpoints and resume state.
- **Vietnamese text normalization:** use a versioned normalizer with span traces before benchmark synthesis.
- **Speech evaluation:** compute Whisper WER/CER, NISQA, DNSMOS, WavLM speaker similarity, signal metrics, and generation speed.
- **Review outputs:** export per-segment metrics, document summaries, manual review tables, and an HTML audio review page.

## What “full-parameter” means here

The recovered training configuration sets `use_lora=false` and initializes from a pretrained G-OmniVoice checkpoint. The upstream builder loads the TTS model in training mode; the optimizer updates its trainable parameters without attaching LoRA adapters.

**The pretrained audio codec is used separately to encode/decode audio; it is not retrained in this workflow.** This is continued fine-tuning of a pretrained TTS model. The recovered configuration and archived evaluation metadata support that training mode; the original run's complete frozen configuration and optimizer state are unavailable.

See the [local training configuration](scripts/training/make_train_config.py), [upstream model builder](https://github.com/k2-fsa/OmniVoice/blob/08be0b4ccbac3e13e374e86fbfead4b4cac343e2/omnivoice/training/builder.py), and [upstream optimizer setup](https://github.com/k2-fsa/OmniVoice/blob/08be0b4ccbac3e13e374e86fbfead4b4cac343e2/omnivoice/training/trainer.py).

## Recorded results

| Metric | Checkpoint 17,500 |
| --- | ---: |
| Documents / speech segments | 17 / 101 |
| Mean Whisper WER ↓ | 9.016% |
| Mean Whisper CER ↓ | 6.7603% |
| Predicted NISQA MOS ↑ | 4.666840 |
| DNSMOS OVRL ↑ | 3.433894 |
| WavLM speaker similarity ↑ | 0.951994 |
| Weighted generation RTF ↓ | 0.057426 |

These values come from the [archived experiment results](reports/checkpoint-17500/). WER/CER are means across segments and use Whisper transcripts. NISQA/DNSMOS are model predictions rather than human listening scores. Generation RTF is total generation time divided by total generated audio duration and reflects the recorded run.

The audit flags **18 segments for normalization review** and **49 for model-or-ASR review**. These flags are screening results, not confirmed synthesis errors. No paired pretrained baseline is included, so the table does not establish an improvement over the base model. See [evaluation methodology](docs/evaluation.md).

## Repository layout

```text
.
├── benchmarks/                 # Source documents and expected 101-segment output
├── configs/                    # Machine-specific configuration template
├── docs/                       # Data, training, evaluation, and project notes
├── norm/                       # Vietnamese TTS Normalizer 0.13.3 snapshot
├── reports/                    # Checkpoint-17500 metrics and manual review tables
├── requirements/               # CUDA, training, evaluation, and test dependencies
├── requirements.txt            # Training + evaluation dependency entry point
├── scripts/
│   ├── training/               # CSV manifests, tokenization, model/config utilities
│   ├── evaluation/             # Synthesis, ASR/quality scoring, and reports
│   ├── setup.sh
│   ├── train.sh
│   ├── evaluate.sh
│   ├── prepare_benchmark.py
│   └── check_repo.py
└── tests/                      # CPU pipeline checks
```

## Installation

GPU training and synthesis target **Linux or WSL2, Python 3.12, and an NVIDIA GPU with BF16 support**. The environment uses **PyTorch 2.8.0 with CUDA 12.8**. Install Git, FFmpeg, `taskset`, and `zip` as system tools. Minimum training VRAM was not established from the archived materials; validate your hardware with the smoke test.

```bash
git clone https://github.com/harilama05/g-omnivoice-finetune.git
cd g-omnivoice-finetune
cp configs/project.env.example configs/local.env
# Edit local.env for your dataset, GPU allocation, and reference files.
bash scripts/setup.sh
source .venv/bin/activate
```

The setup script checks out OmniVoice at commit `08be0b4ccbac3e13e374e86fbfead4b4cac343e2`, then installs the upstream runtime, local normalizer, and dependencies in one pip invocation. That commit was recorded in the source preparation notes and checked for API compatibility; it is not a verified record of the exact source revision used by the original training run.

### Dependency files

| File | What it installs |
| --- | --- |
| [requirements.txt](requirements.txt) | Combined GPU training and evaluation dependencies |
| [requirements/torch-cu128.txt](requirements/torch-cu128.txt) | Matching CUDA builds of PyTorch and torchaudio |
| [requirements/training.txt](requirements/training.txt) | Transformers, Accelerate, NumPy, Hub/checkpoint utilities, WebDataset, audio I/O, and logging |
| [requirements/evaluation.txt](requirements/evaluation.txt) | Faster-Whisper, JiWER, TorchMetrics audio metrics, ONNX Runtime, and supporting libraries |
| [requirements/dev.txt](requirements/dev.txt) | Pytest for CPU acceptance tests |

The setup script also installs the OmniVoice source checkout and `./norm` as editable packages. Development requirements are intentionally separate from the GPU runtime. See [dependency details](requirements/README.md).

These specifications are not a complete historical lockfile. Setup saves the resolved packages to `outputs/environment.freeze.txt` for new runs. Model and metric weights are downloaded separately. Access to the G-OmniVoice initialization requires the relevant Hugging Face permissions.

## Training

### 1. Provide the dataset

Place your CSV at `data/combined_train_shuffled.csv`, or set `CSV` in `configs/local.env`.

```csv
dataset,segment_id,audio_path,text
htv,segment_001,audio/segment_001.wav,"Đây là văn bản huấn luyện đã chuẩn bị."
```

The workflow uses all valid rows as training data, preserves the supplied transcript, and applies no additional text normalization or WER filtering. It does not create a development split. Audio paths must resolve to real files; token shard output paths must not contain whitespace. See the [data contract](docs/data.md).

### 2. Run the workflow

```bash
bash scripts/train.sh check
bash scripts/train.sh download-model
bash scripts/train.sh prepare
bash scripts/train.sh smoke
bash scripts/train.sh tokenize
bash scripts/train.sh start
```

| Setting | Default |
| --- | --- |
| Initialization | `g-group-ai-lab/g-omnivoice` |
| Adaptation | Full-parameter, `use_lora=false` |
| Target optimizer steps | 17,500 |
| Learning rate | `1e-5` |
| Batch tokens / gradient accumulation | 8192 / 1 |
| Precision / attention | BF16 / FlexAttention |
| Warmup ratio / seed | 0.01 / 42 |
| Checkpoint interval | 500 steps |

The recovered v2 script originally specified 5,000 steps. This repository sets the default target to 17,500 to match the selected checkpoint. The table describes the reconstructed recipe; the original run's frozen configuration is missing.

Monitor or resume a run:

```bash
bash scripts/train.sh status
tail -f outputs/g_omnivoice_full/launcher.log
bash scripts/train.sh stop
bash scripts/train.sh resume
```

The default final checkpoint directory is `outputs/g_omnivoice_full/run/checkpoint-17500`. Resume uses the configuration frozen when the new run started and requires the corresponding training state. See [training details](docs/training.md).

## Evaluation

Provide a complete checkpoint directory, a reference WAV, and its exact transcript. Default reference paths are `data/reference/ref04.wav` and `data/reference/ref04.txt`; override them in the local configuration as needed.

```bash
bash scripts/evaluate.sh check
bash scripts/evaluate.sh smoke
bash scripts/evaluate.sh start
bash scripts/evaluate.sh status
# Wait for all 101 segments before scoring.
bash scripts/evaluate.sh score-all
bash scripts/evaluate.sh pack
```

New results are written to `outputs/eval_checkpoint_17500/`, including audio, normalization traces, metric tables, and `review.html`. Use a new result directory when changing the checkpoint, reference, or benchmark inputs.

To prepare and normalize the benchmark on CPU without loading a speech model:

```bash
python scripts/prepare_benchmark.py --output-dir outputs/benchmark_cpu
```

## Validation

The CPU pipeline checks run with Python and Git, including on Windows:

```bash
python -m unittest discover -s tests -v
python scripts/check_repo.py
```

Run the normalizer's independent 0.13.3 acceptance suite:

```bash
python -m pip install -r requirements/dev.txt -e ./norm
python -m pytest norm/tests/test_upgrade_0_13_3.py -q
```

The recorded local validation passed **9 pipeline tests and 118 normalizer acceptance tests**. Pipeline tests reproduce all 101 normalized benchmark segments and exercise manifest failure handling and token-cache recovery. GPU token extraction is mocked in cache tests; GPU training and synthesis have not been rerun during repository preparation.

The [CI workflow](.github/workflows/checks.yml) covers CPU tests, shell syntax, CLI help, and repository file checks. Some older normalizer tests depend on upstream fixtures absent from the archive and are outside the selected CI suite.

## Reproducibility and scope

The private training CSV/audio, complete checkpoint, reference WAV, original optimizer state, and full training environment are not bundled. The repository preserves evaluation results and source hashes, but cannot independently reproduce the historical checkpoint bit for bit. See [provenance and limitations](docs/reproducibility.md).

Dataset files, model weights, credentials, virtual environments, and generated outputs are excluded from Git. The source archives used during organization were removed from this working directory after their owner confirmed a separate backup.

## Portfolio summary

**Vietnamese TTS Adaptation & Evaluation — Python, PyTorch, Transformers, Accelerate, CUDA, Whisper**

> Developed a full-parameter G-OmniVoice adaptation workflow through checkpoint 17,500, with validated manifests, resumable audio tokenization, Vietnamese text normalization, and speech evaluation across 101 segments from 17 documents.

See [project positioning and CV wording](docs/project-profile.md) for a suggested repository name, project description, and result wording.

## Acknowledgments

- [G-Group AI Lab / G-OmniVoice](https://huggingface.co/g-group-ai-lab/g-omnivoice) — pretrained initialization.
- [k2-fsa / OmniVoice](https://github.com/k2-fsa/OmniVoice) — architecture, training engine, and inference runtime.
- The normalizer snapshot retains the [soe-vinorm license and provenance](norm/data/NOTICE.md).

See [third-party notices](THIRD_PARTY_NOTICES.md) for component attribution and licensing notes.
