#!/usr/bin/env bash

set -e

SIZE=${1:-100}

rm src/tests/migrations/0*.py || true

docker compose down --volumes || true

docker compose up --build --force-recreate -d
sleep 5

docker compose exec django python manage.py makemigrations
docker compose exec django python manage.py migrate

docker compose exec django python manage.py collectstatic --no-input
docker compose exec django python manage.py populate_users
docker compose exec django python manage.py populate_data -s ${SIZE}
