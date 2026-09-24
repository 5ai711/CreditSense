FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY creditsense_ml ./creditsense_ml
# Generate the documented synthetic dataset and train the first (tuned) champion at build time,
# so a new container serves immediately. The entrypoint copies it into the data volume once.
ARG BOOTSTRAP_TRIALS=25
RUN python -m creditsense_ml.bootstrap --data-dir /app/seed --trials ${BOOTSTRAP_TRIALS}

COPY docker-entrypoint.sh ./
RUN useradd --system --uid 10001 mlsvc && mkdir -p /data && chown -R mlsvc /data /app/seed
USER mlsvc

ENV ML_DATA_DIR=/data PORT=8000
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=30s --retries=10 \
  CMD python -c "import urllib.request,sys; sys.exit(urllib.request.urlopen('http://localhost:8000/health').status != 200)" 
ENTRYPOINT ["./docker-entrypoint.sh"]
