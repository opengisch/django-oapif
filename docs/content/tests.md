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
