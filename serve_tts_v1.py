#!/usr/bin/env python3
"""Nepali-only inference runtime for the SwarNano v1 weights."""

import io
import lzma
import math
import re
import threading
import unicodedata
import wave
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from language_frontend import to_devanagari


ROOT = Path(__file__).resolve().parent
SAMPLE_RATE = 22050
HOP = 256
NFFT = 1024
MAX_TEXT_CHARS = 2000
MAX_AUDIO_SECONDS = 300
SENTENCE_END_PAUSE_SECONDS = 0.30

CONS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "ng",
    "च": "ts", "छ": "tsh", "ज": "dz", "झ": "dzh", "ञ": "ny",
    "ट": "T", "ठ": "Th", "ड": "D", "ढ": "Dh", "ण": "N",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "व": "w", "श": "sh",
    "ष": "sh", "स": "s", "ह": "h",
}
IVOW = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ii", "उ": "u",
    "ऊ": "uu", "ऋ": "ri", "ए": "e", "ऐ": "ai", "ओ": "o",
    "औ": "au",
}
MATRA = {
    "ा": "aa", "ि": "i", "ी": "ii", "ु": "u", "ू": "uu",
    "ृ": "ri", "े": "e", "ै": "ai", "ो": "o", "ौ": "au",
}
SIGNS = {"ं": "M", "ँ": "~", "ः": "h"}
DIGIT_WORD = ["शून्य", "एक", "दुई", "तीन", "चार", "पाँच", "छ", "सात", "आठ", "नौ"]
LONG_PAUSE = set("।.?!;:|\n")
SHORT_PAUSE = set(",–—")
VIRAMA = "\u094d"
NUKTA = "\u093c"
SPECIAL = ["<pad>", "sil", "_", "|", ","]
PHONES = sorted(set(list(CONS.values()) + list(IVOW.values()) + list(MATRA.values()) + list(SIGNS.values())))
VOCAB = SPECIAL + [phone for phone in PHONES if phone not in SPECIAL]
TOK2ID = {phone: index for index, phone in enumerate(VOCAB)}


def normalize_text(text):
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\u200d", "").replace("\u200c", "").replace(NUKTA, "").replace("ज्ञ", "ग्य")
    text = text.translate(str.maketrans({"。": "।", "！": "!", "？": "?", "؟": "?", "、": ",", "،": ","}))
    output = []
    for char in text:
        if "०" <= char <= "९":
            output.append(" " + DIGIT_WORD[ord(char) - 0x966] + " ")
        elif "0" <= char <= "9":
            output.append(" " + DIGIT_WORD[ord(char) - 0x30] + " ")
        else:
            output.append(char)
    return re.sub(r"[ \t]+", " ", "".join(output)).strip()


def g2p(text):
    text = normalize_text(text)
    tokens = ["sil"]
    index = 0
    unknown = 0
    while index < len(text):
        char = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if char in CONS:
            tokens.append(CONS[char])
            if following == VIRAMA:
                index += 2
                continue
            if following in MATRA:
                tokens.append(MATRA[following])
                index += 2
                continue
            tokens.append("a")
            index += 1
            continue
        if char in IVOW:
            tokens.append(IVOW[char])
        elif char in SIGNS:
            tokens.append(SIGNS[char])
        elif char == " ":
            tokens.append("_")
        elif char in LONG_PAUSE:
            tokens.append("|")
        elif char in SHORT_PAUSE:
            tokens.append(",")
        elif char not in MATRA and char != VIRAMA and char not in "\"'“”‘’()[]-":
            unknown += 1
        index += 1

    clean = []
    for token in tokens:
        if token in ("_", "|", ","):
            if clean and clean[-1] == "sil":
                continue
            if clean and clean[-1] in ("_", "|", ","):
                if token == "_" or clean[-1] == "|":
                    continue
                clean[-1] = token
                continue
        clean.append(token)
    while clean and clean[-1] in ("_", "|", ",", "sil"):
        clean.pop()
    clean.append("sil")
    return [TOK2ID[token] for token in clean], unknown


@dataclass
class ModelConfig:
    vocab_size: int
    speakers: int
    channels: int
    enc_blocks: int
    dec_blocks: int
    latent_channels: int
    dct_coefficients: int
    env_bands: int
    post_channels: int
    post_blocks: int
    harmonics: int
    decoder_loops: int = 2


def hz2mel(freq):
    return 2595.0 * torch.log10(1.0 + freq / 700.0)


class Block(nn.Module):
    def __init__(self, channels, kernel=7, dilation=1, mult=2):
        super().__init__()
        self.dw = nn.Conv1d(
            channels,
            channels,
            kernel,
            padding=dilation * (kernel - 1) // 2,
            dilation=dilation,
            groups=channels,
        )
        self.ln = nn.LayerNorm(channels)
        self.pw1 = nn.Linear(channels, channels * mult)
        self.pw2 = nn.Linear(channels * mult, channels)
        self.g = nn.Parameter(torch.full((channels,), 0.1))

    def forward(self, x, mask=None):
        y = self.dw(x if mask is None else x * mask)
        y = self.pw2(F.gelu(self.pw1(self.ln(y.transpose(1, 2))))) * self.g
        x = x + y.transpose(1, 2)
        return x if mask is None else x * mask


def length_regulate_indices(dur, frames):
    cumulative = torch.cumsum(dur, 1)
    time = torch.arange(frames, device=dur.device)
    indices = (cumulative[:, None, :] <= time[None, :, None]).sum(-1).clamp(max=dur.shape[1] - 1)
    start = (cumulative - dur).gather(1, indices)
    frame_duration = dur.gather(1, indices).clamp(min=1)
    position = ((time[None] - start).float() + 0.5) / frame_duration.float()
    return indices, position.clamp(0, 1), frame_duration, (time[None] < cumulative[:, -1:])


class Acoustic(nn.Module):
    def __init__(self, config):
        super().__init__()
        channels = config.channels
        self.emb = nn.Embedding(config.vocab_size, channels, padding_idx=0)
        self.spk = nn.Embedding(config.speakers, channels)
        self.enc = nn.ModuleList([
            Block(channels, 5, dilation=[1, 2][index % 2])
            for index in range(config.enc_blocks)
        ])
        self.dur_head = nn.Sequential(
            nn.Conv1d(channels, channels // 2, 3, padding=1),
            nn.GELU(),
            nn.Conv1d(channels // 2, 1, 1),
        )
        self.coef = nn.Conv1d(channels, config.latent_channels * config.dct_coefficients, 1)
        self.frame_in = nn.Conv1d(channels + config.latent_channels + 2, channels, 1)
        self.dec = nn.ModuleList([
            Block(channels, 7, dilation=[1, 2, 4, 8][index % 4])
            for index in range(config.dec_blocks)
        ])
        self.head_pv = nn.Conv1d(channels, 2, 1)
        self.head_env = nn.Conv1d(channels, 2 * config.env_bands, 1)
        self.latent_channels = config.latent_channels
        self.dct_coefficients = config.dct_coefficients
        self.env_bands = config.env_bands
        self.decoder_loops = config.decoder_loops

    def forward(self, phones, speakers, speed):
        phone_mask = (phones > 0).float()[:, None, :]
        conditioning = self.spk(speakers)
        hidden = (self.emb(phones) + conditioning[:, None, :]).transpose(1, 2)
        for block in self.enc:
            hidden = block(hidden, phone_mask)
        log_duration = self.dur_head(hidden)[:, 0]
        duration = (torch.exp(log_duration.detach()) / speed).round().clamp(min=1).long()
        duration = duration * (phones > 0).long()
        frames = int(duration.sum(1).max())
        if frames > MAX_AUDIO_SECONDS * SAMPLE_RATE // HOP:
            raise ValueError(f"Generated audio would exceed {MAX_AUDIO_SECONDS} seconds.")

        indices, position, frame_duration, valid = length_regulate_indices(duration, frames)
        batch, channels, _ = hidden.shape
        frame_hidden = hidden.gather(2, indices[:, None, :].expand(-1, channels, -1))
        coefficients = self.coef(hidden).gather(
            2,
            indices[:, None, :].expand(
                -1, self.latent_channels * self.dct_coefficients, -1
            ),
        ).view(batch, self.latent_channels, self.dct_coefficients, frames)
        basis = torch.cos(
            math.pi
            * torch.arange(self.dct_coefficients, device=phones.device)[None, :, None]
            * position[:, None, :]
        )
        gesture = (coefficients * basis[:, None]).sum(2)
        frame_mask = valid.float()[:, None, :]
        hidden = self.frame_in(torch.cat([
            frame_hidden,
            gesture,
            position[:, None],
            torch.log(frame_duration.float())[:, None] / 3.0,
        ], 1))
        hidden = (hidden + conditioning[:, :, None]) * frame_mask
        for _ in range(self.decoder_loops):
            for block in self.dec:
                hidden = block(hidden, frame_mask)
        pitch_voicing = self.head_pv(hidden)
        envelope = self.head_env(hidden)
        return {
            "lf0": pitch_voicing[:, 0].clamp(math.log(50.0), math.log(600.0)),
            "vlog": pitch_voicing[:, 1],
            "env_h": envelope[:, :self.env_bands],
            "env_n": envelope[:, self.env_bands:],
            "feat": hidden,
            "valid": valid,
        }


class Renderer(nn.Module):
    def __init__(self, env_bands, harmonics):
        super().__init__()
        self.env_bands = env_bands
        self.harmonics = harmonics
        self.mel_max = float(hz2mel(torch.tensor(SAMPLE_RATE / 2.0)))
        frequencies = torch.arange(NFFT // 2 + 1) * SAMPLE_RATE / NFFT
        position = hz2mel(frequencies) / self.mel_max * (env_bands - 1)
        matrix = (1 - (position[:, None] - torch.arange(env_bands)[None]).abs()).clamp(min=0)
        self.register_buffer("M", matrix)
        self.register_buffer("win", torch.hann_window(NFFT))
        self.register_buffer("k", torch.arange(1, harmonics + 1).float())

    def forward(self, f0, voiced, env_h, env_n):
        batch, frames = f0.shape
        samples = frames * HOP
        f0 = f0.float()
        voiced = voiced.float()
        env_h = env_h.float().clamp(-12, 3)
        env_n = env_n.float().clamp(-12, 3)
        f0_up = F.interpolate(f0[:, None], size=samples, mode="linear", align_corners=False)[:, 0]
        phase = torch.cumsum(f0_up.double() / SAMPLE_RATE, 1)
        phase = ((phase - torch.floor(phase)) * 2 * math.pi).float()
        harmonic_freq = f0[:, None, :] * self.k[None, :, None]
        position = (hz2mel(harmonic_freq) / self.mel_max * (self.env_bands - 1)).clamp(
            0, self.env_bands - 1 - 1e-4
        )
        index = position.floor().long()
        weight = position - index
        envelope = (1 - weight) * env_h.gather(1, index) + weight * env_h.gather(
            1, (index + 1).clamp(max=self.env_bands - 1)
        )
        amplitude = torch.exp(envelope) * (harmonic_freq < 0.47 * SAMPLE_RATE).float() * voiced[:, None, :]
        amplitude_up = F.interpolate(amplitude, size=samples, mode="linear", align_corners=False)
        harmonics = (amplitude_up * torch.sin(self.k[None, :, None] * phase[:, None, :])).sum(1)
        spectrum = torch.stft(
            torch.randn(batch, samples, device=f0.device),
            NFFT,
            HOP,
            window=self.win,
            return_complex=True,
        )
        gain = torch.exp(torch.einsum("fe,bet->bft", self.M, env_n))
        gain = F.pad(gain, (0, spectrum.shape[-1] - gain.shape[-1]), mode="replicate")
        noise = torch.istft(spectrum * gain, NFFT, HOP, window=self.win, length=samples)
        return harmonics + noise


class PostNet(nn.Module):
    def __init__(self, config):
        super().__init__()
        bins = NFFT // 2 + 1
        self.inp = nn.Conv1d(bins + config.channels, config.post_channels, 1)
        self.blocks = nn.ModuleList([
            Block(config.post_channels, 7, dilation=[1, 2, 3, 1][index % 4])
            for index in range(config.post_blocks)
        ])
        self.head = nn.Conv1d(config.post_channels, 4 * bins, 1)
        self.register_buffer("win", torch.hann_window(NFFT))
        self.bins = bins

    def forward(self, wav, features):
        samples = wav.shape[-1]
        spectrum = torch.stft(wav, NFFT, HOP, window=self.win, return_complex=True)
        magnitude = torch.sqrt(spectrum.real ** 2 + spectrum.imag ** 2 + 1e-10)
        log_magnitude = torch.log(magnitude + 1e-5)
        features = F.pad(features, (0, spectrum.shape[-1] - features.shape[-1]), mode="replicate")
        hidden = self.inp(torch.cat([log_magnitude, features], 1))
        for block in self.blocks:
            hidden = block(hidden)
        output = self.head(hidden)
        bins = self.bins
        gain = torch.complex(output[:, :bins], output[:, bins:2 * bins])
        add = torch.complex(output[:, 2 * bins:3 * bins], output[:, 3 * bins:])
        scale = (magnitude.mean(1, keepdim=True) + 1e-3).detach()
        return torch.istft(
            spectrum * (1 + gain) + add * scale,
            NFFT,
            HOP,
            window=self.win,
            length=samples,
        )


class Nano(nn.Module):
    def __init__(self, config):
        super().__init__()
        self.ac = Acoustic(config)
        self.rend = Renderer(config.env_bands, config.harmonics)
        self.post = PostNet(config)

    def forward(self, phones, speakers, speed):
        output = self.ac(phones, speakers, speed)
        pitch = torch.exp(output["lf0"].detach())
        voiced = torch.sigmoid(output["vlog"]).detach() * output["valid"].float()
        waveform = self.rend(pitch, voiced, output["env_h"], output["env_n"])
        output["wav_out"] = self.post(waveform, output["feat"])
        return output["wav_out"]


def _block_count(state, prefix):
    pattern = re.compile(re.escape(prefix) + r"(\d+)\.")
    return max(
        (
            int(match.group(1))
            for key in state
            for match in [pattern.match(key)]
            if match
        ),
        default=-1,
    ) + 1


def _normalize_state_keys(state):
    normalized = {}
    quantized = False
    for key, value in state.items():
        if ".parametrizations.weight.original" in key:
            key = key.replace(".parametrizations.weight.original", ".weight")
            quantized = True
        if ".parametrizations.weight." in key:
            continue
        normalized[key] = value
    return normalized, quantized


def _remap_legacy_duration_head(state, model_state):
    legacy_keys = ("ac.dur_head.3.weight", "ac.dur_head.3.bias")
    current_keys = ("ac.dur_head.2.weight", "ac.dur_head.2.bias")
    if not all(key in state for key in legacy_keys):
        return state
    if any(key in state for key in current_keys):
        return state
    if not all(
        tuple(state[old_key].shape) == tuple(model_state[new_key].shape)
        for old_key, new_key in zip(legacy_keys, current_keys)
    ):
        return state

    remapped = dict(state)
    for old_key, new_key in zip(legacy_keys, current_keys):
        remapped[new_key] = remapped.pop(old_key)
    return remapped


def _make_model(state, signature=None):
    state, has_qat_weights = _normalize_state_keys(state)
    if "ac.lang.weight" in state:
        raise ValueError("This runner supports Nepali-only SwarNano v1 weights.")

    embedding = state.get("ac.emb.weight")
    speaker_embedding = state.get("ac.spk.weight")
    frame_in = state.get("ac.frame_in.weight")
    coefficient = state.get("ac.coef.weight")
    head_env = state.get("ac.head_env.weight")
    post_in = state.get("post.inp.weight")
    if any(item is None for item in (embedding, speaker_embedding, frame_in, coefficient, head_env, post_in)):
        raise ValueError("This file is not a complete SwarNano v1 model.")
    if speaker_embedding.shape[0] != 18:
        raise ValueError("SwarNano v1 weights must contain 18 female voice embeddings.")

    latent_channels = frame_in.shape[1] - embedding.shape[1] - 2
    if latent_channels <= 0 or coefficient.shape[0] % latent_channels:
        raise ValueError("Unable to infer model dimensions from these weights.")
    render_harmonics = state.get("rend.k")
    signature = signature or {}
    config = ModelConfig(
        vocab_size=embedding.shape[0],
        speakers=speaker_embedding.shape[0],
        channels=embedding.shape[1],
        enc_blocks=_block_count(state, "ac.enc."),
        dec_blocks=_block_count(state, "ac.dec."),
        latent_channels=latent_channels,
        dct_coefficients=coefficient.shape[0] // latent_channels,
        env_bands=head_env.shape[0] // 2,
        post_channels=post_in.shape[0],
        post_blocks=_block_count(state, "post.blocks."),
        harmonics=int(signature.get(
            "N_HARM",
            render_harmonics.shape[0]
            if render_harmonics is not None
            else (40 if embedding.shape[1] <= 48 else 80),
        )),
        decoder_loops=int(signature.get("N_LOOPS", 2)),
    )
    if state.get("rend.M") is not None:
        config.env_bands = state["rend.M"].shape[1]

    model = Nano(config)
    state = _remap_legacy_duration_head(state, model.state_dict())
    missing, unexpected = model.load_state_dict(state, strict=False)
    missing_parameters = [
        key for key in missing
        if key not in {"rend.M", "rend.win", "rend.k", "post.win"}
    ]
    if missing_parameters or unexpected:
        raise ValueError(
            "Weights do not match the SwarNano v1 runtime "
            f"(missing: {', '.join(missing_parameters[:4]) or 'none'}; "
            f"unexpected: {', '.join(unexpected[:4]) or 'none'})."
        )

    if has_qat_weights:
        for module in model.modules():
            if isinstance(module, (nn.Conv1d, nn.Linear, nn.Embedding)):
                weight = module.weight.data
                if weight.ndim >= 2:
                    scale = weight.abs().amax(
                        dim=tuple(range(1, weight.ndim)),
                        keepdim=True,
                    ).clamp(min=1e-8) / 127
                    module.weight.data.copy_(
                        (weight / scale).round().clamp(-127, 127) * scale
                    )
    return model.eval(), config


def _load_model(path):
    if path.suffix.lower() == ".xz":
        try:
            with lzma.open(path, "rb") as compressed:
                archive = np.load(io.BytesIO(compressed.read()), allow_pickle=False)
                state = {}
                for key in archive.files:
                    if key.endswith(".f"):
                        state[key[:-2]] = torch.from_numpy(archive[key].astype(np.float32))
                    elif key.endswith(".q"):
                        shape = tuple(archive[key[:-2] + ".shape"].tolist())
                        scale = archive[key[:-2] + ".s"].astype(np.float32)
                        quantized = archive[key]
                        bits_key = key[:-2] + ".bits"
                        bits = int(archive[bits_key].item()) if bits_key in archive.files else 8
                        if bits == 4:
                            high = (quantized >> 4).astype(np.int8) - 8
                            low = (quantized & 15).astype(np.int8) - 8
                            quantized = np.stack([high, low], 1).reshape(-1)[:int(np.prod(shape))]
                        elif bits not in (6, 8):
                            raise ValueError(f"Unsupported quantization width {bits} for {key}.")
                        values = quantized.reshape(shape).astype(np.float32)
                        values *= scale.reshape(-1, *([1] * (len(shape) - 1)))
                        state[key[:-2]] = torch.from_numpy(values)
        except (lzma.LZMAError, ValueError, KeyError) as error:
            raise ValueError(f"Could not read the exported SwarNano archive: {error}") from error
        model, config = _make_model(state)
        return model, config, None

    loaded = torch.load(path, map_location="cpu", weights_only=True)
    step = None
    signature = {}
    if isinstance(loaded, dict) and isinstance(loaded.get("G"), (dict, OrderedDict)):
        step = loaded.get("step")
        signature = loaded.get("sig") if isinstance(loaded.get("sig"), dict) else {}
        state = loaded["G"]
    elif isinstance(loaded, (dict, OrderedDict)):
        state = loaded
    else:
        raise ValueError("Expected a SwarNano v1 state dict or training checkpoint.")
    model, config = _make_model(state, signature)
    return model, config, step


MODEL_CACHE = {}
MODEL_CACHE_LOCK = threading.Lock()


def get_model(relative_path):
    path = (ROOT / relative_path).resolve()
    if ROOT not in path.parents or path.suffix.lower() not in {".pt", ".xz"} or not path.is_file():
        raise ValueError("Choose a supported v1 model file inside this package.")
    stat = path.stat()
    key = str(path)
    fingerprint = (stat.st_mtime_ns, stat.st_size)
    with MODEL_CACHE_LOCK:
        cached = MODEL_CACHE.get(key)
        if cached and cached[0] == fingerprint:
            return cached[1], cached[2], cached[3]
        if cached:
            del MODEL_CACHE[key]
        model, config, step = _load_model(path)
        MODEL_CACHE[key] = (fingerprint, model, config, step)
        return model, config, step


def _sentence_segments(text):
    segments = []
    start = 0
    boundary = re.compile(r"[.!?।…！？。؟]+[\"'”’)\]]*(?=\s|$)|\n+")
    for match in boundary.finditer(text):
        terminal_mark = not match.group().startswith("\n")
        end = match.end() if terminal_mark else match.start()
        segment = text[start:end].strip()
        if segment:
            segments.append((segment, True))
        start = match.end()
    remainder = text[start:].strip()
    if remainder:
        segments.append((remainder, False))
    return segments


def synthesize(relative_path, text, speaker, speed=1.0, language="ne"):
    if language != "ne":
        raise ValueError("SwarNano v1 supports Nepali text only.")
    if not text.strip():
        raise ValueError("Enter text to synthesize.")
    if len(text) > MAX_TEXT_CHARS:
        raise ValueError(f"Text must be no longer than {MAX_TEXT_CHARS} characters.")
    if not math.isfinite(speed) or speed <= 0:
        raise ValueError("Speed must be a finite number greater than zero.")

    model, config, step = get_model(relative_path)
    prepared_text = to_devanagari(text, "ne")
    phones, unknown = g2p(prepared_text)
    if len(phones) < 2:
        raise ValueError("The text did not produce any supported pronunciation.")
    if speaker < 0 or speaker >= config.speakers:
        raise ValueError(f"Choose a speaker from 0 to {config.speakers - 1}.")

    with torch.inference_mode():
        speaker_tensor = torch.tensor([speaker], dtype=torch.long)
        pieces = []
        for sentence, ends_sentence in _sentence_segments(text):
            sentence_phones, _ = g2p(to_devanagari(sentence, "ne"))
            if len(sentence_phones) >= 2:
                phone_tensor = torch.tensor([sentence_phones], dtype=torch.long)
                audio_piece = model(phone_tensor, speaker_tensor, speed)[0].clamp(-1, 1).cpu().numpy()
                pieces.append(audio_piece)
            if ends_sentence:
                pieces.append(np.zeros(round(SENTENCE_END_PAUSE_SECONDS * SAMPLE_RATE), dtype=np.float32))
        audio = np.concatenate(pieces) if pieces else np.zeros(0, dtype=np.float32)

    if len(audio) > MAX_AUDIO_SECONDS * SAMPLE_RATE:
        raise ValueError(f"Generated audio would exceed {MAX_AUDIO_SECONDS} seconds.")
    if not np.isfinite(audio).all():
        raise RuntimeError("The model produced non-finite audio.")
    audio = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(audio.tobytes())
    return buffer.getvalue(), {
        "seconds": len(audio) / SAMPLE_RATE,
        "sample_rate": SAMPLE_RATE,
        "unknown_characters": unknown,
        "step": step,
        "prepared_text": prepared_text,
        "language": "ne",
    }
