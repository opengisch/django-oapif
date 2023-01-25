from django.conf import settings
from django.contrib.gis.geos import Polygon
from django.http import HttpResponse
from django_oapif.mixins import OAPIFDescribeModelViewSetMixin
from rest_framework import viewsets
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from signalo_app.models import Pole, Sign


def index(request):
    return HttpResponse("hi")


class OapifResponse(HttpResponse):
    def __init__(self, data):
        data = f'{{"type": "FeatureCollection", "features": [{",".join(data)}]}}'
        super(OapifResponse, self).__init__(data)


class PoleSerializer(GeoFeatureModelSerializer):
    # used only for API route
    class Meta:
        model = Sign
        fields = "__all__"
        geo_field = "geom"


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
    oapif_title = "PoleOAPIFModel"
    oapif_description = "PoleOAPIFModel layer"
    oapif_geom_lookup = (
        "geom"  # (one day this will be retrieved automatically from the serializer)
    )
    oapif_srid = (
        settings.SRID
    )  # (one day this will be retrieved automatically from the DB field)

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # queryset = queryset.values_list("_serialized", flat=True)
        queryset = queryset.values_list("id","geom","name")

        serialized_poles = []

        page = self.paginate_queryset(queryset)
        if page is not None:
            for pole in page:
                serialized_poles.append(
                 f'{{"id": "{pole[0]}", "type": "Feature", "geometry": {pole[1].hexewkb}, "properties": {{"name": "{pole[2]}"}}}}')
            return self.get_paginated_response(serialized_poles)

        for pole in queryset:
            serialized_poles.append(pole or "")
        return OapifResponse(serialized_poles)

    def get_queryset(self):
        if self.request.GET.get("bbox"):
            coords = self.request.GET["bbox"].split(",")
            my_bbox_polygon = Polygon.from_bbox(coords)
            return Pole.objects.filter(geom__intersects=my_bbox_polygon)

        # for key in request.GET.iterkeys()

        return Pole.objects.all()
