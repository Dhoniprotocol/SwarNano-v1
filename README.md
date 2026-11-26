---
license: cc-by-sa-4.0
language:
  - ne
pipeline_tag: text-to-speech
tags:
  - nepali
  - text-to-speech
  - tts
---

# SwarNano v1

<p align="center">
  <img src="./assets/swarnano-logo.jpg" alt="SwarNano logo" width="600">
</p>

SwarNano v1 is a Nepali text-to-speech model. This repository publishes the
FP32 and INT8 model weights, minimal vocabulary/speaker metadata, and the
notices needed for attribution. The source code, model implementation, and
architecture are maintained separately by the project creator; they are not
included or licensed by this weights-only release.

## Audio samples

### Sample 1

एकादेशमा हरियाली डाँडाले घेरिएको एउटा सुन्दर गाउँ थियो। त्यो गाउँको छेउमा एउटा घना जङ्गल थियो।

<audio controls preload="none" src="https://huggingface.co/dhoni420/SwarNano-v1/resolve/main/samples/demo_01.wav">
  Your browser does not support the audio player.
</audio>

### Sample 2

सबै जनावरहरूले राजाको कुरा ध्यान दिएर सुने। तर, चङ्खे भने एउटा पुतलीलाई लखेट्नमै व्यस्त थियो।

<audio controls preload="none" src="https://huggingface.co/dhoni420/SwarNano-v1/resolve/main/samples/demo_02.wav">
  Your browser does not support the audio player.
</audio>

The WAV files are example speech outputs; the text above is the transcript for
each sample.

## Model details

- **Task:** Nepali text-to-speech.
- **Language:** Nepali.
- **Voice choices:** 18 speaker IDs are available through a compatible
  implementation. They are model voice options, not verified identities.
- **Audio output:** The included examples are mono WAV at 22,050 Hz.
- **Weights:** [`weights/swarnano_v1_fp32.pt`](./weights/swarnano_v1_fp32.pt)
  and [`weights/swarnano_v1_int8.xz`](./weights/swarnano_v1_int8.xz).
- **Metadata:** [`weights/swarnano_v1_meta.json`](./weights/swarnano_v1_meta.json)
  contains the phone vocabulary and speaker-ID map.

## Capabilities at a glance

When paired with a compatible Nepali speech application, SwarNano v1 turns
Nepali text into spoken audio and lets the application select among the
available speaker IDs. Two weight formats are provided:

- **FP32:** about 6.2 MiB.
- **INT8 compressed:** about 1.4 MiB for a smaller download and storage
  footprint.

These are file sizes, not speed or quality benchmarks. No comparative
performance claims are made for the two formats.

The weight files require a compatible model implementation to run. This
repository is weights-only and does not provide that implementation.

## Intended use and limitations

Use for Nepali speech synthesis, research, and evaluation, subject to the
license and applicable third-party rights. Do not present generated speech as
a real recording or use it to impersonate a person.

Speech quality, pronunciation, and prosody may vary. The source corpus contains
female-speaker Nepali recordings; the 18 speaker embeddings are not a balanced
set and should not be treated as verified identities. The dataset license
alone may not grant publicity, privacy, or other personality rights.

## Data and attribution

The model weights were created using OpenSLR SLR43, which OpenSLR lists under
CC BY-SA 4.0 and credits to Google LLC. No source dataset audio or transcripts
are included. Keep [`DATASET_ATTRIBUTION.md`](./DATASET_ATTRIBUTION.md) with
redistributed copies and adaptations.

## License

The model weights and accompanying metadata are offered under
[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/), to the extent
the release publisher holds the necessary rights. This license permits
commercial use and requires attribution and ShareAlike for adaptations where
applicable. It applies only to the released weights and metadata, not to the
creator's separately maintained source code, implementation, or architecture.
See
[`LICENSE`](https://huggingface.co/dhoni420/SwarNano-v1/resolve/main/LICENSE)
and
[`LICENSING.md`](https://huggingface.co/dhoni420/SwarNano-v1/resolve/main/LICENSING.md).

## Repository files

- `weights/` — FP32 and INT8 model weights plus minimal metadata.
- `samples/` — two example speech WAVs with their transcripts above.
- `assets/` — SwarNano logo used on this card.
- `DATASET_ATTRIBUTION.md`, `LICENSE`, `LICENSING.md` — license and attribution
  notices.
- `SHA256SUMS.txt` — checksums for both weight files.

**Created by:** Sandesh Bastola  
**Project:** SwarNano  
**Version:** v1.0
