# Run SwarNano v1 locally

This guide is for the Windows CPU setup tested with Python 3.14.6,
PyTorch 2.13.0 CPU, and NumPy 2.5.1. The repository includes the v1 inference
source, weights, and runners under CC BY-SA 4.0. It does not include the
training pipeline or training dataset.

## Create the Python environment

Open PowerShell in the downloaded repository folder and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\requirements-v1.txt
```

The requirements use CPU-only PyTorch; CUDA is not required. If PowerShell
blocks environment activation, run the server with the environment's Python
directly instead:

```powershell
.\.venv\Scripts\python.exe .\server_tts_v1.py
```

## Start the browser server

Run the browser server:

```powershell
python .\server_tts_v1.py
```

Open `http://127.0.0.1:8000` in your browser. Select FP32 or INT8, choose one
of the 18 female voice options, enter Nepali text, and press **Generate speech**.
The resulting WAV can be played in the page or downloaded. The server binds to loopback only;
it does not expose an endpoint to the local network or send text/audio to a
cloud service.

If port 8000 is already in use, choose another port:

```powershell
python .\server_tts_v1.py --port 8001
```

Then open `http://127.0.0.1:8001`.

## Troubleshooting

- **Missing runtime files:** confirm `serve_tts_v1.py` and
  `language_frontend.py` are present beside `server_tts_v1.py`.
- **Missing `torch` or `numpy`:** activate `.venv` and repeat the requirements
  install command.
- **Weights not found:** keep the repository's `weights/` directory next to
  `server_tts_v1.py`.
- **Stop the server:** press `Ctrl+C` in the PowerShell window running it.
