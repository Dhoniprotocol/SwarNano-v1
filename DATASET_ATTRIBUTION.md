# Dataset attribution

## SwarNano project credit

SwarNano v1.0 was created by **Sandesh Bastola** as part of the **SwarNano**
project. This is the model creator credit; it is separate from the source
dataset credit below.

Suggested project attribution:

> SwarNano v1.0, created by Sandesh Bastola.

## OpenSLR SLR43 dataset credit

Source dataset: **OpenSLR SLR43, High quality TTS data for Nepali**. OpenSLR
lists the dataset under CC BY-SA 4.0 and credits Copyright 2016, 2017, 2018
Google LLC. The dataset was collected by Google in Nepal.

- Dataset: <https://openslr.org/43/>
- License: <https://creativecommons.org/licenses/by-sa/4.0/>
- Dataset license file: <https://openslr.trmal.net/resources/43/LICENSE>

## Model context

SwarNano v1 is a Nepali speech model. With a compatible implementation, it can
produce mono speech audio at 22,050 Hz and offers 18 speaker IDs. The release
provides FP32 weights (about 6.2 MiB) and compressed INT8 weights (about
1.4 MiB). These descriptions concern the released files and sample format;
they are not claims about speed or comparative audio quality. The speaker IDs
are model options, not verified identities.

Suggested dataset attribution:

> Nepali TTS data from OpenSLR SLR43, collected by Google in Nepal,
> Copyright 2016, 2017, 2018 Google LLC, licensed under CC BY-SA 4.0.
> SwarNano v1 weights were created using this data; the audio was transformed
> into model weights. Dataset: <https://openslr.org/43/>. License:
> <https://creativecommons.org/licenses/by-sa/4.0/>.

No source audio or transcripts are included. Keep the dataset attribution
with redistributed copies and adaptations.

The associated paper is by Keshan Sodimana, Knot Pipatsrisawat, Linne Ha,
Martin Jansche, Oddur Kjartansson, Pasindu De Silva, and Supheakmungkol Sarin:
"A Step-by-Step Process for Building TTS Voices Using Open Source Data and
Framework for Bangla, Javanese, Khmer, Nepali, Sinhala, and Sundanese,"
SLTU 2018, pp. 66-70:
<https://doi.org/10.21437/SLTU.2018-14>.
