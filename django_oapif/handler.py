import math
from functools import cache
from typing import Literal, cast

from django.contrib.auth import get_permission_codename
from django.contrib.gis.db.models import GeometryField
from django.contrib.gis.db.models.functions import AsGeoJSON, Transform
from django.contrib.gis.geos import Polygon as GEOSPolygon
from django.db.models import ForeignKey, GeneratedField, JSONField, ManyToManyRel, ManyToOneRel, Model, QuerySet
from django.db.models.functions import Cast
from django.http import HttpRequest
from ninja import ModelSchema, Schema
from ninja.errors import HttpError, ValidationError
from ninja.schema import NinjaGenerateJsonSchema
from pydantic import ConfigDict
from pydantic import ValidationError as PydanticValidationError

from django_oapif.crs import get_srid_from_uri
from django_oapif.geojson import (
    Coordinate2D,
    Coordinate3D,
    Feature,
    FeatureCollection,
    FeaturePatch,
    Geometry,
    GeometryCollection,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)
from django_oapif.utils import PatchSchema

model_config = ConfigDict(
    extra="forbid",
    from_attributes=True,
    validate_by_name=True,
    serialize_by_alias=False,
    loc_by_alias=False,
)


class OapifCollection[M: Model]:
    """
    Base class used to customize authorization and model operations.

    Attributes:
        id:
            The collection identifier when calling the API, eg: `https://example.com/oapif/collections/<id>/items`.
            If not defined, will be set to `model_class._meta.label_lower`.
        title:
            The collection title. If not defined, will be set to `model_class._meta.label`.
        description:
            The collection description.
        geometry_field:
            The collection geometry field. If not defined, the geometry field will be infered from the model.
        fields:
            The list of fields that will be exposed as feature properties. If not defined, all fields will be used.
        readonly_fields:
            The list of fields that will be included in the feature properties, but won't be accepted in Create/Update operations.
        exclude:
            The list of fields to be excluded from the feature properties.exclude:
        ordering:
            The field used to sort the queryset.
    """

    id: str
    title: str
    description: str | None = None

    geometry_field: str | None
    fields: tuple[str, ...]
    readonly_fields: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    ordering = ()

    def __init__(self, model: type[M]) -> None:
        cls = type(self)
        self.model = model
        self.opts = model._meta
        self.id = getattr(cls, "id", model._meta.label_lower)
        self.title = getattr(cls, "title", model._meta.label)

        model_fields = model._meta.get_fields()

        self.srid = None
        self.geometry_field = None
        if not hasattr(cls, "geometry_field"):
            geometry_fields = [field for field in model_fields if isinstance(field, GeometryField)]
            if len(geometry_fields) == 1:
                self.srid = geometry_fields[0].srid  # type: ignore
                self.geometry_field = geometry_fields[0].name
            elif len(geometry_fields) > 1:
                raise Exception(
                    f"Model {model} has more than one geometry field. Please use the `geometry_field` parameter to configure one."
                )
        elif geometry_field := getattr(cls, "geometry_field", None):
            field = self.model._meta.get_field(geometry_field)
            if isinstance(field, GeometryField):
                self.srid = field.srid
                self.geometry_field = field.name
            else:
                raise Exception(f"Field {field} of model {model} is not a GeometryField.")

        self.fields = getattr(
            cls,
            "fields",
            tuple(
                field.name
                for field in model_fields
                if not isinstance(field, (ManyToOneRel, ManyToManyRel)) and not field.name == self.geometry_field
            ),
        )

        self.foreign_key_fields = {
            field.name: field.remote_field.model for field in model_fields if isinstance(field, ForeignKey)
        }

    def query(
        self,
        request: HttpRequest,
        crs: str,
        bbox: str | None = None,
        bbox_crs: str | None = None,
    ) -> QuerySet[M]:
        output_srid = get_srid_from_uri(crs)
        qs = self.get_queryset(request)
        qs = qs.only("pk", *self.get_fields(request))
        if geom_field := self.geometry_field:
            geometry_query = geom_field if output_srid == self.srid else Transform(geom_field, output_srid)
            qs = qs.annotate(_oapif_geometry=Cast(AsGeoJSON(geometry_query, bbox=True), JSONField()))
            if bbox is not None:
                assert bbox_crs is not None
                try:
                    minx, miny, maxx, maxy = map(float, bbox.split(","))
                    bbox_geom: GEOSPolygon = GEOSPolygon.from_bbox((
                        minx,
                        miny,
                        maxx,
                        maxy,
                    ))
                    bbox_geom.srid = get_srid_from_uri(bbox_crs)
                    bbox_expr = bbox_geom if bbox_geom.srid == self.srid else Transform(bbox_geom, self.srid)
                    qs = qs.filter(**{f"{geom_field}__intersects": bbox_expr})
                except ValueError as err:
                    raise HttpError(
                        400,
                        "Invalid bbox parameter. Expected format: minx,miny,maxx,maxy",
                    ) from err
        return qs

    def get_queryset(self, request: HttpRequest) -> QuerySet[M]:
        """Return the model queryset."""
        qs = self.model._default_manager.get_queryset()
        ordering = self.get_ordering(request)
        if ordering:
            qs = qs.order_by(*ordering)
        return qs

    def get_ordering(self, request) -> tuple:
        """
        Hook for specifying field ordering.
        """
        return self.ordering

    def get_fields(self, request, obj=None):
        """
        Hook for specifying fields.
        """
        return self.fields

    def get_exclude(self, request, obj=None):
        """
        Hook for specifying fields.
        """
        return self.exclude

    def get_readonly_fields(self, request, obj=None):
        """
        Hook for specifying custom readonly fields.
        """
        generated_fields = {f.name for f in self.model._meta.get_fields() if isinstance(f, GeneratedField)}
        return set(*self.readonly_fields, *generated_fields)

    def save_model(self, _request: HttpRequest, obj: M, _change: bool) -> None:
        """Given a model instance save it to the database."""
        obj.save()

    def delete_model(self, _request: HttpRequest, obj: M) -> tuple[int, dict[str, int]]:
        """Given a model instance delete it from the database."""
        return obj.delete()

    def has_view_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        """Returns True if the given request has permission to view objects in the collection,
        or a given object if defined.
        """
        codename_view = get_permission_codename("view", self.opts)
        codename_change = get_permission_codename("change", self.opts)
        can_view = request.user.has_perm(f"{self.opts.app_label}.{codename_view}")
        can_change = request.user.has_perm(f"{self.opts.app_label}.{codename_change}")
        return can_view or can_change

    def has_add_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        """Returns True if the given request has permission to create objects in the collection,
        or a given object if defined.
        """
        codename = get_permission_codename("add", self.opts)
        return request.user.has_perm(f"{self.opts.app_label}.{codename}")

    def has_change_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        """Returns True if the given request has permission to change objects in the collection,
        or a given object if defined.
        """
        codename = get_permission_codename("change", self.opts)
        return request.user.has_perm(f"{self.opts.app_label}.{codename}")

    def has_delete_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        """Returns True if the given request has permission to delete objects in the collection,
        or a given object if defined.
        """
        codename = get_permission_codename("delete", self.opts)
        return request.user.has_perm(f"{self.opts.app_label}.{codename}")

    @cache
    def get_geometry_schema(self) -> type[Geometry] | None:
        if self.geometry_field is None:
            return None

        geom_field = cast("GeometryField", self.model._meta.get_field(self.geometry_field))
        is_3d = geom_field.geom_type.endswith("Z") or geom_field.geom_type.endswith("ZM")
        CoordType = Coordinate3D if is_3d else Coordinate2D

        if geom_field.geom_type.startswith("POINT"):
            GeometryType = Point[CoordType]
        elif geom_field.geom_type.startswith("MULTIPOINT"):
            GeometryType = MultiPoint[CoordType]
        elif geom_field.geom_type.startswith("LINESTRING"):
            GeometryType = LineString[CoordType]
        elif geom_field.geom_type.startswith("MULTILINESTRING"):
            GeometryType = MultiLineString[CoordType]
        elif geom_field.geom_type.startswith("POLYGON"):
            GeometryType = Polygon[CoordType]
        elif geom_field.geom_type.startswith("MULTIPOLYGON"):
            GeometryType = MultiPolygon[CoordType]
        elif geom_field.geom_type.startswith("GEOMETRYCOLLECTION"):
            GeometryType = GeometryCollection[CoordType]
        else:
            GeometryType = Geometry[CoordType]

        if geom_field.null:
            return GeometryType | None
        else:
            return GeometryType

    def get_properties_schema(
        self,
        properties_fields: tuple[str, ...] | Literal["__all__"],
        optional_fields: tuple[str, ...] | Literal["__all__"] = (),
    ) -> type[Schema]:
        class Properties(ModelSchema):
            model_config = model_config

            class Meta:
                model = self.model
                fields = properties_fields
                fields_optional = optional_fields

        return Properties

    def get_feature_input_schema(self, request: HttpRequest) -> type[Feature]:
        fields = tuple(
            set(self.get_fields(request)) - set(self.get_exclude(request)) - set(self.get_readonly_fields(request))
        )
        PropertiesSchema = self.get_properties_schema(fields)
        GeometrySchema = self.get_geometry_schema()
        return Feature[GeometrySchema, PropertiesSchema]

    def get_feature_patch_schema(self, request: HttpRequest) -> type[FeaturePatch]:
        fields = tuple(
            set(self.get_fields(request)) - set(self.get_exclude(request)) - set(self.get_readonly_fields(request))
        )
        PropertiesSchema = self.get_properties_schema(fields)
        GeometrySchema = self.get_geometry_schema()
        return FeaturePatch[GeometrySchema, PatchSchema[PropertiesSchema]]

    def get_feature_output_schema(self, request: HttpRequest) -> type[Feature]:
        fields = tuple(set(self.get_fields(request)) - set(self.get_exclude(request)))
        PropertiesSchema = self.get_properties_schema(fields)
        GeometrySchema = self.get_geometry_schema()
        return Feature[GeometrySchema, PropertiesSchema]

    def get_feature_collection_schema(self, request: HttpRequest) -> type[FeatureCollection]:
        FeatureSchema = self.get_feature_output_schema(request)
        return FeatureCollection[FeatureSchema]

    def get_json_schema(self, request: HttpRequest) -> dict:
        properties_schema = self.get_properties_schema(self.get_fields(request))
        schema = properties_schema.model_json_schema(
            by_alias=False,
            schema_generator=NinjaGenerateJsonSchema,
        )

        required_fields = set(schema.get("required", []))
        # Optional fields are represented as a AnyOf union of their actual type and None
        # We patch this as it is unnecessary considering optional fields are already infered
        # from the list of required ones
        for field_name, field_props in schema["properties"].items():
            if field_name not in required_fields:
                types = field_props.get("anyOf")
                if types and len(types) == 2 and types[1] == {"type": "null"}:
                    del field_props["anyOf"]
                    field_props.update(types[0])

        if geom_field := self.geometry_field:
            geom_field = cast("GeometryField", self.model._meta.get_field(self.geometry_field))
            geom_type = geom_field.geom_type.lower()
            if geom_type.endswith("m"):
                geom_type = geom_type[:-1]
            if geom_type.endswith("z"):
                geom_type = geom_type[:-1]
            if geom_type == "geometry":
                geom_type = "any"
            schema["properties"][geom_field.name] = {
                "title": "geometry",
                "x-ogc-role": "primary-geometry",
                "format": f"geometry-{geom_type}",
            }
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        schema["title"] = self.title
        return schema

    def queryset_to_featurecollection(self, request: HttpRequest, qs: QuerySet) -> FeatureCollection:
        features: list[Feature] = []
        bbox = (math.inf, math.inf, -math.inf, -math.inf)
        FeatureSchema = self.get_feature_output_schema(request)
        FeatureCollectionSchema = FeatureCollection[FeatureSchema]
        for obj in qs:
            feature = self._model_to_feature(request, FeatureSchema, obj)
            features.append(feature)
            if geometry := feature.geometry:
                bbox = (
                    min(bbox[0], geometry.bbox[0]),
                    min(bbox[1], geometry.bbox[1]),
                    max(bbox[2], geometry.bbox[2]),
                    max(bbox[3], geometry.bbox[3]),
                )
        if bbox == (math.inf, math.inf, -math.inf, -math.inf):
            bbox = None
        return FeatureCollectionSchema(
            type="FeatureCollection",
            features=features,
            bbox=bbox,
            numberMatched=len(features),
            numberReturned=len(features),
            links=[],
        )

    def model_to_feature(self, request: HttpRequest, obj: M) -> Feature:
        schema = self.get_feature_output_schema(request)
        return self._model_to_feature(request, schema, obj)

    def _model_to_feature(self, request: HttpRequest, schema: type[Feature], obj: M) -> Feature:
        return schema(
            type="Feature",
            id=str(obj.pk),
            geometry=getattr(obj, "_oapif_geometry", None),
            properties=obj,
        )

    def validate_feature_input_or_raise(self, request: HttpRequest, feature: Feature) -> Feature:
        schema = self.get_feature_input_schema(request)
        return self.validate_feature_or_raise(request, schema, feature)

    def validate_feature_patch_or_raise(self, request: HttpRequest, feature: FeaturePatch) -> FeaturePatch:
        schema = self.get_feature_patch_schema(request)
        return self.validate_feature_or_raise(request, schema, feature)

    def validate_feature_or_raise[T: Feature | FeaturePatch](
        self, request: HttpRequest, schema: type[T], feature: T
    ) -> T:
        try:
            validated = schema.model_validate(feature)
            validated.__pydantic_fields_set__ = feature.__pydantic_fields_set__.copy()
            return validated
        except PydanticValidationError as e:
            raise ValidationError(e.errors())  # type: ignore


class AllowAnyCollection[M: Model](OapifCollection):
    """Allows full access to everyone."""

    def has_view_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        return True

    def has_add_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        return True

    def has_change_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        return True

    def has_delete_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        return True


class AuthenticatedCollection[M: Model](OapifCollection):
    """Allows full access to authenticated users only."""

    def has_view_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_add_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_change_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        return bool(request.user and request.user.is_authenticated)

    def has_delete_permission(self, request: HttpRequest, _obj: M | None = None) -> bool:
        return bool(request.user and request.user.is_authenticated)


class AuthenticatedOrReadOnlyCollection[M: Model](AuthenticatedCollection):
    """Allows full access to authenticated users only, but allows readonly access to everyone."""

    def has_view_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        return True


class AnonReadOnlyCollection[M: Model](OapifCollection):
    """Reuses all Django permissions for a given model, but allows readonly access to everyone."""

    def has_view_permission(self, _request: HttpRequest, _obj: M | None = None) -> bool:
        return True
