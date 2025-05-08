#!/bin/bash

set -e

# Check if we should skip entrypoint logic (used during build process)
if [ "${DISABLE_ENTRYPOINT}" = "true" ]; then
  echo "Entrypoint setup disabled, running command directly"
  exec "$@"
  exit 0
fi

# Validate required environment variables
validate_env() {
  if [ -z "$POSTGRES_USER" ]; then
    echo "ERROR: Required environment variable POSTGRES_USER is not set"
    echo "Please ensure POSTGRES_USER is defined in your .env file"
    exit 1
  fi
  
  if [ "$POSTGRES_USER" = "root" ]; then
    echo "ERROR: Cannot use 'root' as PostgreSQL user"
    echo "Please use a different username in your .env file"
    exit 1
  fi
  
  if [ -z "$POSTGRES_PASSWORD" ]; then
    echo "ERROR: Required environment variable POSTGRES_PASSWORD is not set"
    echo "Please ensure POSTGRES_PASSWORD is defined in your .env file"
    exit 1
  fi
  
  if [ -z "$POSTGRES_DB" ]; then
    echo "ERROR: Required environment variable POSTGRES_DB is not set"
    echo "Please ensure POSTGRES_DB is defined in your .env file"
    exit 1
  fi
}

# Validate environment before proceeding
validate_env

# Wait for PostgreSQL to start up
echo "Waiting for PostgreSQL to start up..."
MAX_RETRIES=10
RETRY_COUNT=0

until PGPASSWORD=$POSTGRES_PASSWORD psql -h db -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1" > /dev/null 2>&1 || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
  echo "Waiting for PostgreSQL to start, retry $((RETRY_COUNT+1))/$MAX_RETRIES..."
  RETRY_COUNT=$((RETRY_COUNT+1))
  sleep 5
  
  # On every other attempt, check if DB is reachable via netcat
  if [ $((RETRY_COUNT % 2)) -eq 0 ]; then
    echo "Checking if PostgreSQL port is reachable..."
    if nc -z db 5432; then
      echo "PostgreSQL port is reachable, but connection failed. Trying again..."
    else
      echo "PostgreSQL port is not reachable yet."
    fi
  fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
  echo "Error: could not connect to PostgreSQL after $MAX_RETRIES attempts!"
  echo "Please check your database configuration and ensure the database service is running."
  exit 1
fi

echo "PostgreSQL started successfully!"

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Create superuser if specified in environment
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
  echo "Creating/updating superuser..."
  python manage.py createsuperuser --noinput --username $DJANGO_SUPERUSER_USERNAME --email $DJANGO_SUPERUSER_EMAIL || true
fi

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

exec "$@" 