from django_oapif import OAPIF
from django_oapif.handler import DjangoModelPermissionsHandler

from .models import (
    Line_2056_10fields,
    NoGeom_10fields,
    NoGeom_100fields,
    Point_2056_10fields,
    Polygon_2056,
    SecretLayer,
)

ogc_api = OAPIF()

ogc_api.register(
    Point_2056_10fields,
    title="point_2056",
    description="yo",
    properties_fields=["field_bool", "field_int", *[f"field_str_{i}" for i in range(10)]],
)

ogc_api.register(
    NoGeom_10fields,
    title="nogeom_10fields",
    description="yo",
    geometry_field=None,
    properties_fields=[
        "field_bool",
        "field_int",
        *[f"field_str_{i}" for i in range(10)],
    ],
)

ogc_api.register(
    NoGeom_100fields,
    title="nogeom_100fields",
    description="yo",
    geometry_field=None,
    properties_fields=[
        "field_bool",
        "field_int",
        *[f"field_str_{i}" for i in range(100)],
    ],
)

ogc_api.register(
    Line_2056_10fields,
    title="line_2056",
    description="yo",
    properties_fields=[
        "field_bool",
        "field_int",
        *[f"field_str_{i}" for i in range(10)],
    ],
)

ogc_api.register(
    Polygon_2056,
    title="polygon_2056",
    description="yo",
    properties_fields=["name"],
)


ogc_api.register(
    SecretLayer,
    title="secret",
    properties_fields=[
        "field_bool",
        "field_int",
        *[f"field_str_{i}" for i in range(10)],
    ],
    handler=DjangoModelPermissionsHandler,
)
