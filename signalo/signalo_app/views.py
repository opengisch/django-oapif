from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.http import HttpResponse
from rest_framework.response import Response

from django_oapif.mixins import OAPIFDescribeModelViewSetMixin
from rest_framework import viewsets, serializers
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from rest_framework.pagination import LimitOffsetPagination
from signalo_app.models import Pole, Sign


def index(request):
    return HttpResponse("hi")


class OapifResponse(HttpResponse):
    def __init__(self, data):
        data = f'{{"type": "FeatureCollection", "features": [{",".join(data)}]}}'
        super(OapifResponse, self).__init__(data)


class PoleSerializer(serializers.ModelSerializer):
    # used only for API route
    geom_wkb = serializers.ReadOnlyField()

    class Meta:
        model = Pole
        fields = ["id", "geom_wkb", "name", ]


class SignSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Sign
        fields = "__all__"
        geo_field = "geom"


class SignViewset(OAPIFDescribeModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Sign.objects.all()
    serializer_class = SignSerializer
    oapif_title = "RoadSignOAPIFModel"
    oapif_description = "RoadSignOAPIFModel layer"
    oapif_geom_lookup = (
        "geom"  # (one day this will be retrieved automatically from the serializer)
    )
    oapif_srid = (
        settings.SRID
    )  # (one day this will be retrieved automatically from the DB field)


class PoleViewset(OAPIFDescribeModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = PoleSerializer  # used only for API route
    pagination_class = LimitOffsetPagination
    oapif_title = "PoleOAPIFModel"
    oapif_description = "PoleOAPIFModel layer"
    oapif_geom_lookup = (
        "geom"  # (one day this will be retrieved automatically from the serializer)
    )
    oapif_srid = (
        settings.SRID
    )  # (one day this will be retrieved automatically from the DB field)


    def get_queryset(self):
        if self.request.GET.get("bbox"):
            coords = self.request.GET["bbox"].split(",")
            my_bbox_polygon = Polygon.from_bbox(coords)
            return Pole.objects.filter(geom__intersects=my_bbox_polygon)

        return Pole.objects.all()
