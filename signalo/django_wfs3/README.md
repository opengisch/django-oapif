# Django WFS3

This Django app implements an OGC Services API (a.k.a. WFS3) for Django.

It provides a Django Rest Framework (DRF) specific router to which you can
regsiter your Viewsets, and thus benefit from all DRF's features (permissions,
serialization, authentication, etc.).

## Usage

> NOTE : these snippets are not tested and may require fixing/adaptations.

Add this to your `urls.py` :

Register your viewset in the wfs3 router
```python
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from geocity.apps.django_wfs3.urls import wfs3_router

class MyModelSerializer(gis_serializers.GeoFeatureModelSerializer):
    class Meta:
        model = MyModel
        fields = "__all__"
        geo_field = "geom"

class MyModelViewset(WFS3DescribeModelViewSetMixin, viewsets.ModelViewSet):
    queryset = MyModel.objects.all()
    serializer_class = MyModelSerializer

    wfs3_title = "layer title"
    wfs3_description = "layer_description"
    wfs3_geom_lookup = 'geom'  # (one day this will be retrieved automatically from the serializer)
    wfs3_srid = 2056  # (one day this will be retrieved automatically from the DB field)

wfs3_router.register(r"permits", MyModelViewSet, "permits")
```

Add the router to your `urls.py`:

```python
urlpatterns += [
    path("wfs3/", include(django_wfs3.urls))
]
```

Optionally specify your endpoint's metadata in `settings.py`:

```python
WFS3_TITLE = "My Endpoint"
WFS3_DESCRIPTION = "Description"
```

## Roadmap / status

This is probably still relatively far from a full OGC Services API implementation and currently only aims to support read-only view from QGIS.

This app will at some point be factored out into a reusable Django library.
