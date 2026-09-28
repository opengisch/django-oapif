# Quick start

## Installation

django-oapif needs Python 3.12 and Django 5.2 or later, and is tested on Django 5.2, 6.0 and the latest
release. It serves models stored in PostgreSQL with PostGIS, through the
[GeoDjango](https://docs.djangoproject.com/en/stable/ref/contrib/gis/) PostGIS backend.

Install it with your favorite package manager:

```bash
pip install django-oapif
```

!!! note "Pre-release"

    This documentation describes django-oapif 2.0, which is still in pre-release. pip only installs it when
    asked for:

    ```bash
    pip install "django-oapif>=2.0.0rc1"
    ```

Django needs a driver for PostgreSQL, which django-oapif leaves to your project to choose. Unless it has one
already, install [psycopg 3](https://www.psycopg.org/psycopg3/docs/basic/install.html), which Django
recommends:

```bash
pip install "psycopg[binary]"
```

To serve [GeoArrow](formats/geoarrow.md) as well, install the `arrow` extra:

```bash
pip install "django-oapif[arrow]"
```

## Enable the app

Add GeoDjango, django-oapif and Django Ninja to the installed apps, and use the PostGIS backend:

```python
# settings.py

INSTALLED_APPS = [
    ...
    "django.contrib.gis",
    "django_oapif",
    "ninja",
]

DATABASES = {
    "default": {
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        ...
    }
}
```

## Declare your models

```python
# models.py

from django.contrib.gis.db import models

class TestModel(models.Model):
    name = models.CharField(max_length=10)
    geom = models.PointField(srid=2056)

class OtherTestModel(models.Model):
    id = models.CharField(max_length=10, primary_key=True)
    geom = models.PolygonField(srid=2056)
```

## Register your models

Instantiate `OAPIF`, and register each model as a collection:

```python
# oapif.py

from django_oapif import OAPIF

from .models import OtherTestModel, TestModel

oapif = OAPIF()

oapif.register_collection(TestModel)
oapif.register_collection(OtherTestModel)
```

## Add the API to the URLs

```python
# urls.py

from django.urls import path

from .oapif import oapif

urlpatterns = [
    ...,
    path("oapif/", oapif.urls),
]
```

## Try it

Once Django runs, the API serves:

| Path                                                    | Resource                                                      |
|---------------------------------------------------------|---------------------------------------------------------------|
| `/oapif/`                                               | The landing page                                              |
| `/oapif/conformance`                                    | The conformance classes the API implements                    |
| `/oapif/collections`                                    | The collections                                               |
| `/oapif/collections/{collectionId}`                     | A collection, `my_app.testmodel` for instance                 |
| `/oapif/collections/{collectionId}/schema`              | The schema of its features                                    |
| `/oapif/collections/{collectionId}/items`               | Its features: `GET`, and `POST` to create one                 |
| `/oapif/collections/{collectionId}/items/{featureId}`   | A feature: `GET`, `PUT`, `PATCH` and `DELETE`                 |
| `/oapif/openapi.json`                                   | The OpenAPI definition of the API                             |
| `/oapif/docs`                                           | The same definition, in Swagger UI                            |

By default, a collection is served only to the users with the view or change permission of its model, such as
superusers: log in to the Django admin site first, or see [permissions](usage/permissions.md) to serve it to
anonymous users too.

In QGIS, add the API as a WFS / OGC API - Features connection, with the URL of its landing page and the
`OGC API - Features` version, as in the [demo](demo.md#use-from-qgis). QGIS logs in with HTTP Basic, which the
API takes once it has [`BasicAuth`](usage/permissions.md#authentication).

Before going to production, read about [deployment](usage/deployment.md).
