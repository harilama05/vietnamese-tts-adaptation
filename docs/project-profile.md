# Project positioning

## Recommended name

**Vietnamese TTS Adaptation & Evaluation**

Suggested repository slug: **`vietnamese-tts-adaptation`**.

This title describes the engineering problem and makes the project understandable without prior knowledge of G-OmniVoice. Use **“Full-Parameter Fine-Tuning of G-OmniVoice”** as the technical subtitle.

Other suitable slugs are `vietnamese-tts-finetuning` for a training-centered portfolio and `g-omnivoice-adaptation` when model discoverability matters most. The existing GitHub remote and package name are unchanged until a repository name is chosen.

## GitHub description

> Vietnamese TTS adaptation with full-parameter G-OmniVoice fine-tuning, text normalization, resumable audio tokenization, and speech quality evaluation.

## CV entry

**Vietnamese TTS Adaptation & Evaluation**  
Python · PyTorch · Hugging Face Transformers · Accelerate · CUDA · Whisper

- Developed a full-parameter G-OmniVoice fine-tuning workflow through checkpoint 17,500, with validated training manifests, resumable audio tokenization, and checkpoint management.
- Integrated Vietnamese text normalization and evaluated 101 speech segments from 17 documents using Whisper WER/CER, NISQA, DNSMOS, and WavLM speaker similarity; recorded 9.02% mean WER and 6.76% mean CER on the project benchmark.

For an interview, explain how invalid data is rejected, token caches are verified, and normalization errors are separated from TTS and ASR errors. These are concrete engineering decisions supported by the repository.

## Scope of the claims

The base architecture and pretrained initialization come from OmniVoice and G-OmniVoice. The project concerns adaptation, integration, training orchestration and evaluation. The neural audio codec is used as a pretrained component and is not retrained by this workflow.

The reported WER/CER are chunk means from a small project benchmark. No paired baseline is included, so an improvement percentage, state-of-the-art claim, or general production-quality claim is not supported. Original training configs and private data are incomplete; see [reproducibility notes](reproducibility.md).
