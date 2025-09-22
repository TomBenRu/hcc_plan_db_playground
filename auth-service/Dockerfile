# auth-service/Dockerfile
FROM python:3.12-slim

LABEL maintainer="HCC Plan Development Team"
LABEL description="FastAPI Authentication Service for Guacamole Multi-User Integration"

# Set working directory
WORKDIR /app

# Install system dependencies (gleich wie HCC Plan)
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY auth-service/requirements_direct_sqlite.txt requirements.txt
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy HCC Plan database package (READ-ONLY Access)
COPY database/ /app/database/
COPY configuration/ /app/configuration/

# Copy Auth Service code
COPY auth-service/ /app/auth-service/

# Set environment variables
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Create non-root user for security
RUN groupadd -r hccauth && useradd -r -g hccauth hccauth
RUN chown -R hccauth:hccauth /app
USER hccauth

# Expose port
EXPOSE 8000

# Run FastAPI application (Direct SQLite Version)
CMD ["python", "auth-service/main_direct_sqlite.py"]
