FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    default-libmysqlclient-dev \
    pkg-config \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml .
COPY src/ ./src/

# Install Python dependencies
RUN pip install --no-cache-dir .

# Create non-root user for security
RUN groupadd --gid 1000 eam \
    && useradd --uid 1000 --gid eam --shell /bin/bash --create-home eam \
    && chown -R eam:eam /app

# Switch to non-root user
USER eam

# Expose port
EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
