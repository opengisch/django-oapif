#!/usr/bin/env bash

set -e

mkdir -p src/tests/fixtures

# download fixtures
curl -L -o ./src/tests/fixtures/polygon_2056.json.gz 'https://drive.google.com/uc?export=download&id=1DhCDaDAA3YvZIP9XFHiap5wjeCCWIfRU'
cp ./src/tests/fixtures/polygon_2056.json.gz ./src/tests/fixtures/polygon_2056_local_geom.json.gz
