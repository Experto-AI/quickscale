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
  # Check DB_USER (will be mapped to POSTGRES_USER by docker-compose)
  if [ -z "$DB_USER" ]; then
    echo "ERROR: Required environment variable DB_USER is not set"
    echo "Please ensure DB_USER is defined in your .env file"
    exit 1
  fi
  
  if [ "$DB_USER" = "root" ]; then
    echo "ERROR: Cannot use 'root' as database user"
    echo "Please use a different username in your .env file"
    exit 1
  fi
  
  # Check DB_PASSWORD (will be mapped to POSTGRES_PASSWORD by docker-compose)
  if [ -z "$DB_PASSWORD" ]; then
    echo "ERROR: Required environment variable DB_PASSWORD is not set"
    echo "Please ensure DB_PASSWORD is defined in your .env file"
    exit 1
  fi
  
  # Check DB_NAME (will be mapped to POSTGRES_DB by docker-compose)
  if [ -z "$DB_NAME" ]; then
    echo "ERROR: Required environment variable DB_NAME is not set"
    echo "Please ensure DB_NAME is defined in your .env file"
    exit 1
  fi
}

# Validate environment before proceeding
validate_env

# Wait for PostgreSQL to start up
echo "Waiting for PostgreSQL to start up..."
MAX_RETRIES=10
RETRY_COUNT=0

# Connect to the database using the standardized DB_* variables
until PGPASSWORD=$DB_PASSWORD psql -h $DB_HOST -U $DB_USER -d $DB_NAME -c "SELECT 1" > /dev/null 2>&1 || [ $RETRY_COUNT -eq $MAX_RETRIES ]; do
  echo "Waiting for PostgreSQL to start, retry $((RETRY_COUNT+1))/$MAX_RETRIES..."
  RETRY_COUNT=$((RETRY_COUNT+1))
  sleep 5
  
  # On every other attempt, check if DB is reachable via netcat
  if [ $((RETRY_COUNT % 2)) -eq 0 ]; then
    echo "Checking if PostgreSQL port is reachable..."
    if nc -z $DB_HOST 5432; then
      echo "PostgreSQL port is reachable, but connection failed. Trying again..."
      # Debug connection issue
      echo "Attempting connection with: psql -h $DB_HOST -U $DB_USER -d $DB_NAME"
    else
      echo "PostgreSQL port is not reachable yet."
    fi
  fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
  echo "Error: could not connect to PostgreSQL after $MAX_RETRIES attempts!"
  echo "Please check your database configuration and ensure the database service is running."
  echo "Database: $DB_NAME, User: $DB_USER, Host: $DB_HOST"
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

# Create default test accounts if they don't exist
echo "Creating default test accounts..."
python manage.py create_default_users

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

exec "$@" 