from django_oapif import OAPIF
from django_oapif.auth import BasicAuth, DjangoAuth
from django_oapif.handler import AnonReadOnlyCollection, OapifCollection

from .models import (
    Geometry_2056,
    LayerWithForeignKey,
    Line_2056_10fields,
    MandatoryField,
    NoGeom_10fields,
    NoGeom_100fields,
    Point_2056_10fields,
    Point_2056_Empty,
    Polygon_2056,
    SecretLayer,
)

ogc_api = OAPIF(auth=[BasicAuth(), DjangoAuth()])

ogc_api.register(Point_2056_10fields, AnonReadOnlyCollection)
ogc_api.register(NoGeom_10fields, AnonReadOnlyCollection)
ogc_api.register(NoGeom_100fields, AnonReadOnlyCollection)
ogc_api.register(Line_2056_10fields, AnonReadOnlyCollection)
ogc_api.register(Polygon_2056, AnonReadOnlyCollection)
ogc_api.register(SecretLayer, OapifCollection)
ogc_api.register(MandatoryField, AnonReadOnlyCollection)
ogc_api.register(Geometry_2056, AnonReadOnlyCollection)
ogc_api.register(Point_2056_Empty, AnonReadOnlyCollection)
ogc_api.register(LayerWithForeignKey, AnonReadOnlyCollection)


@ogc_api.register_decorator(Point_2056_10fields)
class Point_2056_10fieldsSubsetCollection(AnonReadOnlyCollection):
    id = "tests.point_2056_10fields_subset"
    fields = ("field_int", "field_str_0")
