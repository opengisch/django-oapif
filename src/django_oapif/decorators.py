import json
from typing import Any, Callable, Dict, Optional

from django.contrib.gis.db.models.functions import AsWKB
from django.contrib.gis.geos import Polygon
from django.db import connection
from django.db.models import Model
from django.http import HttpResponseBadRequest, StreamingHttpResponse
from psycopg2 import sql
from pyproj import CRS, Transformer
from typing import Any, Callable, Dict, Optional

from django.db.models import Model
from rest_framework import viewsets
from rest_framework_gis.serializers import GeoFeatureModelSerializer

from django_oapif.db import mk_gen_items
from signalo.settings import GEOMETRY_SRID

from .filters import BboxFilterBackend
from .mixins import OAPIFDescribeModelViewSetMixin
from .urls import oapif_router


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

            def list(self, request):
                # Override list to support downloading items with their geometric
                # field as WKB, or alternatively, download just the geometries as FlatGeoBuf
                geom_as = self.request.GET.get("geom_as")
                only_geom_as = self.request.GET.get("only_geom_as")

                if not geom_as and not only_geom_as:
                    return super().list(request)

                if geom_as is not None and geom_as != "wkb":
                    return super().list(request)

                if only_geom_as is not None and only_geom_as != "fgb":
                    return super().list(request)

                queryset = self.get_queryset()
                limit = self.request.GET.get("limit")
                offset = self.request.GET.get("offset")

                if offset:
                    queryset = queryset[int(offset) :]

                if limit:
                    queryset = queryset[: int(limit)]

                if geom_as == "wkb":
                    queryset = queryset.annotate(wkb=AsWKB("geom"))
                    get_geom = lambda v: bytes(v.wkb)
                    gen_items = mk_gen_items(queryset, get_geom)
                    iterable = (json.dumps(item) for item in gen_items)
                    return StreamingHttpResponse(iterable)

                if only_geom_as == "fgb":
                    table_name = Model._meta.db_table
                    pks = tuple(queryset.values_list("id", flat=True))
                    query = sql.SQL(
                        """
                        WITH rows AS (SELECT geom FROM {table} WHERE id IN %s)
                        SELECT encode(ST_AsFlatGeobuf(rows), 'base64') FROM rows
                    """
                    ).format(table=sql.Identifier(table_name))

                    with connection.cursor() as cur:
                        cur.execute(query, (pks,))
                        iterable = cur.fetchall()

                    return StreamingHttpResponse(iterable)

            def get_queryset(self):
                # Override get_queryset to catch bbox-crs
                queryset = self.filter_queryset(super().get_queryset())

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
                        api_crs = CRS.from_epsg(GEOMETRY_SRID)
                        transformer = Transformer.from_crs(user_crs, api_crs)
                        transformed_coords = transformer.transform(coords)
                        my_bbox_polygon = Polygon.from_bbox(transformed_coords)

                    else:
                        my_bbox_polygon = Polygon.from_bbox(coords)

                    return queryset.filter(geom__intersects=my_bbox_polygon)

                return queryset.all()

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
