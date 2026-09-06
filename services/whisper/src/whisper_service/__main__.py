from __future__ import annotations

import os

import uvicorn


def main() -> None:
    host = os.environ.get("WHISPER_HOST", "0.0.0.0")
    port = int(os.environ.get("WHISPER_PORT", "8090"))
    uvicorn.run("whisper_service.server:app", host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
