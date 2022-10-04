from django.http import HttpResponse
from django_wfs3.mixins import WFS3DescribeModelViewSetMixin
from rest_framework import viewsets
from rest_framework_gis.serializers import GeoFeatureModelSErializer
from signalo_app.models import Sign, Pole


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
    wfs3_srid = 2056  # (one day this will be retrieved automatically from the DB field)


class PoleViewset(WFS3DescribeModelViewSetMixin, viewsets.ModelViewSet):
    queryset = Pole.objects.all()
    serializer_class = PoleSerializer
    wfs3_title = "PoleWFS3Model"
    wfs3_description = "PoleWFS3Model layer"
    wfs3_geom_lookup = (
        "geom"  # (one day this will be retrieved automatically from the serializer)
    )
    wfs3_srid = 2056  # (one day this will be retrieved automatically from the DB field)
