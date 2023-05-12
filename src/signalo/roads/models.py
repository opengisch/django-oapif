import uuid

from django.contrib.gis.db import models
from django.utils.translation import gettext as _

from django_oapif.decorators import register_oapif_viewset
from signalo.settings import GEOMETRY_SRID


@register_oapif_viewset()
class Road(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.MultiLineStringField(srid=GEOMETRY_SRID, verbose_name=_("Geometry"))
