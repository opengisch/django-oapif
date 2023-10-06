from typing import Any, Callable, Dict, Optional

from django.db import models
from django.db.models.functions import Cast
from rest_framework import renderers, serializers, viewsets
from rest_framework.serializers import ModelSerializer
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from django_oapif.metadata import OAPIFMetadata
from django_oapif.mixins import OAPIFDescribeModelViewSetMixin
from django_oapif.renderers import (
    FGBRenderer,
    JSONorjson,
    JSONStreamingRenderer,
    JSONujson,
)
from django_oapif.urls import oapif_router

from .filters import BboxFilterBackend
from .functions import AsGeoJSON

USE_PG_GEOJSON = False


def register_oapif_viewset(
    key: Optional[str] = None,
    skip_geom: Optional[bool] = False,
    custom_serializer_attrs: Dict[str, Any] = None,
    custom_viewset_attrs: Dict[str, Any] = None,
) -> Callable[[Any], models.Model]:
    """
    This decorator takes care of all boilerplate code (creating a serializer, a viewset and registering it) to register
    a model to the default OAPIF endpoint.

    - key: allows to pass a custom name for the collection (defaults to the model's label)
    - custom_serializer_attrs: allows to pass custom attributes to set to the serializer's Meta (e.g. custom fields)
    - custom_viewset_attrs: allows to pass custom attributes to set to the viewset (e.g. custom pagination class)
    """

    if custom_serializer_attrs is None:
        custom_serializer_attrs = {}

    if custom_viewset_attrs is None:
        custom_viewset_attrs = {}

    def inner(Model):
        """
        Create the serializers
        1 for viewsets for models with a geometry and
        1 for viewsets for models without (aka 'non-geometric features').
        """

        _viewset_oapif_geom_lookup = "geom"  # one day this will be retrieved automatically from the serializer
        _geo_field = "geom"
        if skip_geom:
            _viewset_oapif_geom_lookup = None
            _geo_field = None

        if USE_PG_GEOJSON:

            class AutoSerializer(ModelSerializer):
                geojson = serializers.JSONField()

                class Meta:
                    model = Model
                    fields = [
                        "id",
                        "geojson",
                        "field_0",
                        "field_1",
                        "field_2",
                        "field_3",
                        "field_4",
                        "field_5",
                        "field_6",
                        "field_7",
                        "field_8",
                        "field_9",
                    ]

        else:

            class AutoSerializer(GeoFeatureModelSerializer):
                class Meta:
                    nonlocal _geo_field

                    model = Model
                    fields = "__all__"
                    geo_field = _geo_field

        # Create the viewset
        class Viewset(OAPIFDescribeModelViewSetMixin, viewsets.ModelViewSet):
            queryset = Model.objects.all()
            serializer_class = AutoSerializer
            renderer_classes = [renderers.JSONRenderer, FGBRenderer]

            # TODO: these should probably be moved to the mixin
            oapif_title = Model._meta.verbose_name
            oapif_description = Model.__doc__

            # (one day this will be retrieved automatically from the serializer)
            oapif_geom_lookup = _viewset_oapif_geom_lookup
            filter_backends = [BboxFilterBackend]

            # Allowing '.' and '-' in urls
            lookup_value_regex = r"[\w.-]+"

            # Metadata
            metadata_class = OAPIFMetadata

            def finalize_response(self, request, response, *args, **kwargs):
                """Ensure OPTIONS requests get a correct response."""
                response = super().finalize_response(request, response, *args, **kwargs)
                if request.method == "OPTIONS":
                    allowed_actions = self.metadata_class().determine_actions(request, self)
                    allowed_actions = ", ".join(allowed_actions.keys())
                    response.headers["Allow"] = allowed_actions
                return response

            def list(self, request, *args, **kwargs):
                """
                Stream collection items as FGB chunks if 'format=fgb' is passed.
                Stream them as JSON chunks if 'format=json' and streaming=true' are passed.
                Otherwise render them as a single JSON chunk, using a variety of renderers depending on the request.
                """
                if request.query_params.get("format") == "json":
                    if request.query_params.get("streaming", "").casefold() == "true":
                        renderer = JSONStreamingRenderer()
                    elif request.query_params.get("json_encoder", "") == "orjson":
                        renderer = JSONorjson()
                    elif request.query_params.get("json_encoder", "") == "ujson":
                        renderer = JSONujson()
                    else:
                        renderer = renderers.JSONRenderer()
                    request.accepted_renderer = renderer
                    request.accepted_media_type = renderer.media_type
                return super().list(request, *args, **kwargs)

            def get_queryset(self):
                qs = super().get_queryset()

                if USE_PG_GEOJSON:
                    # NOTE the defer should not be needed, as the field should be skipped already when we define `Serializer.Meta.Fields` without the `geom` col
                    qs = qs.defer("geom")
                    qs = qs.annotate(geojson=Cast(AsGeoJSON("geom", False, False), models.JSONField()))

                return qs

        # Apply custom serializer attributes
        for k, v in custom_serializer_attrs.items():
            setattr(AutoSerializer.Meta, k, v)

        # Apply custom viewset attributes
        for k, v in custom_viewset_attrs.items():
            setattr(Viewset, k, v)

        # Register the model
        oapif_router.register(key or Model._meta.label_lower, Viewset, key or Model._meta.label_lower)

        return Model

    return inner
