from rest_framework import viewsets
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from django_oapif.mixins import OAPIFDescribeModelViewSetMixin

from .models import DifferentSrid, HighlyPaginated, VariousGeom
from .pagination import HighlyPaginatedPagination


class VariousGeomSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = VariousGeom
        geo_field = "geom"
        fields = "__all__"


class VariousGeomViewset(OAPIFDescribeModelViewSetMixin, viewsets.ModelViewSet):
    """This viewset demonstrates a mixed geometry layer, which is valid OAPIF,
    but doesn't load properly in QGIS (only first met geometry type will
    display, instead of the usual mixed geometry dialog)"""

    queryset = VariousGeom.objects.all()
    serializer_class = VariousGeomSerializer
    oapif_title = "VariousGeoms"
    oapif_description = "VariousGeoms layer"
    # (one day this will be retrieved automatically from the serializer)
    oapif_geom_lookup = "geom"


class HighlyPaginatedSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = HighlyPaginated
        geo_field = "geom"
        fields = "__all__"


class HighlyPaginatedViewset(OAPIFDescribeModelViewSetMixin, viewsets.ModelViewSet):
    """This viewset demonstrates a highly paginated viewset, to see how well it works in QGIS"""

    queryset = HighlyPaginated.objects.all()
    serializer_class = HighlyPaginatedSerializer
    pagination_class = HighlyPaginatedPagination
    oapif_title = "HighlyPaginateds"
    oapif_description = "HighlyPaginateds layer"
    # (one day this will be retrieved automatically from the serializer)
    oapif_geom_lookup = "geom"


class DifferentSridSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = DifferentSrid
        geo_field = "geom"
        fields = "__all__"


class DifferentSridViewset(OAPIFDescribeModelViewSetMixin, viewsets.ModelViewSet):
    """This viewset demonstrates a highly paginated viewset, to see how well it works in QGIS"""

    queryset = DifferentSrid.objects.all()
    serializer_class = DifferentSridSerializer
    oapif_title = "DifferentSrids"
    oapif_description = "DifferentSrids layer"
    # (one day this will be retrieved automatically from the serializer)
    oapif_geom_lookup = "geom"
