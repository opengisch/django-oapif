from django.conf import settings
from django.http import HttpResponse
from django_oapif.mixins import OAPIFDescribeModelViewSetMixin
from rest_framework import viewsets
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from signalo_app.models import Pole, Sign


def index(request):
    return HttpResponse("hi")


class PoleSerializer(GeoFeatureModelSerializer):
    class Meta:
        model = Pole
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
    serializer_class = PoleSerializer
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

            from django.contrib.gis.geos import Polygon

            my_bbox_polygon = Polygon.from_bbox(coords)  # [xmin, ymin, xmax, ymax]

            return Pole.objects.filter(geom__intersects=my_bbox_polygon)

        return Pole.objects.all()
