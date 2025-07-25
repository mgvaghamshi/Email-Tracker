FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ENVIRONMENT=production

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        postgresql-client \
        gcc \
        libc6-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user first
RUN adduser --disabled-password --gecos '' --uid 1000 appuser

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create necessary directories and set permissions
RUN mkdir -p logs \
    && chown -R appuser:appuser /app \
    && chmod +x run.py

# Switch to non-root user
USER appuser

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Run the application using our run.py script
CMD ["python3", "run.py", "--host", "0.0.0.0", "--port", "8001"]