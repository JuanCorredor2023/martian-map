# Phase 1 only: this file builds an image; it never uploads data or publishes it.
FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    MARTIAN_DATA=/data MARTIAN_PUBLIC_MODE=readonly PORT=7860 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin libgdal-dev g++ && rm -rf /var/lib/apt/lists/*
COPY api/requirements.txt /app/api/requirements.txt
# GDAL's Python binding version must match the native library of this image.
RUN python -m pip install --no-cache-dir numpy==2.5.4 setuptools wheel && \
    python -m pip install --no-cache-dir --no-build-isolation \
    -r api/requirements.txt "GDAL==$(gdal-config --version)" ortools==9.15.6755
COPY api /app/api
COPY src /app/src
COPY web /app/web
RUN useradd --uid 1000 --create-home demo && mkdir /data && \
    ln -s /data /app/data && chown demo:demo /data
USER demo
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','7860')+'/health',timeout=4)"
CMD ["sh", "-c", "exec python -m uvicorn api.public_mode:create_app --factory --host 0.0.0.0 --port ${PORT:-7860} --workers 1 --limit-concurrency 32"]
