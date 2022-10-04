from django.conf import settings
from django.http import HttpResponse
from django_wfs3.mixins import WFS3DescribeModelViewSetMixin
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


class SignViewset(WFS3DescribeModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Sign.objects.all()
    serializer_class = SignSerializer
    wfs3_title = "RoadSignWFS3Model"
    wfs3_description = "RoadSignWFS3Model layer"
    wfs3_geom_lookup = (
        "geom"  # (one day this will be retrieved automatically from the serializer)
    )
    wfs3_srid = (
        settings.SRID
    )  # (one day this will be retrieved automatically from the DB field)


class PoleViewset(WFS3DescribeModelViewSetMixin, viewsets.ModelViewSet):
    serializer_class = PoleSerializer
    wfs3_title = "PoleWFS3Model"
    wfs3_description = "PoleWFS3Model layer"
    wfs3_geom_lookup = (
        "geom"  # (one day this will be retrieved automatically from the serializer)
    )
    wfs3_srid = (
        settings.SRID
    )  # (one day this will be retrieved automatically from the DB field)

    def get_queryset(self):
        if self.request.GET.get("bbox"):
            coords = self.request.GET["bbox"].split(",")

            from django.contrib.gis.geos import Polygon

            my_bbox_polygon = Polygon.from_bbox(coords)  # [xmin, ymin, xmax, ymax]

            return Pole.objects.filter(geom__intersects=my_bbox_polygon)

        return Pole.objects.all()
