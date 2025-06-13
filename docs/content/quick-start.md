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

```python
INSTALLED_APPS = [
    ...
    "django_oapif",
    "ninja",
]
```

Add this to your `urls.py` :


```python
urlpatterns += [
    ...,
    path("oapif/", include(django_oapif.urls)),
    ...,
]
```

## Register your models with the decorator:

```python
# models.py

from django.contrib.gis.db import models
from django_oapif import OAPIF

ogc_api = OAPIF()


@ogc_api.register()
class TestingDecorator(models.Model):
    name = models.CharField(max_length=10)
    geom = models.PointField(srid=2056)
```
