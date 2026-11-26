#!/usr/bin/env python3
"""Thin CLI wrapper for the separately licensed SwarNano runtime."""

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
RUNTIME_MODULE_NAME = "_swarnano_private_runtime"


def load_runtime(runtime_dir):
    runtime_file = runtime_dir / "serve_tts.py"
    frontend_file = runtime_dir / "language_frontend.py"
    missing = [path.name for path in (runtime_file, frontend_file) if not path.is_file()]
    if missing:
        raise SystemExit(
            "The separately licensed runtime is not installed. "
            "Place the authorized runtime files beside this script "
            f"(missing: {', '.join(missing)}), or set --runtime-dir."
        )

    if str(runtime_dir) not in sys.path:
        sys.path.insert(0, str(runtime_dir))
    spec = importlib.util.spec_from_file_location(RUNTIME_MODULE_NAME, runtime_file)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load the runtime module at {runtime_file}.")

    runtime = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = runtime
    try:
        spec.loader.exec_module(runtime)
    except ModuleNotFoundError as error:
        if error.name in {"numpy", "torch"}:
            raise SystemExit(
                f"The runtime requires the missing dependency '{error.name}'. "
                "Install dependencies provided with your licensed runtime."
            ) from error
        raise
    return runtime


def resolve_speaker(value, metadata_path):
    with metadata_path.open("r", encoding="utf-8") as metadata_file:
        metadata = json.load(metadata_file)

    speaker_map = metadata.get("spk_map")
    if not isinstance(speaker_map, dict) or not speaker_map:
        raise ValueError(f"No speaker map found in {metadata_path}.")
    if value in speaker_map:
        return int(speaker_map[value])

    try:
        speaker_index = int(value)
    except ValueError as error:
        raise ValueError(
            "Speaker must be an index from the metadata map or a speaker ID such as 0258."
        ) from error

    valid_indices = {int(index) for index in speaker_map.values()}
    if speaker_index not in valid_indices:
        raise ValueError(
            f"Speaker index {speaker_index} is not present in {metadata_path}."
        )
    return speaker_index


def parse_args():
    parser = argparse.ArgumentParser(
        description="Generate Nepali speech using the separately licensed SwarNano runtime."
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=SCRIPT_DIR,
        help="Directory containing the authorized runtime files (default: script directory).",
    )
    parser.add_argument(
        "--model",
        default="weights/swarnano_v1_fp32.pt",
        help="FP32 .pt or compressed INT8 .xz path relative to --runtime-dir.",
    )
    parser.add_argument("--text", required=True, help="Nepali text to synthesize.")
    parser.add_argument(
        "--speaker",
        default="0",
        help="Speaker index (0-17) or source speaker ID such as 0258 (default: 0).",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Synthesis speed multiplier (default: 1.0).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("swarnano_output.wav"),
        help="Output WAV path (default: ./swarnano_output.wav).",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    runtime_dir = args.runtime_dir.expanduser().resolve()
    model_path = Path(args.model).expanduser()
    if not model_path.is_absolute():
        model_path = runtime_dir / model_path
    model_path = model_path.resolve()

    try:
        relative_model_path = model_path.relative_to(runtime_dir)
    except ValueError:
        raise SystemExit("The model path must be inside --runtime-dir.")
    if model_path.suffix.lower() not in {".pt", ".xz"} or not model_path.is_file():
        raise SystemExit(f"Model file not found or unsupported: {model_path}")
    if not math.isfinite(args.speed) or args.speed <= 0:
        raise SystemExit("--speed must be a finite number greater than zero.")
    if not args.text.strip():
        raise SystemExit("--text must not be empty.")

    metadata_path = model_path.parent / "swarnano_v1_meta.json"
    if not metadata_path.is_file():
        raise SystemExit(f"Model metadata file not found: {metadata_path}")
    try:
        speaker = resolve_speaker(args.speaker, metadata_path)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(str(error)) from error

    runtime = load_runtime(runtime_dir)
    synthesize = getattr(runtime, "synthesize", None)
    if not callable(synthesize):
        raise RuntimeError("The licensed runtime does not provide the required synthesize API.")

    wav_bytes, info = synthesize(
        relative_model_path.as_posix(),
        args.text,
        speaker,
        args.speed,
        language="ne",
    )
    output_path = args.output.expanduser()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(wav_bytes)

    print(
        f"Saved {output_path} "
        f"({info['seconds']:.2f} seconds, {info['sample_rate']} Hz, speaker {speaker})."
    )
    if info.get("unknown_characters", 0):
        print(
            f"Warning: {info['unknown_characters']} unsupported character(s) "
            "were omitted during text preparation.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
