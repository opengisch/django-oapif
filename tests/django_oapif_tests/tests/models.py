import logging
import uuid

from django.contrib.gis.db import models
from django.utils.translation import gettext as _

from .ogc import ogc_api

logger = logging.getLogger(__name__)


class BaseModelWithTenFields(models.Model):
    class Meta:
        abstract = True

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    field_bool = models.BooleanField(default=True)
    field_int = models.IntegerField(null=True, blank=True)
    field_str_0 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_str_1 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_str_2 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_str_3 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_str_4 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_str_5 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_str_6 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_str_7 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_str_8 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_str_9 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)

@ogc_api.register(
    title="point_2056",
    description="yo",
    properties_fields=[
        "field_bool",
        "field_int",
        *[f"field_str_{i}" for i in range(10)]
    ],
)
class Point_2056_10fields(BaseModelWithTenFields):
    geom = models.PointField(srid=2056, verbose_name=_("Geometry"))


@ogc_api.register(
    title="nogeom_10fields",
    description="yo",
    geometry_field=None,
    properties_fields=[
        "field_bool",
        "field_int",
        *[f"field_str_{i}" for i in range(10)],
    ],
)
class NoGeom_10fields(BaseModelWithTenFields):
    pass


@ogc_api.register(
    title="nogeom_100fields",
    description="yo",
    geometry_field=None,
    properties_fields=[
        "field_bool",
        "field_int",
        *[f"field_str_{i}" for i in range(100)],
    ],
)
class NoGeom_100fields(BaseModelWithTenFields):
    field_str_10 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_str_11 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_str_12 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_str_13 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_str_14 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_str_15 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_str_16 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_str_17 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_str_18 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_str_19 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_str_20 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_str_21 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_str_22 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_str_23 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_str_24 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_str_25 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_str_26 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_str_27 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_str_28 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_str_29 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_str_30 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_str_31 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_str_32 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_str_33 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_str_34 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_str_35 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_str_36 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_str_37 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_str_38 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_str_39 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_str_40 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_str_41 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_str_42 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_str_43 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_str_44 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_str_45 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_str_46 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_str_47 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_str_48 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_str_49 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_str_50 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_str_51 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_str_52 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_str_53 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_str_54 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_str_55 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_str_56 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_str_57 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_str_58 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_str_59 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_str_60 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_str_61 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_str_62 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_str_63 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_str_64 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_str_65 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_str_66 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_str_67 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_str_68 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_str_69 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_str_70 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_str_71 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_str_72 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_str_73 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_str_74 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_str_75 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_str_76 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_str_77 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_str_78 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_str_79 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_str_80 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_str_81 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_str_82 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_str_83 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_str_84 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_str_85 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_str_86 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_str_87 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_str_88 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_str_89 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)
    field_str_90 = models.CharField(max_length=255, verbose_name=_("Field 0"), null=True, blank=True)
    field_str_91 = models.CharField(max_length=255, verbose_name=_("Field 1"), null=True, blank=True)
    field_str_92 = models.CharField(max_length=255, verbose_name=_("Field 2"), null=True, blank=True)
    field_str_93 = models.CharField(max_length=255, verbose_name=_("Field 3"), null=True, blank=True)
    field_str_94 = models.CharField(max_length=255, verbose_name=_("Field 4"), null=True, blank=True)
    field_str_95 = models.CharField(max_length=255, verbose_name=_("Field 5"), null=True, blank=True)
    field_str_96 = models.CharField(max_length=255, verbose_name=_("Field 6"), null=True, blank=True)
    field_str_97 = models.CharField(max_length=255, verbose_name=_("Field 7"), null=True, blank=True)
    field_str_98 = models.CharField(max_length=255, verbose_name=_("Field 8"), null=True, blank=True)
    field_str_99 = models.CharField(max_length=255, verbose_name=_("Field 9"), null=True, blank=True)


@ogc_api.register(
    title="line_2056",
    description="yo",
    properties_fields=[
        "field_bool",
        "field_int",
        *[f"field_str_{i}" for i in range(10)],
    ],
)
class Line_2056_10fields(BaseModelWithTenFields):
    geom = models.LineStringField(srid=2056, verbose_name=_("Geometry"))


@ogc_api.register(
    title="polygon_2056",
    description="yo",
    properties_fields=["name"],
)
class Polygon_2056(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255, verbose_name=_("Name"), null=True, blank=True)
    geom = models.MultiPolygonField(srid=2056, verbose_name=_("Geometry"))

@ogc_api.register(
    title="secret",
    properties_fields=[
        "field_bool",
        "field_int",
        *[f"field_str_{i}" for i in range(10)],
    ],
)
class SecretLayer(BaseModelWithTenFields):
    geom = models.PointField(srid=2056, verbose_name=_("Geometry"))
