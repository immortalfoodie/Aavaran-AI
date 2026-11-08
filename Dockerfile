# Aavaran Production Backend Dockerfile
# Optimized for Python 3.11 with WeasyPrint & Cairo system libraries
FROM python:3.11-slim-bookworm

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

# Install system dependencies required for WeasyPrint (Pango, Cairo, fonts)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libjpeg62-turbo \
    libopenjp2-7 \
    fonts-dejavu \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first for caching efficiency
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend source code and knowledge base
COPY api/ ./api/
COPY engine/ ./engine/
COPY kb/ ./kb/
COPY pyproject.toml .

# Expose standard port (can be overridden by cloud provider via $PORT)
EXPOSE 8000

# Run Uvicorn listening on all interfaces with dynamic port binding
CMD ["sh", "-c", "exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
