FROM python:3.11-slim

# opencv-python-headless (vision.py) still links against libGL/libglib even
# in its "headless" build — these are the standard packages needed for it to
# actually import on a Debian-based image. rapidocr-onnxruntime needs none.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data

# Uploaded documents are now written back into data/corpus/ on accept (see
# docs/ARCHITECTURE.md §11, ingest.save_document_to_corpus), alongside the
# semantic-index disk cache and the alert-acknowledgement/dispatch/audit
# stores — all of it lives under data/ — mount a volume there in
# docker-compose.yml so all four survive a container restart.
ENV PYTHONUNBUFFERED=1

EXPOSE 8100

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8100"]
