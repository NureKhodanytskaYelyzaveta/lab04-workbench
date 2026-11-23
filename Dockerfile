# Робоче місце в контейнері: користувач без прав root, сховище й індекс — томами,
# ключ API — змінною оточення (не копіюється в образ).
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    OBSIDIAN_VAULT=/data/vault CHROMA_PATH=/data/chroma WORKBENCH_DB=/data/workbench/workbench.db

RUN useradd --create-home --uid 10001 workbench
WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir uv && uv pip install --system --no-cache -r pyproject.toml

COPY app ./app
COPY kb ./kb
COPY workbench ./workbench
COPY streamlit_app.py ./
COPY .streamlit ./.streamlit

RUN mkdir -p /data/vault /data/chroma /data/workbench && chown -R workbench:workbench /data /app
USER workbench
VOLUME ["/data/vault", "/data/chroma", "/data/workbench"]
EXPOSE 8501

# У контейнері сервер має слухати 0.0.0.0, але порт публікуйте лише на localhost:
#   docker run --rm -p 127.0.0.1:8501:8501 --env-file .env \
#     -v "$OBSIDIAN_VAULT":/data/vault -v "$CHROMA_PATH":/data/chroma -v wb_data:/data/workbench lab04-workbench
CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
