---
hide:
  - navigation
---

## Run tests

```bash
# unit tests
docker compose exec django python manage.py test

# integration tests
docker compose --profile testing_integration up -d
docker compose run integration_tests
```

### Writing curves

Curves can only be written with GEOS 3.13 or newer and a Django that knows them, so the tests that write
them are skipped on the default stack. To run them, build the stack from `docker-compose.curves.yml` as
well, which uses Debian trixie and a Django fork with curve support:

```bash
export COMPOSE_FILE=tests/docker-compose.yml:tests/docker-compose.dev.yml:tests/docker-compose.curves.yml
docker compose up --build -d
docker compose exec django python manage.py test
```

### Without the arrow extra

GeoArrow is an optional extra, which django-oapif and its tests have to do without. To check it, build the
stack from `docker-compose.no-arrow.yml` as well, which leaves the extra out, and the Arrow tests are
skipped:

```bash
export COMPOSE_FILE=tests/docker-compose.yml:tests/docker-compose.dev.yml:tests/docker-compose.no-arrow.yml
docker compose up --build -d
docker compose exec django python manage.py test
```

## OGC Conformance

You can run the OGC API conformance test suite like this:

```bash
docker compose --profile testing_conformance up --build -d
docker compose exec django python manage.py migrate --no-input
docker compose exec django python manage.py populate_users
docker compose exec django python manage.py populate_data
docker compose run conformance_test
```

Results will be stored to `tests/output/emailable-report.html`

### OpenAPI 3.1

django-ninja serves the API definition as OpenAPI 3.1, and cannot serve 3.0. The conformance
declaration says so with the OpenAPI 3.1 class of the 1.1 draft of OGC API - Features - Part 1,
`http://www.opengis.net/spec/ogcapi-features-1/1.1/conf/oas31`: the published 1.0 standard and
OGC API - Common - Part 1 only define a class for OpenAPI 3.0, which the API therefore does not claim.
Every other class it declares is from the 1.0 standards.

The test suite tests the 1.0 standard, and reads OpenAPI 3.0 only. It rejects the API definition, as the
`"type": "null"` of OpenAPI 3.1 is not valid OpenAPI 3.0, then skips the tests that rely on it, the CRS
ones among them. `tests/conformance/conformance-baseline.json` records this as the expected result.

Support for OpenAPI 3.1 came to the standard with version 1.1
([ogcapi-features#404](https://github.com/opengeospatial/ogcapi-features/issues/404),
[1.1 draft](https://docs.ogc.org/DRAFTS/17-069r5.html)). As of September 2026, no issue about it has
been reported to the [test suite](https://github.com/opengeospatial/ets-ogcapi-features10/issues).

## Benchmark

`tests/benchmark/main.py` times `/items` for five collections, three limits and both formats, in CRS84,
which reprojects the features, and in EPSG:2056, the CRS they are stored in. CI runs it on every pull
request, under gunicorn with persistent connections as a deployment would, and comments the median
times, compared with `tests/benchmark/baseline.csv`: once a pull request is merged, the run on `main`
stores its results there, for the next ones.

To run it locally, on the same stack:

```bash
export COMPOSE_FILE=tests/docker-compose.yml:tests/docker-compose.dev.yml:tests/docker-compose.benchmark.yml
docker compose up --build -d
docker compose exec django python manage.py migrate --no-input
docker compose exec django python manage.py populate_data -s 1000
scripts/download-fixtures.sh
docker compose exec django python manage.py loaddata polygon_2056
pip install -r requirements-bench.txt
python tests/benchmark/main.py --baseline tests/benchmark/baseline.csv
```

The results, a chart and the table of the comment, are written to `tests/benchmark/output/`.
