import json
from typing import Any, Callable, Dict, Optional

from django.contrib.gis.geos import GEOSGeometry
from django.db import models
from django.db.models.functions import Cast
from rest_framework import reverse, serializers, viewsets
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
    serialize_geom_in_db: Optional[bool] = True,
    geom_field: [str] = "geom",
    crs: Optional[int] = None,
    custom_serializer_attrs: Dict[str, Any] = None,
    custom_viewset_attrs: Dict[str, Any] = None,
) -> Callable[[Any], models.Model]:
    """
    This decorator takes care of all boilerplate code (creating a serializer, a viewset and registering it) to register
    a model to the default OAPIF endpoint.

    - key: allows to pass a custom name for the collection (defaults to the model's label)
    - serialize_geom_in_db: delegate the geometry serialization to the DB
    - geom_field: the geometry field name. If None, a null geometry is produced
    - crs: the EPSG code, if empty CRS84 is assumed
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
        """

        Model.crs = crs

        if serialize_geom_in_db and geom_field:

            class AutoSerializer(GeoFeatureModelSerializer):
                _geom_geojson = serializers.JSONField(required=False, allow_null=True, read_only=True)

                class Meta:
                    model = Model
                    exclude = [geom_field]
                    geo_field = "_geom_geojson"

                def to_internal_value(self, data):
                    # TODO: this needs improvement!!!
                    geo = None
                    if "geometry" in data:
                        geo = data["geometry"]
                        if geo and crs not in geo:
                            geo["crs"] = {"type": "name", "properties": {"name": f"urn:ogc:def:crs:EPSG::{Model.crs}"}}
                    data = super().to_internal_value(data)
                    if geo:
                        data[geom_field] = GEOSGeometry(json.dumps(geo))
                    return data

        else:

            class AutoSerializer(GeoFeatureModelSerializer):
                class Meta:
                    model = Model
                    fields = "__all__"
                    geo_field = geom_field

                def to_internal_value(self, data):
                    # TODO: this needs improvement!!!
                    if "geometry" in data and data["geometry"] is not None and "crs" not in data["geometry"]:
                        data["geometry"]["crs"] = {
                            "type": "name",
                            "properties": {"name": f"urn:ogc:def:crs:EPSG::{Model.crs}"},
                        }
                    data = super().to_internal_value(data)
                    return data

        # Create the viewset
        class OgcAPIFeatureViewSet(OAPIFDescribeModelViewSetMixin, viewsets.ModelViewSet):
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

            def get_success_headers(self, data):
                location = reverse.reverse(f"{self.basename}-detail", {"lookup": data[Model._meta.pk.column]})
                headers = {"Location": location}
                return headers

            def finalize_response(self, request, response, *args, **kwargs):
                response = super().finalize_response(request, response, *args, **kwargs)
                if request.method == "OPTIONS":
                    allowed_actions = self.metadata_class().determine_actions(request, self)
                    allowed_actions = ", ".join(allowed_actions.keys())
                    response.headers["Allow"] = allowed_actions
                return response

            def get_queryset(self):
                qs = super().get_queryset()

                if serialize_geom_in_db and geom_field:
                    qs = qs.annotate(_geom_geojson=Cast(AsGeoJSON(geom_field, False, False), models.JSONField()))

                return qs

        # Apply custom serializer attributes
        for k, v in custom_serializer_attrs.items():
            setattr(AutoSerializer.Meta, k, v)

        # Apply custom viewset attributes
        for k, v in custom_viewset_attrs.items():
            setattr(OgcAPIFeatureViewSet, k, v)

        # Register the model
        oapif_router.register(key or Model._meta.label_lower, OgcAPIFeatureViewSet, key or Model._meta.label_lower)

        return Model

    return inner
