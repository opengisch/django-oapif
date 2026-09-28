# Contributing

django-oapif is developed on [GitHub](https://github.com/opengisch/django-oapif), where issues and pull
requests are welcome.

## Development stack

The [demo](../demo.md) stack is the development one too: `tests/docker-compose.dev.yml`, which `.env.example`
includes, mounts the source for the development server to reload it, and publishes a
[debugpy](https://github.com/microsoft/debugpy) port, 7178 by default.

```bash
cp .env.example .env
docker compose up --build -d
docker compose exec django python manage.py migrate --no-input
docker compose exec django python manage.py populate_users
docker compose exec django python manage.py populate_data
```

The code is formatted and linted by [ruff](https://docs.astral.sh/ruff/), which
[pre-commit](https://pre-commit.com/) runs on every commit once installed:

```bash
pip install pre-commit
pre-commit install
```

## Tests

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

### Other Django versions

The stack installs the latest Django. CI also tests the oldest that django-oapif supports, 5.2, and 6.0:
to run the tests on one of them, build the stack from `docker-compose.django.yml` as well, with
`DJANGO_VERSION` set to it:

```bash
export COMPOSE_FILE=tests/docker-compose.yml:tests/docker-compose.dev.yml:tests/docker-compose.django.yml
export DJANGO_VERSION=5.2
docker compose up --build -d
docker compose exec django python manage.py test
```

## Documentation

The documentation is built with [Zensical](https://zensical.org/), from `docs/content`, and its API
reference from the docstrings of the code:

```bash
pip install -r docs/requirements.txt
zensical serve -f docs/zensical.toml
```
