# Use Python 3.11 slim image as base for smaller size
FROM python:3.11-slim

# Set working directory for all subsequent operations
WORKDIR /app

# Python optimization flags
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install system dependencies and cleanup in single layer
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .