#!/usr/bin/env bash

export COMPOSE_FILE=tests/docker-compose.yml:tests/docker-compose.dev.yml:tests/docker-compose.arm64.yml

#docker compose --profile testing_integration up --build -d
docker compose down -v || true
docker compose up --build -d
docker compose exec django python manage.py migrate --no-input
docker compose exec django python manage.py populate_users
docker compose exec django python manage.py populate_data
docker compose exec django python manage.py test
