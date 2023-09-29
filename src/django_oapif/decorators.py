from typing import Any, Callable, Dict, Optional

from django.db.models import Model
from rest_framework import renderers, viewsets
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from django_oapif.metadata import OAPIFMetadata
from django_oapif.mixins import OAPIFDescribeModelViewSetMixin
from django_oapif.renderers import FGBRenderer, JSONStreamingRenderer
from django_oapif.urls import oapif_router

from .filters import BboxFilterBackend


def register_oapif_viewset(
    key: Optional[str] = None,
    skip_geom: Optional[bool] = False,
    custom_serializer_attrs: Dict[str, Any] = None,
    custom_viewset_attrs: Dict[str, Any] = None,
) -> Callable[[Any], Model]:
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

        class AutoSerializer(GeoFeatureModelSerializer):
            class Meta:
                model = Model
                fields = "__all__"
                geo_field = "geom"

        # ON HOLD, WAITING ON GeoFeatureModelSerializer to admit of null geometries
        """
        class AutoNoGeomSerializer(ModelSerializer):
            class Meta:
                model = Model
                fields = "__all__
        if skip_geom:
            viewset_serializer_class = AutoNoGeomSerializer
            viewset_oapif_geom_lookup = None
        else:
        """
        viewset_serializer_class = AutoSerializer
        viewset_renderer_classes = [
            renderers.JSONRenderer,
            FGBRenderer,
            JSONStreamingRenderer,
        ]
        viewset_oapif_geom_lookup = (
            "geom"  # one day this will be retrieved automatically from the serializer
        )
        _geo_field = "geom"
        if skip_geom:
            _viewset_oapif_geom_lookup = None
            _geo_field = None

        class AutoSerializer(GeoFeatureModelSerializer):
            class Meta:
                nonlocal _geo_field

                model = Model
                fields = "__all__"
                geo_field = _geo_field

        # Create the viewset
        class Viewset(OAPIFDescribeModelViewSetMixin, viewsets.ModelViewSet):
            queryset = Model.objects.all()
            serializer_class = viewset_serializer_class
            renderer_classes = viewset_renderer_classes

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
                    allowed_actions = self.metadata_class().determine_actions(
                        request, self
                    )
                    allowed_actions = ", ".join(allowed_actions.keys())
                    response.headers["Allow"] = allowed_actions
                return response

            def list(self, request, *args, **kwargs):
                """
                Stream collection items as JSON chunks if 'streaming=true' is passed.
                Stream them as FGB chunks if 'format=fgb' is passed.
                Otherwise render them as a single JSON chunk JSON.
                """
                if request.query_params.get("format") == "json":
                    if request.query_params.get("streaming", "").casefold() == "true":
                        self.renderer_classes = [JSONStreamingRenderer]
                elif request.query_params.get("format") == "fgb":
                    self.renderer_classes = [FGBRenderer]
                return super().list(request, *args, **kwargs)

        # ON HOLD, WAITING ON GeoFeatureModelSerializer to admit of null geometries
        """
        # Apply custom serializer attributes
        if viewset_serializer_class.__name__ == "AutoNoGeomSerializer":
             for k, v in custom_serializer_attrs.items():
                 setattr(AutoNoGeomSerializer.Meta, k, v)
        """
        # Apply custom serializer attributes
        for k, v in custom_serializer_attrs.items():
            setattr(AutoSerializer.Meta, k, v)

        # Apply custom viewset attributes
        for k, v in custom_viewset_attrs.items():
            setattr(Viewset, k, v)

        # Register the model
        oapif_router.register(
            key or Model._meta.label_lower, Viewset, key or Model._meta.label_lower
        )

        return Model

    return inner
