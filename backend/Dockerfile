FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system prepwise \
    && useradd --system --gid prepwise --create-home prepwise

COPY pyproject.toml ./
COPY src ./src
COPY alembic.ini ./
COPY migrations ./migrations

RUN pip install --no-cache-dir .

USER prepwise

EXPOSE 8000

CMD ["uvicorn", "prepwise_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
