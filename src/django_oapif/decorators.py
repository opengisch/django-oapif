from os import getenv
from typing import Any, Callable, Dict, Optional

from django.contrib.gis.geos import Polygon
from django.db.models import Model
from django.http import HttpResponseBadRequest
from pyproj import CRS, Transformer
from rest_framework import viewsets
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from django_oapif.mixins import OAPIFDescribeModelViewSetMixin
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

        """ ON HOLD, WAITING ON GeoFeatureModelSerializer to admit of null geometries """
        # class AutoNoGeomSerializer(ModelSerializer):
        #     class Meta:
        #         model = Model
        #         fields = "__all__"

        # if skip_geom:
        #     viewset_serializer_class = AutoNoGeomSerializer
        #     viewset_oapif_geom_lookup = None
        # else:
        viewset_serializer_class = AutoSerializer
        viewset_oapif_geom_lookup = (
            "geom"  # one day this will be retrieved automatically from the serializer
        )

        # Create the viewset
        class Viewset(OAPIFDescribeModelViewSetMixin, viewsets.ModelViewSet):
            queryset = Model.objects.all()
            serializer_class = viewset_serializer_class

            # TODO: these should probably be moved to the mixin
            oapif_title = Model._meta.verbose_name
            oapif_description = Model.__doc__

            # (one day this will be retrieved automatically from the serializer)
            oapif_geom_lookup = viewset_oapif_geom_lookup
            filter_backends = [BboxFilterBackend]

            # Allowing '.' and '-' in urls
            lookup_value_regex = r"[\w.-]+"

            def get_queryset(self):
                # Override get_queryset to catch bbox-crs
                queryset = super().get_queryset()

                if self.request.GET.get("bbox"):
                    coords = self.request.GET["bbox"].split(",")
                    user_crs = self.request.GET.get("bbox-crs")

                    if user_crs:
                        try:
                            crs_epsg = int(user_crs)
                        except ValueError:
                            return HttpResponseBadRequest(
                                "This API supports only EPSG-specified CRS. Make sure to use the appropriate value for the `bbox-crs`query parameter."
                            )
                        user_crs = CRS.from_epsg(crs_epsg)
                        api_crs = CRS.from_epsg(int(getenv("GEOMETRY_SRID", "2056")))
                        transformer = Transformer.from_crs(user_crs, api_crs)
                        transformed_coords = transformer.transform(coords)
                        my_bbox_polygon = Polygon.from_bbox(transformed_coords)

                    else:
                        my_bbox_polygon = Polygon.from_bbox(coords)

                    return queryset.filter(geom__intersects=my_bbox_polygon)

                return queryset.all()

        # Apply custom serializer attributes
        # if viewset_serializer_class.__name__ == "AutoNoGeomSerializer":
        #     for k, v in custom_serializer_attrs.items():
        #         setattr(AutoNoGeomSerializer.Meta, k, v)

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
