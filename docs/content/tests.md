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
request, under gunicorn with persistent connections and without debug mode, as a deployment would, and
comments the median times, compared with those of the base branch. As runners differ too much from one
another for a comparison with the results of another run, a second server, from the same image and on
the same data, serves the `django_oapif` of the base branch, and the requests go to each server in turn.
Only the library differs: changes to the dependencies or to the test app are not compared, nor are the
cases that the library of the base branch does not serve, or not in the same format.

To run it locally, on the same stack:

```bash
export COMPOSE_FILE=tests/docker-compose.yml:tests/docker-compose.dev.yml:tests/docker-compose.benchmark.yml
docker compose up --build -d
docker compose exec django python manage.py migrate --no-input
docker compose exec django python manage.py populate_data -s 1000
scripts/download-fixtures.sh
docker compose exec django python manage.py loaddata polygon_2056
pip install -r requirements-bench.txt
python tests/benchmark/main.py
```

To compare with another branch, serve its library next to it:

```bash
mkdir -p /tmp/base && git archive main django_oapif | tar -x -C /tmp/base
docker compose run --detach --no-deps --name django_base --publish 7181:8000 \
  --volume /tmp/base/django_oapif:/usr/src/django_oapif django
python tests/benchmark/main.py --base-url http://localhost:7181/oapif/collections --base-name main
```

The results, a chart and the table of the comment, are written to `tests/benchmark/output/`.
