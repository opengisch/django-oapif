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

oapif = OAPIF(auth=[BasicAuth(), DjangoAuth()])

oapif.register_collection(Point_2056_10fields, AnonReadOnlyCollection)
oapif.register_collection(NoGeom_10fields, AnonReadOnlyCollection)
oapif.register_collection(NoGeom_100fields, AnonReadOnlyCollection)
oapif.register_collection(Line_2056_10fields, AnonReadOnlyCollection)
oapif.register_collection(Polygon_2056, AnonReadOnlyCollection)
oapif.register_collection(SecretLayer, OapifCollection)
oapif.register_collection(MandatoryField, AnonReadOnlyCollection)
oapif.register_collection(Geometry_2056, AnonReadOnlyCollection)
oapif.register_collection(Point_2056_Empty, AnonReadOnlyCollection)
oapif.register_collection(LayerWithForeignKey, AnonReadOnlyCollection)


@oapif.register(Point_2056_10fields)
class Point_2056_10fieldsSubsetCollection(AnonReadOnlyCollection):
    id = "tests.point_2056_10fields_subset"
    fields = ("field_int", "field_str_0")
