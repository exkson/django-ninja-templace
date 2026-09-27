#!/bin/bash
# Wipe the dev SQLite DB and regenerate the core app's migrations from scratch.
# Use while iterating on model changes before anything is deployed.

set -e
rm -f db.sqlite3
find core/migrations -name "[0-9]*.py" -delete
uv run python manage.py makemigrations core
uv run python manage.py migrate
