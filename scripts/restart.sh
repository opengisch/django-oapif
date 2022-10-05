#!/usr/bin/env bash

set -e
docker-compose down --volumes || true
docker-compose up --build -d
sleep 2s
docker-compose exec django python manage.py loaddata pole
