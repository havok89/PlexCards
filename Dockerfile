# ==========================================
# Stage 1: Build React Frontend
# ==========================================
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# ==========================================
# Stage 2: Python Backend & Final Runtime
# ==========================================
FROM python:3.11-slim AS runtime

# Install system libraries needed by Pillow, font rendering, and healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend application
COPY backend/ ./backend/

# Copy compiled frontend from builder
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create persistence directories
RUN mkdir -p /app/data /app/cache /app/custom_fonts

# Environment variables
ENV PYTHONUNBUFFERED=1 \
    HOST=0.0.0.0 \
    PORT=8080 \
    DATA_DIR=/app/data \
    CACHE_DIR=/app/cache \
    CUSTOM_FONTS_DIR=/app/custom_fonts

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/api/config || exit 1

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8080"]
