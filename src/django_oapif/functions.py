from django.contrib.gis.db.models import functions
from django.db import models

# see https://code.djangoproject.com/ticket/34882#ticket
# and https://github.com/django/django/pull/17320


class AsGeoJSON(functions.AsGeoJSON):
    output_field = models.TextField()

    def __init__(self, expression, bbox=False, crs=False, precision=8, **extra):
        expressions = [expression]
        if precision is not None:
            expressions.append(self._handle_param(precision, "precision", int))
        options = 0
        if crs and bbox:
            options = 3
        elif bbox:
            options = 1
        elif crs:
            options = 2
        expressions.append(options)
        super().__init__(*expressions, **extra)
