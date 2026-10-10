FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install .

COPY config ./config
RUN mkdir -p data eval/data

EXPOSE 8000
CMD ["python", "-m", "news_analyzer", "web", "--host", "0.0.0.0", "--port", "8000"]
