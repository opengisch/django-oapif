#!/usr/bin/env bash

set -e
set -x

SIZE=${1:-100}


docker compose exec django python manage.py flush --no-input

docker compose exec django python manage.py populate_users
docker compose exec django python manage.py populate_data -s ${SIZE}

docker compose exec django python manage.py loaddata polygon_2056 polygon_2056_local_geom
