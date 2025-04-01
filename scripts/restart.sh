#!/usr/bin/env bash

set -e

SIZE=${1:-100}
BUILD=""

show_help() {
    echo "Usage: $(basename "$0") [OPTIONS]... [ARGUMENTS]..."
    echo
    echo "Description:"
    echo "  Build and run Docker container with SIGNALO application"
    echo
    echo "Options:"
    echo "  -h      Display this help message and exit"
    echo "  -b      Build Docker image"
    echo "  -d      Load demo data"
    echo "  -r      Create roles"
    echo "  -p      Override PG port"
}

while getopts 'bdrp:h' opt; do
  case "$opt" in
    b)
      echo "Rebuild docker image"
      BUILD="--build --force-recreate"
      ;;

    d)
      echo "Load demo data"
      DEMO_DATA="-d"
      ;;
    p)
      echo "Overriding PG port to ${OPTARG}"
      TWW_PG_PORT=${OPTARG}
      ;;
    ?|h)
      echo "Usage: $(basename $0) [-bd] [-p PG_PORT]"
      exit 1
      ;;
  esac
done
shift "$(($OPTIND -1))"


docker compose down --volumes || true
docker compose up ${BUILD} -d

docker compose exec django python manage.py migrate
docker compose exec django python manage.py populate_users
docker compose exec django python manage.py populate_data --size $SIZE
