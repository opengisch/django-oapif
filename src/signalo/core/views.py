from django.contrib.gis.geos import Polygon
from django.http import HttpResponse
from rest_framework import viewsets
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from django_oapif.mixins import OAPIFDescribeModelViewSetMixin
from django_oapif.pagination import HighPerfPagination

from .models import Pole


def index(request):
    return HttpResponse("hi")


class OapifResponse(HttpResponse):
    def __init__(self, data):
        data = f'{{"type": "FeatureCollection", "features": [{",".join(data)}]}}'
        super(OapifResponse, self).__init__(data)


class PoleSerializer(GeoFeatureModelSerializer):
    # used only for API route
    class Meta:
        model = Pole
        geo_field = "geom"
        exclude = ["_serialized"]


class PoleHighPerfViewset(OAPIFDescribeModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = PoleSerializer
    pagination_class = HighPerfPagination
    oapif_title = "Poles (high perf)"
    oapif_description = "Poles layer - including high performance optimization"
    # (one day this will be retrieved automatically from the serializer)
    oapif_geom_lookup = "geom"

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        queryset = queryset.values_list("_serialized", flat=True)

        serialized_poles = []

        page = self.paginate_queryset(queryset)
        if page is not None:
            for pole in page:
                serialized_poles.append(pole or "")
            return self.get_paginated_response(serialized_poles)

        for pole in queryset:
            serialized_poles.append(pole or "")

        return OapifResponse(serialized_poles)

    def get_queryset(self):
        if self.request.GET.get("bbox"):
            coords = self.request.GET["bbox"].split(",")
            my_bbox_polygon = Polygon.from_bbox(coords)
            return Pole.objects.filter(geom__intersects=my_bbox_polygon)

        return Pole.objects.all()
