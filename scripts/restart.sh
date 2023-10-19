#!/usr/bin/env bash

set -e

SIZE=${1:-100}


docker compose down --volumes || true
docker compose up --build --force-recreate -d

docker compose exec django python manage.py migrate
