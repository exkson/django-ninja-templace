#!/bin/bash
# Container entrypoint: migrate → collectstatic → (optional) superuser → supervisord.
# supervisord then manages gunicorn (127.0.0.1:8001), the scheduler process
# (APScheduler firing recurring jobs), and nginx (0.0.0.0:8000).

set -e

source /app/.venv/bin/activate
cd /app

python manage.py migrate
python manage.py collectstatic --no-input

if [ -z "$SUPERUSER_EMAIL" ]; then
    echo "SUPERUSER_EMAIL is not set. Skipping superuser creation."
else
    # `createsuperuser --no-input` reads DJANGO_SUPERUSER_PASSWORD from env.
    # The User model has REQUIRED_FIELDS = [] so only email is needed.
    export DJANGO_SUPERUSER_PASSWORD="$SUPERUSER_PASSWORD"
    python manage.py createsuperuser --email "$SUPERUSER_EMAIL" --no-input \
        || echo "Superuser already exists (or creation failed — non-fatal)."
fi

# GUNICORN_WORKERS is read by supervisord from the environment.
export GUNICORN_WORKERS="${GUNICORN_WORKERS:-2}"

exec /usr/bin/supervisord -c /etc/supervisord.conf
