# django-ogcapif

**WARNING** This is in under development. API will break. Do not use in production.

*django-ogcapif* allows to easily expose your Django models through an OGCAPI-Features endpoint. It is based on Django REST Framework.

## Table of contents
- [Quickstart](#quickstart)
- [Use from QGIS](#use-from-qgis)
- [Install it as a Django app](#install-it-as-a-django-app)
- [Authentication & permissions](#custom-authentication--permissions)
- [Tests](#tests)
- [OGC conformance](#ogc-conformance)

## Quickstart

This lets you run the Compose application locally and demo it:

```bash
# copy default conf
cp .env.example .env

# start the stack
docker compose up --build -d

# deploy static files and migrate database
docker compose exec django_oapif_tests python manage.py collectstatic --no-input
docker compose exec django_oapif_tests python manage.py migrate --no-input

# A convenience start-up Django command is there
# to populate the database with testdata
docker compose exec django_oapif_tests python manage.py populate_users
docker compose exec django_oapif_tests python manage.py populate_data
```
After waiting little you'll be able to access all collections at http://0.0.0.0:7180/oapif/collections.

Three users are provided out of the box; they can be logged in with through basic authentication; all `123` for password:
- `demo_viewer`
- `demo_editor`
- `admin`

As expected `admin` can access Django Admin at http://0.0.0.0:7180/admin.

## Use from QGIS

When up and running you can access the REST API from QGIS like this:

- Go to `Layers` > `Add layer` > `Add WFS Layer...`
- Create a new connection
  - URL: `https://0.0.0.0:7180/oapif/`
  - Version: `OGC API - Features`
- Click OK and ignore choose to ignore the invalid certificate error and store the exception
- You should see the two layers in the list, select them and choose `add`.

## Install it as a Django app

This project is [hosted on PyPI](https://pypi.org/project/django-ogcapif/). You can install it as a Django app:

```bash
# Install with your favorite package manager
pip3 install --user django_oapif_tests-ogcapif
# Edit your Django project's settings.py accordingly:
settings.py
-----------
INSTALLED_APPS = [
    ...
    django_ogcapif
]
```
## Custom authentication & permissions

By default the viewsets under `tests` use the `DjangoModelPermissionsOrAnonReadOnly` permissions class. You can add model permissions when registering their corresponding viewsets, as `permission_classes` [^1]. Example:

```python
models.py
---------
from rest_framework import permissions
from django.contrib.gis.db import models
from django_oapif import register_oapif_viewset


@register_oapif_viewset(
    custom_viewset_attrs={
        "permission_classes": (permissions.DjangoModelPermissionsOrAnonReadOnly,)
    }
)
class MyModel(models.Model):
    ...
```

[^1]: Refer to https://www.django-rest-framework.org/api-guide/permissions/#api-reference for permission classes.

## Tests

To run all tests, launch the Compose application as shown in the [Quickstart](#quickstart). Then run

    docker compose exec django python manage.py test


## OGC Conformance

You can run the OGC API conformance test suite like this:

```
docker compose run conformance_test
```

Results will be stored to `test_outputs\emailable-report.html
