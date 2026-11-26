#!/usr/bin/env python3
"""Loopback-only web UI for the SwarNano v1 weights."""

import argparse
import html
import json
import math
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from run_swarnano import load_runtime


SCRIPT_DIR = Path(__file__).resolve().parent
MODEL_FILES = {
    "fp32": Path("weights") / "swarnano_v1_fp32.pt",
    "int8": Path("weights") / "swarnano_v1_int8.xz",
}
MAX_TEXT_CHARS = 2000
MAX_REQUEST_BYTES = 32768

PAGE_TEMPLATE = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SwarNano v1</title>
  <style>
    :root { color-scheme: light dark; font-family: system-ui, sans-serif; }
    body { max-width: 720px; margin: 3rem auto; padding: 0 1rem; }
    h1 { margin-bottom: .3rem; }
    p, label { line-height: 1.5; }
    form { display: grid; gap: 1rem; margin-top: 2rem; }
    textarea, select, input, button { font: inherit; padding: .65rem; }
    textarea { min-height: 8rem; }
    .row { display: grid; grid-template-columns: repeat(auto-fit, minmax(12rem, 1fr)); gap: 1rem; }
    .field { display: grid; gap: .4rem; }
    button { cursor: pointer; }
    audio { width: 100%; margin-top: 1rem; }
    #status { min-height: 1.5rem; }
  </style>
</head>
<body>
  <h1>SwarNano v1</h1>
  <p>Nepali-only text-to-speech with 18 female voice options. Processing runs locally.</p>
  <form id="form">
    <label class="field">Nepali text
      <textarea name="text" maxlength="2000" required placeholder="यहाँ नेपाली पाठ लेख्नुहोस्"></textarea>
    </label>
    <div class="row">
      <label class="field">Weights
        <select name="model">
          <option value="fp32">FP32</option>
          <option value="int8">INT8 (compressed)</option>
        </select>
      </label>
      <label class="field">Female voice
        <select name="speaker">
          {{SPEAKER_OPTIONS}}
        </select>
      </label>
      <label class="field">Speed (0.5–2.0)
        <input name="speed" type="number" min="0.5" max="2" step="0.05" value="1.0">
      </label>
    </div>
    <button id="submit" type="submit">Generate speech</button>
  </form>
  <p id="status" role="status"></p>
  <audio id="audio" controls hidden></audio>
  <p><a id="download" hidden download="swarnano_v1.wav">Download WAV</a></p>
  <script>
    const form = document.getElementById("form");
    const status = document.getElementById("status");
    const audio = document.getElementById("audio");
    const download = document.getElementById("download");
    const submit = document.getElementById("submit");
    let audioUrl = null;
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      status.textContent = "Generating…";
      submit.disabled = true;
      try {
        const response = await fetch("/synthesize", {
          method: "POST",
          headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
          body: new URLSearchParams(new FormData(form))
        });
        if (!response.ok) {
          const result = await response.json();
          throw new Error(result.error || "Speech generation failed.");
        }
        const blob = await response.blob();
        if (audioUrl) URL.revokeObjectURL(audioUrl);
        audioUrl = URL.createObjectURL(blob);
        audio.src = audioUrl;
        audio.hidden = false;
        download.href = audioUrl;
        download.hidden = false;
        status.textContent = "Speech ready.";
      } catch (error) {
        status.textContent = error.message;
      } finally {
        submit.disabled = false;
      }
    });
  </script>
</body>
</html>
"""


def _read_speakers(metadata_path):
    with metadata_path.open("r", encoding="utf-8") as metadata_file:
        metadata = json.load(metadata_file)
    speaker_map = metadata.get("spk_map")
    if not isinstance(speaker_map, dict) or not speaker_map:
        raise ValueError(f"No speaker map found in {metadata_path}.")
    return sorted(
        ((int(index), str(source_id)) for source_id, index in speaker_map.items()),
        key=lambda speaker: speaker[0],
    )


def _make_handler(runtime, model_paths, speakers, runtime_dir):
    speaker_options = "\n".join(
        f'<option value="{index}">Female voice {index} (ID {html.escape(source_id)})</option>'
        for index, source_id in speakers
    )
    page = PAGE_TEMPLATE.replace("{{SPEAKER_OPTIONS}}", speaker_options).encode("utf-8")
    valid_speakers = {index for index, _ in speakers}

    class SwarNanoV1Handler(BaseHTTPRequestHandler):
        def _send(self, status, content_type, body):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(body)

        def _send_json(self, status, message):
            body = json.dumps({"error": message}, ensure_ascii=False).encode("utf-8")
            self._send(status, "application/json; charset=utf-8", body)

        def do_GET(self):
            if urlsplit(self.path).path != "/":
                self._send_json(404, "Not found.")
                return
            self._send(200, "text/html; charset=utf-8", page)

        def do_POST(self):
            if urlsplit(self.path).path != "/synthesize":
                self._send_json(404, "Not found.")
                return
            if self.headers.get("Content-Type", "").split(";", 1)[0].lower() != (
                "application/x-www-form-urlencoded"
            ):
                self._send_json(415, "Use a form-encoded request.")
                return
            try:
                content_length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                self._send_json(400, "A valid Content-Length header is required.")
                return
            if content_length < 0 or content_length > MAX_REQUEST_BYTES:
                self._send_json(413, "Request is too large.")
                return
            try:
                fields = parse_qs(
                    self.rfile.read(content_length).decode("utf-8"),
                    keep_blank_values=True,
                )
            except UnicodeDecodeError:
                self._send_json(400, "Request text must be UTF-8.")
                return

            def one_field(name):
                values = fields.get(name, [])
                if len(values) != 1:
                    raise ValueError(f"Provide exactly one {name} value.")
                return values[0]

            try:
                text = one_field("text")
                if not text.strip():
                    raise ValueError("Enter Nepali text.")
                if len(text) > MAX_TEXT_CHARS:
                    raise ValueError(f"Text must be no longer than {MAX_TEXT_CHARS} characters.")

                model_key = one_field("model")
                if model_key not in model_paths:
                    raise ValueError("Choose one of the available v1 weight files.")

                speaker = int(one_field("speaker"))
                if speaker not in valid_speakers:
                    raise ValueError("Choose a speaker listed in the speaker menu.")

                speed = float(one_field("speed"))
                if not math.isfinite(speed) or not 0.5 <= speed <= 2.0:
                    raise ValueError("Speed must be between 0.5 and 2.0.")

                relative_model_path = model_paths[model_key].relative_to(runtime_dir).as_posix()
                wav_bytes, _info = runtime.synthesize(
                    relative_model_path,
                    text,
                    speaker,
                    speed,
                    language="ne",
                )
            except (ValueError, KeyError) as error:
                self._send_json(400, str(error))
                return
            except RuntimeError as error:
                self._send_json(500, str(error))
                return

            self._send(200, "audio/wav", wav_bytes)

        def log_message(self, fmt, *args):
            print("%s - %s" % (self.address_string(), fmt % args))

    return SwarNanoV1Handler


def create_server(runtime_dir, model_dir, port):
    runtime_dir = runtime_dir.expanduser().resolve()
    model_dir = model_dir.expanduser()
    if not model_dir.is_absolute():
        model_dir = runtime_dir / model_dir
    model_dir = model_dir.resolve()
    try:
        model_dir.relative_to(runtime_dir)
    except ValueError:
        raise ValueError("Model directory must be inside --runtime-dir.")

    model_paths = {
        key: (model_dir / relative_path).resolve()
        for key, relative_path in MODEL_FILES.items()
    }
    for model_path in model_paths.values():
        if not model_path.is_file():
            raise FileNotFoundError(f"Required v1 weight file not found: {model_path}")
    metadata_path = model_dir / "weights" / "swarnano_v1_meta.json"
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Required v1 metadata file not found: {metadata_path}")

    speakers = _read_speakers(metadata_path)
    runtime = load_runtime(runtime_dir)
    handler = _make_handler(runtime, model_paths, speakers, runtime_dir)
    return HTTPServer(("127.0.0.1", port), handler)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the local SwarNano v1 browser UI."
    )
    parser.add_argument(
        "--runtime-dir",
        type=Path,
        default=SCRIPT_DIR,
        help="Directory containing serve_tts_v1.py and language_frontend.py (default: script directory).",
    )
    parser.add_argument(
        "--model-dir",
        type=Path,
        default=Path("."),
        help="Directory containing the v1 weights and metadata, relative to --runtime-dir.",
    )
    parser.add_argument("--port", type=int, default=8000, help="Local web server port.")
    return parser.parse_args()


def main():
    args = parse_args()
    if not 1024 <= args.port <= 65535:
        raise SystemExit("--port must be between 1024 and 65535.")
    server = create_server(args.runtime_dir, args.model_dir, args.port)
    print(f"SwarNano v1 is ready at http://127.0.0.1:{args.port}")
    print("Press Ctrl+C to stop the server.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping SwarNano v1.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
