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
