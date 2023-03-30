# Django OAPIF

This Django app implements an OGC Services API (a.k.a. OAPIF) for Django.

It provides a Django Rest Framework (DRF) specific router to which you can
regsiter your Viewsets, and thus benefit from all DRF's features (permissions,
serialization, authentication, etc.).

## Usage

> NOTE : these snippets are not tested and may require fixing/adaptations.

0. In `settings.py` make sure that rest_framework is installed:

```python
INSTALLED_APPS = [
    ...,
    "rest_framework",
    "rest_framework_gis",
    ...,
]

```

Add this to your `urls.py` :

1. Define your viewset:

```python
from rest_framework_gis.serializers import GeoFeatureModelSerializer
from geocity.apps.django_oapif.urls import oapif_router

class MyModelSerializer(gis_serializers.GeoFeatureModelSerializer):
    class Meta:
        model = MyModel
        fields = "__all__"
        geo_field = "geom"

class MyModelViewset(OAPIFDescribeModelViewSetMixin, viewsets.ModelViewSet):
    queryset = MyModel.objects.all()
    serializer_class = MyModelSerializer

    oapif_title = "layer title"
    oapif_description = "layer_description"
    oapif_geom_lookup = 'geom'  # (one day this will be retrieved automatically from the serializer)
    oapif_srid = 2056  # (one day this will be retrieved automatically from the DB field)
```

2. Register the routers against the `oapif router` (suggestion: do this in `{your_project}.urls.py`):

```python
oapif_router.register(r"permits", MyModelViewSe`, "permits")
```

3. In the same file, include the router:

```python
urlpatterns += [
    path("oapif/", include(django_oapif.urls))
]
```

Optionally specify your endpoint's metadata in `settings.py`:

```python
OAPIF_TITLE = "My Endpoint"
OAPIF_DESCRIPTION = "Description"
```

## Roadmap / status

This is probably still relatively far from a full OGC Services API implementation and currently only aims to support read-only view from QGIS.

This app will at some point be factored out into a reusable Django library.
