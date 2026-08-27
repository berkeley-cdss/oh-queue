#!/bin/bash
set -e

# Tell Flask where the app is
export FLASK_APP=manage.py
export PYTHONPATH=$PYTHONPATH:.

echo "Applying database migrations..."
flask db upgrade

echo "Starting Gunicorn..."
exec "$@"