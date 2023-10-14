#!/usr/bin/env bash

set -e

OUTPUT_PATH="tests/benchmark/results"

mkdir -p ${OUTPUT_PATH}
rm -f ${OUTPUT_PATH}/benchmark.dat

SIZES=( 100 1000 10000 100000 )
LAYERS=( point_2056_10fields point_2056_10fields_local_geom nogeom_10fields nogeom_100fields line_2056_10fields line_2056_10fields_local_geom polygon_2056 polygon_2056_local_geom secretlayer )

for SIZE in "${SIZES[@]}"; do
  echo "::group::setup ${SIZE}"
  ./scripts/restart.sh ${SIZE}
  sleep 2
  echo "::endgroup::"

  for LAYER in "${LAYERS[@]}"; do

    ACTUAL_SIZE=$SIZE
    if [[ $LAYER =~ ^polygon_2056.*$ ]]; then
      ACTUAL_SIZE=$(( $ACTUAL_SIZE < 2175 ? $ACTUAL_SIZE : 2175 ))
    fi

    LIMIT=10
    while [[ $LIMIT -lt $ACTUAL_SIZE ]]; do
      LIMIT=$((LIMIT*10))
      LIMIT=$(( LIMIT < ACTUAL_SIZE ? LIMIT : ACTUAL_SIZE ))

      hyperfine --warmup 1 -r 10 "curl http://${OGCAPIF_HOST}:${DJANGO_DEV_PORT}/oapif/collections/tests.${LAYER}/items?limit=${LIMIT}" --export-json ${OUTPUT_PATH}/.time.json
      echo "$ACTUAL_SIZE,$LIMIT,$LAYER,$(cat ${OUTPUT_PATH}/.time.json | jq -r '.results[0]| [.mean, .stddev] | @csv')" >> ${OUTPUT_PATH}/benchmark.dat
    done
  done
done

rm ${OUTPUT_PATH}/.time.json
