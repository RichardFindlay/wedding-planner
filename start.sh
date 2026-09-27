#!/bin/sh
# Railway start command: prepare the database, then serve.
set -e
python manage.py migrate --noinput
python manage.py collectstatic --noinput
python manage.py setup_wedding
exec gunicorn config.wsgi --bind "0.0.0.0:${PORT:-8000}" --workers 2 --timeout 60 --access-logfile -
