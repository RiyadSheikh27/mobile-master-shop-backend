python manage.py collectstatic --noinput
python manage.py migrate --noinput
gunicorn app.wsgi:application --bind 0.0.0.0:8000 --workers 3 app.wsgi:application