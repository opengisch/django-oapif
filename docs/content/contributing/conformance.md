# OGC conformance

CI runs the [conformance test suite](https://github.com/opengeospatial/ets-ogcapi-features10) of
OGC API - Features on every pull request, and compares its results with
`tests/conformance/conformance-baseline.json`: when they differ, it comments the difference on the pull
request, and commits the new results to the baseline.

To run it locally, on the development stack:

```bash
docker compose --profile testing_conformance up --build -d
docker compose exec django python manage.py migrate --no-input
docker compose exec django python manage.py populate_users
docker compose exec django python manage.py populate_data
docker compose run conformance_test
```

The report is written to `tests/output/emailable-report.html`.

## OpenAPI 3.1

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
