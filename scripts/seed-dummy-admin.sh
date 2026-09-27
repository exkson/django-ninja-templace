#!/bin/bash
# Create a dummy superuser for local/dev use.
# Credentials: admin@example.com / 1234

set -e
export DJANGO_SUPERUSER_PASSWORD='1234'
uv run python manage.py createsuperuser --email admin@example.com --no-input
