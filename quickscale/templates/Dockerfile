# Use Python 3.11 slim image as base for smaller size
FROM python:3.11-slim

# Set working directory for all subsequent operations
WORKDIR /app

# Python optimization flags
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV IN_DOCKER True

# Install system dependencies and cleanup in single layer
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    postgresql-client \
    netcat-openbsd \
    curl \
    iputils-ping --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Create quickscale user and group with a home directory
RUN groupadd -r quickscale && useradd -r -g quickscale -d /home/quickscale -m quickscale

# Set hostname
ENV HOSTNAME=quickscale

# Install Python dependencies first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Create logs directory with proper permissions - ensure it's writable for the quickscale user
RUN mkdir -p /app/logs && \
    chmod 775 /app/logs && \
    chown -R quickscale:quickscale /app

# Add entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Switch to quickscale user
USER quickscale

# Set the entrypoint
ENTRYPOINT ["/entrypoint.sh"]