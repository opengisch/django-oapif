#!/usr/bin/env bash

set -e

mkdir -p ./tests/django_oapif_tests/tests/fixtures

# download fixtures
curl -L -o ./tests/django_oapif_tests/tests/fixtures/polygon_2056.json.gz 'https://drive.google.com/uc?export=download&id=1UuGoK_9Y99jiTvQd4juxu85eVZhvlAvy'
curl -L -o ./tests/django_oapif_tests/tests/fixtures/polygon_2056_local_geom.json.gz 'https://drive.google.com/uc?export=download&id=18PGtiptcJiRtLnVq7N64EVQLagse0bu0'
