FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

COPY config ./config
RUN mkdir -p data eval/data

# Python side: collector + LLM analyzer worker. The website is web/Dockerfile (Node).
CMD ["python", "-m", "news_analyzer", "worker"]
