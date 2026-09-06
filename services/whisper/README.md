# Whisper service

Independent local streaming STT. Assistant Core talks to it only through `STTProvider`.

```text
PCM (s16le, 16 kHz mono)
        ↓
WhisperSession window / hop
        ↓
partial transcript
        ↓
finalize_turn()
        ↓
final transcript
```

## Run

```bash
cd services/whisper
pip install -e .
python -m whisper_service
```

Defaults to a scripted CPU engine so the stack boots without a ggml model. To use whisper.cpp:

```text
WHISPER_BIN=whisper-cli
WHISPER_MODEL_PATH=/models/ggml-base.en.bin
```

## Endpoints

- `GET /health`
- `POST /v1/transcribe` — one-shot PCM body
- `POST /v1/session` then `/audio`, `/finalize`, `/reset`; `DELETE /v1/session/{id}` releases it
- `WS /v1/stream` — binary PCM in; JSON `partial` / `final` out

Control messages: `{"type":"reset"}`, `{"type":"finalize"}`, `{"type":"config","sample_rate":16000}`.
