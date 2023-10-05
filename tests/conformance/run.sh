#!/usr/bin/env bash

set -e

OUTPUT_DIR=/build/output
TEST_RUN_PROPS=/build/run/test-run-props.xml


java -jar /build/target/ets-ogcapi-features10-${VERSION}-aio.jar -o /tmp/test_ouputs/ -h true ${TEST_RUN_PROPS}

find /tmp/test_ouputs/ -iname 'emailable-report.html' -exec mv {} ${OUTPUT_DIR} \;
