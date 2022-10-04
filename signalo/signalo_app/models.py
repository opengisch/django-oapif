from django.contrib.gis.db import models
from django.utils.translation import gettext as _
import uuid


class Pole(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField(srid=2056, verbose_name=_("Geometry"))
    name = models.CharField(max_length=255, verbose_name=_("Name"))


class Sign(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pole = models.ForeignKey(
        Pole, on_delete=models.CASCADE, blank=True, null=True, related_name="poles"
    )
    order = models.IntegerField( default=1)