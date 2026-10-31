FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY server/requirements.txt ./server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

COPY server/ ./server/
COPY index.html admin.html ./
COPY css ./css
COPY js ./js
COPY assets ./assets

# непривилегированный пользователь; /app/data монтируется как volume
RUN useradd -m web && mkdir -p /app/data && chown -R web:web /app
USER web

EXPOSE 8000
CMD ["uvicorn", "server.app:app", "--host", "0.0.0.0", "--port", "8000"]
