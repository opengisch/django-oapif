import logging
import uuid

from computedfields.models import ComputedFieldsModel
from django.contrib.gis.db import models
from django.utils.translation import gettext as _
from rest_framework import permissions

from django_oapif.decorators import register_oapif_viewset

logger = logging.getLogger(__name__)


@register_oapif_viewset(skip_geom=False)
class Point_2056_10fields(ComputedFieldsModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField(srid=2056, verbose_name=_("Geometry"))
    field_0 = models.CharField(max_length=255, verbose_name=_("Field 0"))
    field_1 = models.CharField(max_length=255, verbose_name=_("Field 1"))
    field_2 = models.CharField(max_length=255, verbose_name=_("Field 2"))
    field_3 = models.CharField(max_length=255, verbose_name=_("Field 3"))
    field_4 = models.CharField(max_length=255, verbose_name=_("Field 4"))
    field_5 = models.CharField(max_length=255, verbose_name=_("Field 5"))
    field_6 = models.CharField(max_length=255, verbose_name=_("Field 6"))
    field_7 = models.CharField(max_length=255, verbose_name=_("Field 7"))
    field_8 = models.CharField(max_length=255, verbose_name=_("Field 8"))
    field_9 = models.CharField(max_length=255, verbose_name=_("Field 9"))


@register_oapif_viewset(skip_geom=True)
class NoGeom_10fields(ComputedFieldsModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    field_0 = models.CharField(max_length=255, verbose_name=_("Field 0"))
    field_1 = models.CharField(max_length=255, verbose_name=_("Field 1"))
    field_2 = models.CharField(max_length=255, verbose_name=_("Field 2"))
    field_3 = models.CharField(max_length=255, verbose_name=_("Field 3"))
    field_4 = models.CharField(max_length=255, verbose_name=_("Field 4"))
    field_5 = models.CharField(max_length=255, verbose_name=_("Field 5"))
    field_6 = models.CharField(max_length=255, verbose_name=_("Field 6"))
    field_7 = models.CharField(max_length=255, verbose_name=_("Field 7"))
    field_8 = models.CharField(max_length=255, verbose_name=_("Field 8"))
    field_9 = models.CharField(max_length=255, verbose_name=_("Field 9"))


@register_oapif_viewset(
    skip_geom=False,
    custom_viewset_attrs={"permission_classes": (permissions.DjangoModelPermissions,)},
)
class Line_2056_10fields(ComputedFieldsModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.LineStringField(srid=2056, verbose_name=_("Geometry"))
    field_0 = models.CharField(max_length=255, verbose_name=_("Field 0"))
    field_1 = models.CharField(max_length=255, verbose_name=_("Field 1"))
    field_2 = models.CharField(max_length=255, verbose_name=_("Field 2"))
    field_3 = models.CharField(max_length=255, verbose_name=_("Field 3"))
    field_4 = models.CharField(max_length=255, verbose_name=_("Field 4"))
    field_5 = models.CharField(max_length=255, verbose_name=_("Field 5"))
    field_6 = models.CharField(max_length=255, verbose_name=_("Field 6"))
    field_7 = models.CharField(max_length=255, verbose_name=_("Field 7"))
    field_8 = models.CharField(max_length=255, verbose_name=_("Field 8"))
    field_9 = models.CharField(max_length=255, verbose_name=_("Field 9"))
