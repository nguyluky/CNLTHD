FROM python:3.13-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home appuser && chown appuser:appuser /app


FROM base as api

COPY --chown=appuser:appuser app ./app
USER appuser
ENV ENV=production
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]


FROM base as migration
COPY --chown=appuser:appuser script ./script
COPY --chown=appuser:appuser alembic ./alembic
COPY --chown=appuser:appuser app/core ./app/core
COPY --chown=appuser:appuser alembic.ini .

CMD ["python", "-m", "script.migration"]