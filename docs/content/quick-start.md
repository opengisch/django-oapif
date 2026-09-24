---
hide:
  - navigation
---

# Quickstart

## Installation

Install with your favorite package manager

```bash
pip install --user https://github.com/opengisch/django-oapif
```

Django needs a driver for PostgreSQL, which django-oapif leaves to your project to choose. Unless it has one
already, install [psycopg 3](https://www.psycopg.org/psycopg3/docs/basic/install.html), which Django
recommends:

```bash
pip install "psycopg[binary]"
```

To serve [GeoArrow](geoarrow.md) as well, install the `arrow` extra:

```bash
pip install "django-oapif[arrow]"
```

## Enable the app

Edit settings.py

```python
INSTALLED_APPS = [
    ...
    "django_oapif",
    "ninja",
]
```

## Declare your models:

```python
# models.py

from django.contrib.gis.db import models

class TestModel(models.Model):
    name = models.CharField(max_length=10)
    geom = models.PointField(srid=2056)

class OtherTestModel(models.Model):
    id = models.CharField(max_length=10)
    geom = models.PolygonField(srid=2056)
```

## Instantiate `OAPIF` and register your models:

```python
# oapif.py

from .models import TestModel
from django_oapif import OAPIF

oapif = OAPIF()

oapif.register_collection(TestModel)
oapif.register_collection(OtherTestModel)
```


## Add the API to the Django URLs:
```python
# urls.py

urlpatterns += [
    ...,
    path("oapif/", include(oapif.urls)),
    ...,
]
```

## Deployment

Use persistent database connections. PostGIS prepares each reprojection once per connection, then keeps
it: without them, every request for features in another CRS than the one they are stored in pays for it
again, about 130 ms on the test stack, against well under a millisecond once it is prepared. CRS84, the
default, is such a CRS for any collection stored in a projected one.

Under a WSGI server such as gunicorn, keep connections for a while with
[`CONN_MAX_AGE`](https://docs.djangoproject.com/en/stable/ref/settings/#conn-max-age), and have Django
check one before reusing it with
[`CONN_HEALTH_CHECKS`](https://docs.djangoproject.com/en/stable/ref/settings/#conn-health-checks), in case
the database closed it meanwhile, after a restart for instance:

```python
DATABASES["default"]["CONN_MAX_AGE"] = 600
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
```

Keep the age finite, and under any idle timeout between Django and the database. Each worker thread keeps a
connection of its own, so the workers and threads of every instance have to fit within the
`max_connections` of PostgreSQL, or to go through a connection pooler such as pgbouncer.

Under ASGI, Django advises against persistent connections: use its
[connection pool](https://docs.djangoproject.com/en/stable/ref/databases/#postgresql-pool) instead, which
needs psycopg 3 and `psycopg[pool]`, with `CONN_MAX_AGE` left at 0. Each connection of the pool prepares a
reprojection once, then keeps it too.

```python
DATABASES["default"]["OPTIONS"] = {"pool": True}
```

Django's development server opens a new connection for every request, whatever the settings.
