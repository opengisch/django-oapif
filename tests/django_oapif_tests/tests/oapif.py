from django.db.models import F
from django.db.models.functions import Length
from django_oapif import OAPIF
from django_oapif.auth import BasicAuth, DjangoAuth
from django_oapif.handler import AnonReadOnlyCollection, OapifCollection

from .models import (
    Arc_2056_10fields,
    CurvePolygon_2056,
    Geometry_2056,
    GeometryZ_2056,
    LayerWithConstraints,
    LayerWithDate,
    LayerWithFile,
    LayerWithForeignKey,
    LayerWithOrdering,
    LayerWithVariousTypes,
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
oapif.register_collection(GeometryZ_2056, AnonReadOnlyCollection)
oapif.register_collection(Point_2056_Empty, AnonReadOnlyCollection)
oapif.register_collection(LayerWithForeignKey, AnonReadOnlyCollection)
oapif.register_collection(LayerWithFile, AnonReadOnlyCollection)
oapif.register_collection(LayerWithDate, AnonReadOnlyCollection)
oapif.register_collection(LayerWithOrdering, AnonReadOnlyCollection)
oapif.register_collection(LayerWithVariousTypes, AnonReadOnlyCollection)
oapif.register_collection(Arc_2056_10fields, AnonReadOnlyCollection)
oapif.register_collection(CurvePolygon_2056, AnonReadOnlyCollection)
oapif.register_collection(LayerWithConstraints, AnonReadOnlyCollection)


@oapif.register(Point_2056_10fields)
class Point_2056_10fieldsSubsetCollection(AnonReadOnlyCollection):
    id = "tests.point_2056_10fields_subset"
    fields = ("field_int", "field_str_0")


@oapif.register(LayerWithForeignKey)
class LayerWithForeignKeyPointCollection(AnonReadOnlyCollection):
    """
    Filtered on properties of its point that `query()` annotates: its label, a field of the related model, the
    length of it, an expression, and its geometry.
    """

    id = "tests.layerwithforeignkey_point"

    def query(self, request, crs, bbox=None, bbox_crs=None):
        return (
            super()
            .query(request, crs, bbox, bbox_crs)
            .annotate(
                point_label=F("point__field_str_9"),
                point_label_length=Length("point__field_str_9"),
                point_geom=F("point__geom"),
            )
        )

    def get_queryables(self, request):
        return (*super().get_queryables(request), "point_label", "point_label_length", "point_geom")
