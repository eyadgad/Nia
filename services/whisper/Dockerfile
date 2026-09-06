FROM python:3.12-slim

# libgomp1 is required by ctranslate2 (faster-whisper backend).
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /service
COPY pyproject.toml ./
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

ENV WHISPER_HOST=0.0.0.0
ENV WHISPER_PORT=8090
ARG WHISPER_MODEL=small.en
ENV WHISPER_MODEL=${WHISPER_MODEL}
ENV WHISPER_ENGINE=faster

# Pre-download the model so the container transcribes offline with no cold-start.
RUN python -c "import os; from faster_whisper import WhisperModel; WhisperModel(os.environ['WHISPER_MODEL'], device='cpu', compute_type='int8')"

EXPOSE 8090
CMD ["python", "-m", "whisper_service"]
