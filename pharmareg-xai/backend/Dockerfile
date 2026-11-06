FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements*.txt ./
ARG INSTALL_ML=false
ARG INSTALL_VECTOR=false
RUN pip install --no-cache-dir -r requirements.txt && if [ "$INSTALL_ML" = "true" ]; then pip install --no-cache-dir -r requirements-ml.txt; fi
RUN if [ "$INSTALL_VECTOR" = "true" ] && [ "$INSTALL_ML" != "true" ]; then pip install --no-cache-dir chromadb==1.5.9; fi
COPY . .
RUN useradd -m appuser && mkdir /data && chown appuser:appuser /data
USER appuser
ENV STORAGE_DIR=/data
EXPOSE 8000
CMD ["sh","-c","python -m alembic upgrade head && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
