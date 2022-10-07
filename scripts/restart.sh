#!/usr/bin/env bash

set -e

FULL=$1

SRID=4326

if [[ $FULL == "reset" ]];then
  rm signalo/signalo_app/migrations/00*.py || true
   ./scripts/fixture-generator.py -s $SRID -m 100
fi

docker-compose down --volumes || true

docker-compose up --build -d
sleep 5

if [[ $FULL == "reset" ]];then
  docker-compose exec django python manage.py makemigrations
  docker-compose exec django python manage.py migrate
fi

docker-compose exec django python manage.py loaddata pole
docker-compose exec django python manage.py loaddata sign
docker-compose exec django python manage.py updatedata
