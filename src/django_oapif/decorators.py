import re
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

# taken from https://github.com/geopython/pygeoapi/blob/953b6fa74d2ce292d8f566c4f4d3bcb4161d6e95/pygeoapi/util.py#L90
CRS_AUTHORITY = [
    "AUTO",
    "EPSG",
    "OGC",
]

CRS_URI_PATTERN = re.compile(
    (
        rf"^http://www.opengis\.net/def/crs/"
        rf"(?P<auth>{'|'.join(CRS_AUTHORITY)})/"
        rf"[\d|\.]+?/(?P<code>\w+?)$"
    )
)


# taken from
def get_crs_from_uri(uri: str) -> CRS:
    """
    Get a `pyproj.CRS` instance from a CRS URI.
    Author: @MTachon

    :param uri: Uniform resource identifier of the coordinate
        reference system.
    :type uri: str

    :raises `CRSError`: Error raised if no CRS could be identified from the
        URI.

    :returns: `pyproj.CRS` instance matching the input URI.
    :rtype: `pyproj.CRS`
    """

    try:
        crs = CRS.from_authority(*CRS_URI_PATTERN.search(uri).groups())
    except RuntimeError:
        msg = (
            f"CRS could not be identified from URI {uri!r} "
            f"(Authority: {CRS_URI_PATTERN.search(uri).group('auth')!r}, "
            f"Code: {CRS_URI_PATTERN.search(uri).group('code')!r})."
        )
        raise RuntimeError(msg)
    except AttributeError:
        msg = (
            f"CRS could not be identified from URI {uri!r}. CRS URIs must "
            "follow the format "
            "'http://www.opengis.net/def/crs/{authority}/{version}/{code}' "
            "(see https://docs.opengeospatial.org/is/18-058r1/18-058r1.html#crs-overview)."  # noqa
        )
        raise AttributeError(msg)
    else:
        return crs


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

                api_crs = CRS.from_epsg(int(getenv("GEOMETRY_SRID", "2056")))

                crs = self.request.GET.get(
                    "crs", "http://www.opengis.net/def/crs/OGC/1.3/CRS84"
                )
                do_transform = crs != api_crs

                if self.request.GET["bbox"]:
                    coords = self.request.GET["bbox"].split(",")
                    bbox_crs = self.request.GET.get("bbox-crs")

                    if bbox_crs:
                        try:
                            bbox_crs = get_crs_from_uri(bbox_crs)
                        except:
                            return HttpResponseBadRequest(
                                "This API supports only EPSG-specified CRS. Make sure to use the appropriate value for the `bbox-crs`query parameter."
                            )
                        transformer = Transformer.from_crs(user_crs, api_crs)
                        LL = transformer.transform(coords[0], coords[1])
                        UR = transformer.transform(coords[2], coords[3])
                        my_bbox_polygon = Polygon.from_bbox(
                            [LL[0], LL[1], UR[0], UR[1]]
                        )

                    else:
                        my_bbox_polygon = Polygon.from_bbox(coords)

                    if do_transform:
                        return queryset.filter(
                            geom__intersects=my_bbox_polygon
                        ).transform(srid=crs)
                    else:
                        return queryset.filter(geom__intersects=my_bbox_polygon)

                if do_transform:
                    return queryset.all().transform(srid=crs)
                else:
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
