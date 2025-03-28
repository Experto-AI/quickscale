#!/bin/bash

set -e

# Check if we should skip entrypoint logic (used during build process)
if [ "${DISABLE_ENTRYPOINT}" = "true" ]; then
  echo "Entrypoint setup disabled, running command directly"
  exec "$@"
  exit 0
fi

# Wait for PostgreSQL to start up
echo "Waiting for PostgreSQL to start up..."
MAX_RETRIES=10
RETRY_COUNT=0

until PGPASSWORD=$POSTGRES_PASSWORD psql -h db -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1" > /dev/null 2>&1 || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
  echo "Waiting for PostgreSQL to start, retry $((RETRY_COUNT+1))/$MAX_RETRIES..."
  RETRY_COUNT=$((RETRY_COUNT+1))
  sleep 5
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
  echo "Error: could not connect to PostgreSQL after $MAX_RETRIES attempts!"
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