#!/usr/bin/env bash

SIZES=( 100 1000 10000 )
for SIZE in "${SIZES[@]}"; do
  echo "::group::setup ${SIZE}"
  ./scripts/restart.sh ${SIZE}
  echo "::endgroup::"

  LIMIT=10
  while [[ $LIMIT -lt $SIZE ]]; do
    LIMIT=$((LIMIT*10))

  hyperfine -r 10 "curl http://${OGCAPIF_HOST}:${DJANGO_DEV_PORT}/oapif/collections/tests.point_2056_10fields/items?limit=${LIMIT}"
  hyperfine -r 10 "curl http://${OGCAPIF_HOST}:${DJANGO_DEV_PORT}/oapif/collections/tests.point_2056_10fields_local_json/items?limit=${LIMIT}"

  done
done
