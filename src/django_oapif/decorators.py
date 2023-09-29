import json
from typing import Any, Callable, Dict, Optional

from django.contrib.gis.geos import GEOSGeometry
from django.db import models
from django.db.models.functions import Cast
from rest_framework import serializers, viewsets
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from django_oapif.metadata import OAPIFMetadata
from django_oapif.mixins import OAPIFDescribeModelViewSetMixin
from django_oapif.urls import oapif_router

from .filters import BboxFilterBackend

# this should be be switched to contrib
# when https://code.djangoproject.com/ticket/34882#ticket is fixed
from .functions import AsGeoJSON


def register_oapif_viewset(
    key: Optional[str] = None,
    geom_db_serializer: Optional[bool] = True,
    geom_field: [str] = "geom",
    custom_serializer_attrs: Dict[str, Any] = None,
    custom_viewset_attrs: Dict[str, Any] = None,
) -> Callable[[Any], models.Model]:
    """
    This decorator takes care of all boilerplate code (creating a serializer, a viewset and registering it) to register
    a model to the default OAPIF endpoint.

    - key: allows to pass a custom name for the collection (defaults to the model's label)
    - geom_db_serializer: delegate the geometry serialization to the DB
    - geom_field: the geometry field name. If None, a null geometry is produced
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

        if geom_db_serializer and geom_field:

            class AutoSerializer(GeoFeatureModelSerializer):
                _geom_json_db = serializers.JSONField(required=False, allow_null=True, read_only=True)

                class Meta:
                    model = Model
                    exclude = [geom_field]
                    geo_field = "_geom_json_db"

                def to_internal_value(self, data):
                    # TODO: this needs improvement!!!
                    geo = data["geometry"]
                    data = super().to_internal_value(data)
                    data[geom_field] = GEOSGeometry(json.dumps(geo))
                    return data

        else:

            class AutoSerializer(GeoFeatureModelSerializer):
                class Meta:
                    model = Model
                    fields = "__all__"
                    geo_field = geom_field

        # Create the viewset
        class Viewset(OAPIFDescribeModelViewSetMixin, viewsets.ModelViewSet):
            queryset = Model.objects.all()
            serializer_class = AutoSerializer

            # TODO: these should probably be moved to the mixin
            oapif_title = Model._meta.verbose_name
            oapif_description = Model.__doc__

            oapif_geom_lookup = geom_field

            filter_backends = [BboxFilterBackend]

            # Allowing '.' and '-' in urls
            lookup_value_regex = r"[\w.-]+"

            # Metadata
            metadata_class = OAPIFMetadata

            def finalize_response(self, request, response, *args, **kwargs):
                response = super().finalize_response(request, response, *args, **kwargs)
                if request.method == "OPTIONS":
                    allowed_actions = self.metadata_class().determine_actions(request, self)
                    allowed_actions = ", ".join(allowed_actions.keys())
                    response.headers["Allow"] = allowed_actions
                return response

            def get_queryset(self):
                qs = super().get_queryset()

                if geom_db_serializer and geom_field:
                    qs = qs.annotate(_geom_json_db=Cast(AsGeoJSON(geom_field, False, False), models.JSONField()))

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
