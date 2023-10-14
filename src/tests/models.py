import logging
import uuid

from django.contrib.gis.db import models
from django.utils.translation import gettext as _
from rest_framework import permissions

from django_oapif.decorators import register_oapif_viewset

logger = logging.getLogger(__name__)


class BaseModel10Fields(models.Model):
    class Meta:
        abstract = True

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    field_0 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_1 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_2 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_3 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_4 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_5 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_6 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_7 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_8 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_9 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)


@register_oapif_viewset(crs=2056)
class Point_2056_10fields(BaseModel10Fields):
    geom = models.PointField(srid=2056, verbose_name=_("Geometry"))


@register_oapif_viewset(crs=2056, serialize_geom_in_db=False)
class Point_2056_10fields_local_geom(BaseModel10Fields):
    geom = models.PointField(srid=2056, verbose_name=_("Geometry"))


@register_oapif_viewset(geom_field=None)
class NoGeom_10fields(BaseModel10Fields):
    pass


@register_oapif_viewset(geom_field=None)
class NoGeom_100fields(BaseModel10Fields):
    field_10 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_11 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_12 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_13 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_14 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_15 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_16 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_17 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_18 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_19 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_20 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_21 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_22 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_23 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_24 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_25 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_26 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_27 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_28 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_29 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_30 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_31 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_32 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_33 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_34 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_35 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_36 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_37 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_38 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_39 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_40 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_41 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_42 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_43 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_44 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_45 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_46 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_47 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_48 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_49 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_50 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_51 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_52 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_53 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_54 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_55 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_56 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_57 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_58 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_59 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_60 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_61 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_62 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_63 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_64 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_65 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_66 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_67 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_68 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_69 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_70 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_71 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_72 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_73 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_74 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_75 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_76 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_77 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_78 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_79 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_80 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_81 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_82 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_83 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_84 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_85 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_86 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_87 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_88 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_89 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_90 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_91 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_92 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_93 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_94 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_95 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_96 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_97 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_98 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_99 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)


@register_oapif_viewset(crs=2056)
class Line_2056_10fields(BaseModel10Fields):
    geom = models.LineStringField(srid=2056, verbose_name=_("Geometry"))


@register_oapif_viewset(crs=2056, serialize_geom_in_db=False)
class Line_2056_10fields_local_geom(BaseModel10Fields):
    geom = models.LineStringField(srid=2056, verbose_name=_("Geometry"))


@register_oapif_viewset(crs=2056)
class Polygon_2056(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name=_("Name"), null=True, blank=True)
    geom = models.MultiPolygonField(srid=2056, verbose_name=_("Geometry"))


@register_oapif_viewset(crs=2056, serialize_geom_in_db=False)
class Polygon_2056_local_geom(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name=_("Name"), null=True, blank=True)
    geom = models.MultiPolygonField(srid=2056, verbose_name=_("Geometry"))


@register_oapif_viewset(crs=2056, custom_viewset_attrs={"permission_classes": (permissions.DjangoModelPermissions,)})
class SecretLayer(BaseModel10Fields):
    geom = models.PointField(srid=2056, verbose_name=_("Geometry"))
