# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DJANGO_SETTINGS_MODULE=interlinker_tool.settings

WORKDIR /app

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home app
RUN chown -R app:app /app
USER app

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
