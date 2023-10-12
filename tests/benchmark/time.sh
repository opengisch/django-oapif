#!/usr/bin/env bash

rm -p benchmark.dat

SIZES=( 100 1000 10000 100000 )
LAYERS=( point_2056_10fields point_2056_10fields_local_geom nogeom_10fields nogeom_100fields line_2056_10fields line_2056_10fields_local_geom polygon_2056_10fields polygon_2056_10fields_local_geom secretlayer )

for SIZE in "${SIZES[@]}"; do
  echo "::group::setup ${SIZE}"
  ./scripts/restart.sh ${SIZE}
  sleep 2
  echo "::endgroup::"

  LIMIT=10
  while [[ $LIMIT -lt $SIZE ]]; do
    LIMIT=$((LIMIT*10))

    for LAYER in "${LAYERS[@]}"; do
      hyperfine -r 10 "curl http://${OGCAPIF_HOST}:${DJANGO_DEV_PORT}/oapif/collections/tests.${LAYER}/items?limit=${LIMIT}" --export-json .time.json
      cat .time.json
      echo "$SIZE,$LIMIT,$LAYER,$(cat .time.json | jq -r '.results[0]| [.mean, .stddev] | @csv')" >> benchmark.dat
    done
  done
done
