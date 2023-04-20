# Django OAPIF

This Django app implements an OGC Services API (a.k.a. OAPIF) for Django.

It provides a Django Rest Framework (DRF) specific router to which you can
regsiter your Viewsets, and thus benefit from all DRF's features (permissions,
serialization, authentication, etc.).

## Quickstart

> NOTE : these snippets are not tested and may require fixing/adaptations.

1. In `settings.py` make sure that rest_framework is installed:

```python
INSTALLED_APPS = [
    ...,
    "rest_framework",
    "rest_framework_gis",
    ...,
]

```

Add this to your `urls.py` :

urlpatterns += [
    ...,
    path("oapif/", include(django_oapif.urls)),
    ...,
]

2. Register your models with the decorator:

```python
# models.py

from django.contrib.gis.db import models
from django_oapif.decorators import register

@register()
class TestingDecorator(models.Model):
    name = models.CharField(max_length=10)
    geom = models.PointField(srid=2056)
```

3. Configure global settings

Optionally specify your endpoint's metadata in `settings.py`:

```python
# settings.py
...

OAPIF_TITLE = "My Endpoint"
OAPIF_DESCRIPTION = "Description"
```

Voilà ! Your OAPIF endpoint should be ready to use.

## Advanced use cases

If you need more control over the serialization or the viewset, refer to the decorator's code and to DRF's viewset documentation.

## Roadmap / status

This is probably still relatively far from a full OGC Services API implementation and currently only aims to support read-only view from QGIS.

This app will at some point be factored out into a reusable Django library.

## Releases

Releases are made automatically from the CI whenever a tag in format `v*` is pushed. Please use semantic versionning for tagging releases.
