import math
from typing import Any, NamedTuple, Optional, TypeAlias

from django.contrib.gis.db.models import Extent
from django.contrib.gis.db.models.functions import AsGeoJSON, Transform
from django.contrib.gis.geos import GEOSGeometry
from django.contrib.gis.geos import Polygon as GEOSPolygon
from django.db import models
from django.db.models.functions import Cast
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from ninja import Header, ModelSchema, Query, Router, Schema
from ninja.errors import AuthorizationError, HttpError
from ninja.schema import NinjaGenerateJsonSchema
from pydantic import ConfigDict

from django_oapif.crs import CRS84_URI, get_srid_from_uri
from django_oapif.geojson import (
    Coordinate2D,
    Coordinate3D,
    Feature,
    FeatureCollection,
    Geometry,
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    NewFeature,
    Point,
    Polygon,
)
from django_oapif.handler import QueryHandler
from django_oapif.permissions import BasePermission
from django_oapif.schema import (
    OAPIFCollection,
    OAPIFCollections,
    OAPIFExtent,
    OAPIFLink,
    OAPIFSpatialExtent,
)
from django_oapif.utils import replace_query_param


class OAPIFCollectionEntry(NamedTuple):
    model_class: models.Model
    id: str
    title: str
    description: str
    geometry_field: str | None
    properties_fields: list[str] | None
    handler: QueryHandler
    auth: type[BasePermission]

    @property
    def srid(self):
        if not self.geometry_field:
            return None
        return self.model_class._meta.get_field(self.geometry_field).srid

    def query(self, request: HttpRequest, crs: str, bbox: str | None = None, bbox_crs: str | None = None):
        output_srid = get_srid_from_uri(crs)
        qs = self.handler.get_queryset(request)
        if self.properties_fields:
            qs = qs.only("pk", *self.properties_fields)
        else:
            qs = qs.all()
        if geom_field := self.geometry_field:
            geometry_query = geom_field if output_srid == self.srid else Transform(geom_field, output_srid)
            qs = qs.annotate(_oapif_geometry=Cast(AsGeoJSON(geometry_query, bbox=True), models.JSONField()))
            if bbox:
                try:
                    minx, miny, maxx, maxy = map(float, bbox.split(","))
                    bbox_geom: GEOSPolygon = GEOSPolygon.from_bbox((minx, miny, maxx, maxy))
                    bbox_geom.srid = get_srid_from_uri(bbox_crs)
                    bbox_expr = bbox_geom if bbox_geom.srid == self.srid else Transform(bbox_geom, self.srid)
                    qs = qs.filter(**{f"{geom_field}__intersects": bbox_expr})
                except ValueError:
                    raise HttpError(400, "Invalid bbox parameter. Expected format: minx,miny,maxx,maxy")
        return qs

    def check_permissions(self, request: HttpRequest):
        if not self.auth().has_permission(request, self.model_class):
            raise AuthorizationError()

    def check_object_permissions(self, request: HttpRequest, obj):
        if not self.auth().has_object_permission(request, obj):
            raise AuthorizationError()

    def json_schema(self, geom_schema: type[Schema], properties_schema: type[Schema]) -> dict[str, Any]:
        schema = properties_schema.model_json_schema(by_alias=False, schema_generator=NinjaGenerateJsonSchema)
        required_fields = set(schema.get("required", []))
        # Optional fields are represented as a AnyOf union of their actual type and None
        # We patch this as it is unnecessary considering optional fields are already infered
        # from the list of required ones
        for field_name, field_props in schema["properties"].items():
            if field_name not in required_fields:
                if (t := field_props.get("anyOf")) and len(t) == 2 and t[1] == {"type": "null"}:
                    for k, v in t[0].items():
                        field_props[k] = v
                    del field_props["anyOf"]

        if geom_field := self.geometry_field:
            schema["properties"][geom_field] = {
                "title": "geometry",
                "x-ogc-role": "primary-geometry",
                "format": f"geometry-{geom_schema.__name__.lower()}",
            }
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["title"] = self.title
        return schema


def get_page_links(request: HttpRequest, limit: int, offset: int, total_count: int, returned_count: int):
    links = [
        OAPIFLink(rel="self", title="items (self)", type="application/geo+json", href=request.build_absolute_uri())
    ]
    if offset > 0:
        links.append(
            OAPIFLink(
                rel="prev",
                title="items (prev)",
                type="application/geo+json",
                href=replace_query_param(request, offset=None if offset - limit <= 0 else offset - limit),
            )
        )
    if offset + limit < total_count:
        links.append(
            OAPIFLink(
                rel="next",
                title="items (next)",
                type="application/geo+json",
                href=replace_query_param(request, offset=offset + limit),
            )
        )
    return links


def get_collection_response(request: HttpRequest, collection: OAPIFCollectionEntry):
    uri_prefix = "collections/" if request.get_full_path().endswith("collections") else ""
    response = OAPIFCollection(
        id=collection.id,
        title=collection.title,
        description=collection.description,
        itemType="feature",
        links=[
            OAPIFLink(
                href=request.build_absolute_uri(f"{uri_prefix}{collection.id}"),
                rel="self",
                type="application/json",
            ),
            OAPIFLink(
                href=request.build_absolute_uri(f"{uri_prefix}{collection.id}/schema"),
                rel="http://www.opengis.net/def/rel/ogc/1.0/schema",
                type="application/json",
            ),
            OAPIFLink(
                href=request.build_absolute_uri(f"{uri_prefix}{collection.id}/items"),
                rel="items",
                type="application/geo+json",
            ),
        ],
    )

    if geom := collection.geometry_field:
        crs_uri = f"http://www.opengis.net/def/crs/EPSG/0/{collection.srid}"
        response.storageCrs = crs_uri
        response.crs = [CRS84_URI, crs_uri]
        if extent := collection.model_class.objects.aggregate(extent=Extent(geom))["extent"]:
            response.extent = OAPIFExtent(spatial=OAPIFSpatialExtent(bbox=[extent], crs=crs_uri))

    return response


def create_collections_router(collections: dict[str, OAPIFCollectionEntry]):
    router = Router()

    @router.get("", response=OAPIFCollections, operation_id="get_collections")
    def list_collections(request: HttpRequest):
        return OAPIFCollections(
            links=[
                OAPIFLink(
                    href=request.build_absolute_uri(),
                    rel="self",
                    type="application/json",
                    title="this document",
                )
            ],
            collections=[
                get_collection_response(request, collection)
                for collection in collections.values()
                if collection.auth().has_permission(request, collection.model_class)
            ],
        )

    return router


def create_collection_router(collection: OAPIFCollectionEntry):
    class PropertiesSchema(ModelSchema):
        model_config = ConfigDict(extra="forbid", from_attributes=True, populate_by_name=True)

        class Meta:
            model = collection.model_class
            fields = collection.properties_fields
            exclude = (
                None
                if collection.properties_fields
                else [collection.model_class._meta.pk.name, collection.geometry_field]
                if collection.geometry_field
                else [collection.model_class._meta.pk.name]
            )

    if collection.geometry_field:
        geom_field = collection.model_class._meta.get_field(collection.geometry_field)
        if geom_field.geom_type.startswith("POINT"):
            Geom: TypeAlias = Point
        elif geom_field.geom_type.startswith("MULTIPOINT"):
            Geom: TypeAlias = MultiPoint
        elif geom_field.geom_type.startswith("LINESTRING"):
            Geom: TypeAlias = LineString
        elif geom_field.geom_type.startswith("MULTILINESTRING"):
            Geom: TypeAlias = MultiLineString
        elif geom_field.geom_type.startswith("POLYGON"):
            Geom: TypeAlias = Polygon
        elif geom_field.geom_type.startswith("MULTIPOLYGON"):
            Geom: TypeAlias = MultiPolygon
        elif geom_field.geom_type.startswith("GEOMETRYCOLLECTION"):
            Geom: TypeAlias = GeometryCollection
        else:
            Geom: TypeAlias = Geometry

        if geom_field.geom_type.endswith("Z") or geom_field.geom_type.endswith("ZM"):
            Coordinate: TypeAlias = Coordinate3D
        else:
            Coordinate: TypeAlias = Coordinate2D

        if geom_field.null:
            GeometrySchema: TypeAlias = Optional[Geom[Coordinate]]
        else:
            GeometrySchema: TypeAlias = Geom[Coordinate]
    else:
        Geom: TypeAlias = None
        GeometrySchema: TypeAlias = None

    FeatureSchema: TypeAlias = Feature[GeometrySchema, PropertiesSchema]
    NewFeatureSchema: TypeAlias = NewFeature[GeometrySchema, PropertiesSchema]
    FeatureCollectionSchema: TypeAlias = FeatureCollection[FeatureSchema]

    json_schema = collection.json_schema(Geom, PropertiesSchema)

    router = Router()

    @router.get("", response=OAPIFCollection, operation_id=f"get_{collection.id}")
    def get_collection(request):
        collection.check_permissions(request)
        return get_collection_response(request, collection)

    @router.get("/schema", operation_id=f"get_{collection.id}_schema")
    def get_schema(request: HttpRequest):
        collection.check_permissions(request)
        return {**json_schema, "$id": request.build_absolute_uri()}

    @router.get("/items", response=FeatureCollectionSchema, operation_id=f"get_{collection.id}_items")
    def get_items(
        request: HttpRequest,
        limit: int = 100,
        offset: int = 0,
        crs: str = CRS84_URI,
        bbox_crs: str = Query(CRS84_URI, alias="bbox-crs"),
        bbox: str | None = Query(None, description="BBOX in the format: minx,miny,maxx,maxy"),
    ):
        collection.check_permissions(request)
        query = collection.query(request, crs, bbox, bbox_crs)
        paginated_query = query[offset : offset + limit]

        total_count = query.count()
        result_count = len(paginated_query)

        features = []
        bbox = [math.inf, math.inf, -math.inf, -math.inf]
        for obj in paginated_query:
            feature = FeatureSchema.from_orm(obj)
            features.append(feature)
            if geometry := feature.geometry:
                bbox = [
                    min(bbox[0], geometry.bbox[0]),
                    min(bbox[1], geometry.bbox[1]),
                    max(bbox[2], geometry.bbox[2]),
                    max(bbox[3], geometry.bbox[3]),
                ]
        if bbox == [math.inf, math.inf, -math.inf, -math.inf]:
            bbox = None

        return FeatureCollectionSchema(
            type="FeatureCollection",
            features=features,
            bbox=bbox,
            numberMatched=total_count,
            numberReturned=result_count,
            links=get_page_links(request, limit, offset, total_count, result_count),
        )

    @router.api_operation(["OPTIONS"], "/items", operation_id=f"get_{collection.id}_items_rights")
    def options_items(
        request: HttpRequest,
        response: HttpResponse,
    ):
        collection.check_permissions(request)
        allowed = ["OPTIONS"]
        for method in ["GET", "POST"]:
            request.method = method
            if collection.auth().has_permission(request, collection.model_class):
                allowed.append(method)
        response.headers["Allow"] = ", ".join(allowed)

    @router.get("/items/{item_id}", response=FeatureSchema, operation_id=f"get_{collection.id}_item")
    def get_item(
        request: HttpRequest,
        item_id: str,
        crs: str = CRS84_URI,
    ):
        collection.check_permissions(request)
        query = collection.query(request, crs)
        item = get_object_or_404(query, pk=item_id)
        collection.check_object_permissions(request, item)
        return FeatureSchema.from_orm(item)

    @router.post("/items", response={201: FeatureSchema}, operation_id=f"create_{collection.id}_item")
    def create_item(
        request: HttpRequest,
        response: HttpResponse,
        feature: NewFeatureSchema,
        crs: str | None = Header(alias="Content-Crs", default=CRS84_URI),
    ):
        collection.check_permissions(request)
        input = feature.properties.model_dump() or {}
        if (geom_field := collection.geometry_field) and feature.geometry:
            geometry = GEOSGeometry(feature.geometry.model_dump_json())
            geometry.srid = get_srid_from_uri(crs)
            input[geom_field] = geometry
        item = collection.model_class.objects.create(**input)
        collection.handler.save_model(request, item, False)
        item = collection.query(request, CRS84_URI).get(pk=item.pk)
        response.headers["Location"] = request.build_absolute_uri(f"items/{item.pk}")
        return 201, FeatureSchema.from_orm(item)

    @router.api_operation(["OPTIONS"], "/items/{item_id}", operation_id=f"create_{collection.id}_item_rights")
    def options_item(
        request: HttpRequest,
        response: HttpResponse,
    ):
        collection.check_permissions(request)
        allowed = ["OPTIONS"]
        for method in ["GET", "PUT", "DELETE"]:
            request.method = method
            if collection.auth().has_permission(request, collection.model_class):
                allowed.append(method)
        response.headers["Allow"] = ", ".join(allowed)

    @router.put("/items/{item_id}", response=FeatureSchema, operation_id=f"replace_{collection.id}_item")
    def replace_item(
        request: HttpRequest,
        item_id: str,
        feature: NewFeatureSchema,
        crs: str | None = Header(alias="Content-Crs", default=CRS84_URI),
    ):
        collection.check_permissions(request)
        item = get_object_or_404(collection.model_class, pk=item_id)
        for field, value in feature.properties.model_dump().items():
            setattr(item, field, value)
        if geom_field := collection.geometry_field:
            if feature.geometry:
                geometry = GEOSGeometry(feature.geometry.model_dump_json())
                geometry.srid = get_srid_from_uri(crs)
            else:
                geometry = None
            setattr(item, geom_field, geometry)
        collection.handler.save_model(request, item, True)
        item = collection.query(request, CRS84_URI).get(pk=item_id)
        return FeatureSchema.from_orm(item)

    @router.delete("/items/{item_id}", operation_id=f"delete_{collection.id}_item")
    def delete_item(
        request: HttpRequest,
        item_id: str,
    ):
        collection.check_permissions(request)
        item = get_object_or_404(collection.model_class, pk=item_id)
        collection.handler.delete_model(request, item)

    return router
