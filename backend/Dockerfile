# Build context must be the repository ROOT (not backend/), since main.py
# imports feature_config.py from its parent directory as the single source
# of truth for feature extraction. See docker-compose.yml.
FROM python:3.13-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY feature_config.py .
COPY backend/ backend/

EXPOSE 8000

CMD ["uvicorn", "main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]
