#!/usr/bin/env bash

LIMIT=${1}

hyperfine -r 10 "curl http://0.0.0.0:7180/oapif/collections/tests.point_2056_10fields/items?limit=${LIMIT}"

hyperfine -r 10 "curl http://0.0.0.0:7180/oapif/collections/tests.point_2056_10fields_local_json/items?limit=${LIMIT}"