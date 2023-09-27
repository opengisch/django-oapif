#!/usr/bin/env bash

set -e

FULL=$1

#if [[ $FULL == "reset" ]];then
  #rm signalo/signalo_app/migrations/00*.py || true
#fi

export COMPOSE_FILE=docker-compose.dev.yml:docker-compose.yml

docker-compose down --volumes || true

docker-compose up --build -d
sleep 5

if [[ $FULL == "reset" ]];then
  docker-compose exec django python manage.py makemigrations
  docker-compose exec django python manage.py migrate
fi

docker-compose exec django python manage.py collectstatic --no-input
docker-compose exec django python manage.py populate
