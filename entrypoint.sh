#!/bin/sh

set -e

echo "Waiting for PostgreSQL..."

# Loop until Postgres responds
until nc -z $DATABASE_HOST $DATABASE_PORT; do
  echo "Postgres is unavailable - sleeping"
  sleep 2
done

echo "PostgreSQL is up - continuing"

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Applying database migrations..."
python manage.py migrate --noinput

echo "Starting Gunicorn..."
gunicorn app.wsgi:application --bind 0.0.0.0:8000 --workers 3

#docker exec -it django_web bash