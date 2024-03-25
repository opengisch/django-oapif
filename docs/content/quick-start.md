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

## Enable the app

Edit settings.py

```
INSTALLED_APPS = [
    ...
    "django_oapif",
    "rest_framework",
    "rest_framework_gis",
]
```

Add this to your `urls.py` :

urlpatterns += [
    ...,
    path("oapif/", include(django_oapif.urls)),
    ...,
]

## Register your models with the decorator:

```python
# models.py

from django.contrib.gis.db import models
from django_oapif import register


@register_oapif_viewset()
class TestingDecorator(models.Model):
    name = models.CharField(max_length=10)
    geom = models.PointField(srid=2056)
```

## Configure global settings

Optionally specify your endpoint's metadata in `settings.py`:

```python
# settings.py
...

OAPIF_TITLE = "My Endpoint"
OAPIF_DESCRIPTION = "Description"
```

Voilà ! Your OAPIF endpoint should be ready to use.
