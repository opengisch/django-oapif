import uuid

from django.contrib.gis.db import models
from django.utils.translation import gettext as _


class VariousGeom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.GeometryField(srid=2056, verbose_name=_("Geometry"))


class HighlyPaginated(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField(srid=2056, verbose_name=_("Geometry"))


class DifferentSrid(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField(srid=2154, verbose_name=_("Geometry"))
