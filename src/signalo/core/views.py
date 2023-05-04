from os import getenv

from django.contrib.gis.geos import Polygon
from django.http import HttpResponse, HttpResponseBadRequest
from pyproj import CRS, Transformer
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


class PoleViewset(OAPIFDescribeModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Pole.objects.all()
    serializer_class = PoleSerializer  # used only for API route
    oapif_title = "Poles"
    oapif_description = "Poles layer"
    # (one day this will be retrieved automatically from the serializer)
    oapif_geom_lookup = "geom"

    def get_queryset(self):
        if self.request.GET.get("bbox"):
            coords = self.request.GET["bbox"].split(",")
            user_crs = self.request.GET.get("bbox-crs")

            if user_crs:
                try:
                    crs_epsg = int(user_crs)
                except ValueError:
                    return HttpResponseBadRequest(
                        "This API supports only EPSG-specified CRS. Make sure to use the appropriate value for the `bbox-crs`query parameter."
                    )
                user_crs = CRS.from_epsg(crs_epsg)
                api_crs = CRS.from_epsg(int(getenv("GEOMETRY_SRID", "2056")))
                transformer = Transformer.from_crs(user_crs, api_crs)
                transformed_coords = transformer.transform(coords)
                my_bbox_polygon = Polygon.from_bbox(transformed_coords)

            else:
                my_bbox_polygon = Polygon.from_bbox(coords)

            return Pole.objects.filter(geom__intersects=my_bbox_polygon)

        return Pole.objects.all()


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
