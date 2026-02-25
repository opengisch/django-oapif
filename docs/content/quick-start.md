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
