import uuid

from django.contrib.gis.db import models
from django.utils.translation import gettext as _

from django_oapif.decorators import register_oapif_viewset

from .pagination import HighlyPaginatedPagination


@register_oapif_viewset()
class VariousGeom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.GeometryField(srid=2056, verbose_name=_("Geometry"))


@register_oapif_viewset(
    custom_serializer_attrs={"pagination_class": HighlyPaginatedPagination}
)
class HighlyPaginated(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField(srid=2056, verbose_name=_("Geometry"))


@register_oapif_viewset()
class DifferentSrid(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField(srid=2154, verbose_name=_("Geometry"))
