from typing import Any, Callable, Dict, Optional

from django.db import connection
from django.db.models import Model
from django.http import StreamingHttpResponse
from psycopg2 import sql
from rest_framework import viewsets
from rest_framework_gis.serializers import GeoFeatureModelSerializer

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

            # Handling BBOX requirements
            filter_backends = [BboxFilterBackend]

            # Allowing '.' and '-' in urls
            lookup_value_regex = r"[\w.-]+"

            def list(self, request):
                # Override list to support downloading geometry
                # in items as FlatGeoBuf
                output = self.request.GET.get("output")

                if output != "fgb":
                    return super().list(request)

                queryset = self.filter_queryset(self.get_queryset())
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
                    return StreamingHttpResponse(cur.fetchall())

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
