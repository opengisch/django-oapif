from datetime import date, datetime, time
from functools import cache
from types import NoneType, new_class
from typing import Annotated, Literal, cast, get_args, overload
from uuid import UUID

from django.contrib.auth import get_permission_codename
from django.contrib.gis.db.models import Extent, GeometryField
from django.contrib.gis.db.models.functions import AsWKB, Transform
from django.contrib.gis.geos import Polygon as GEOSPolygon
from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import (
    DateTimeField,
    DurationField,
    FileField,
    ForeignKey,
    Func,
    GeneratedField,
    ManyToManyRel,
    ManyToOneRel,
    Model,
    QuerySet,
    TextField,
    TimeField,
)
from django.http import HttpRequest
from ninja import Field, ModelSchema, Schema
from ninja.errors import ValidationError
from ninja.schema import NinjaGenerateJsonSchema
from pydantic import ConfigDict, field_serializer
from pydantic import ValidationError as PydanticValidationError
from pydantic.config import ExtraValues

from django_oapif import jsonfg
from django_oapif.crs import CRS, CRS84_SRID, BBox
from django_oapif.geojson import (
    CircularString,
    CircularStringParts,
    CompoundCurve,
    Coordinate2D,
    Coordinate3D,
    CurvePolygon,
    Feature,
    FeatureCollection,
    FeaturePatch,
    Geometry,
    GeometryCollection,
    LineString,
    MultiCurve,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    MultiSurface,
    Point,
    Polygon,
)
from django_oapif.schema import OAPIFLink
from django_oapif.utils import PatchSchema

try:
    import geoarrow.pyarrow as ga
    import pyarrow as pa

    ARROW_AVAILABLE = True

    # A page carries its own schema, so it has to be derived from the property types rather than
    # from the values: a column that happens to be all null on one page would otherwise come back
    # null-typed and no longer concatenate with the other pages.
    ARROW_TYPES = {
        bool: pa.bool_(),
        int: pa.int64(),
        float: pa.float64(),
        str: pa.string(),
        UUID: pa.string(),  # serialized with str() below
        date: pa.date32(),
        datetime: pa.timestamp("us", tz="UTC"),
        time: pa.time64("us"),
    }
except ImportError:
    ARROW_AVAILABLE = False


model_config = {
    "from_attributes": True,
    "validate_by_name": True,
    "serialize_by_alias": False,
    "loc_by_alias": False,
}


def parse_box2d(value: str) -> tuple[float, float, float, float]:
    """Read a PostGIS box, which comes as 'BOX(xmin ymin,xmax ymax)'."""
    xmin, ymin, xmax, ymax = map(float, value.removeprefix("BOX(").removesuffix(")").replace(",", " ").split())
    return xmin, ymin, xmax, ymax


class ReprojectedExtent(Func):
    """
    The extent of a geometry column in another CRS, as a PostGIS box. Reprojecting every geometry to get it
    would be slow, so the extent is computed where they are stored, and only its outline is reprojected:
    densified first, as the edges of a box curve once reprojected, and its corners alone would miss the
    bulge, over a kilometre across Switzerland.
    """

    output_field = TextField()

    def __init__(self, geometry, source_srid: int, target_srid: int):
        super().__init__(Extent(geometry))
        self.source_srid = int(source_srid)
        self.target_srid = int(target_srid)

    def as_sql(self, compiler, connection, **extra_context):
        extent, params = compiler.compile(self.source_expressions[0])
        box = f"ST_SetSRID({extent}::geometry, {self.source_srid})"
        sql = f"Box2D(ST_Transform(ST_Segmentize({box}, ST_Perimeter({box}) / 128), {self.target_srid}))"
        return sql, (*params, *params)


def without(fields: tuple[str, ...], *excluded: tuple[str, ...]) -> tuple[str, ...]:
    """
    The fields minus the excluded ones, in their declared order. A set difference would do, but its
    order changes from one process to the next, and so would the columns of GeoArrow pages served by
    different workers, which then no longer concatenate.
    """
    removed = set().union(*excluded)
    return tuple(field for field in fields if field not in removed)


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
            The fields used to sort the queryset. Defaults to the model ordering, completed by the
            primary key so that pagination is stable.
    """

    id: str
    title: str
    description: str | None = None

    geometry_field: str | None
    fields: tuple[str, ...]
    readonly_fields: tuple[str, ...] = ()
    exclude: tuple[str, ...] = ()
    ordering: tuple = ()

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
                if not isinstance(field, (ManyToOneRel, ManyToManyRel)) and field.name != self.geometry_field
            ),
        )

        self.foreign_key_fields = {
            field.name: field.remote_field.model for field in model_fields if isinstance(field, ForeignKey)
        }

    def storage_crs(self) -> CRS | None:
        """The CRS the geometries are stored in, or None for a collection without geometry."""
        if self.srid is None:
            return None
        return CRS("OGC", CRS84_SRID) if self.srid == CRS84_SRID else CRS("EPSG", self.srid)

    def supported_crs(self) -> tuple[CRS, ...]:
        """
        Hook for specifying which CRS the collection can be queried in.
        """
        storage_crs = self.storage_crs()
        if storage_crs is None:
            return ()
        if storage_crs.srid == CRS84_SRID:
            return (storage_crs,)
        return (CRS("OGC", CRS84_SRID), storage_crs)

    def _geometry_in(self, crs: CRS):
        """The geometry field, reprojected when the crs is not the storage one."""
        return self.geometry_field if crs.srid == self.srid else Transform(self.geometry_field, crs.srid)

    @overload
    def query(self, request: HttpRequest, crs: CRS): ...

    @overload
    def query(self, request: HttpRequest, crs: CRS, bbox: BBox | None, bbox_crs: CRS): ...

    def query(
        self, request: HttpRequest, crs: CRS, bbox: BBox | None = None, bbox_crs: CRS | None = None
    ) -> QuerySet[M]:
        qs = self.get_queryset(request)
        qs = qs.only("pk", *self.get_fields(request))
        if geom_field := self.geometry_field:
            qs = qs.annotate(_oapif_geometry=AsWKB(self._geometry_in(crs)))
            if bbox is not None:
                assert bbox_crs is not None
                bbox_geom = GEOSPolygon.from_bbox((bbox.xmin, bbox.ymin, bbox.xmax, bbox.ymax))
                bbox_geom.srid = bbox_crs.srid
                bbox_expr = bbox_geom if bbox_geom.srid == self.srid else Transform(bbox_geom, self.srid)
                qs = qs.filter(**{f"{geom_field}__intersects": bbox_expr})
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

        The model ordering is kept, with the primary key appended as a tie breaker: without one,
        rows that compare equal can move between pages and be returned twice or not at all.
        """
        return self.ordering or (*self.opts.ordering, "pk")

    def get_fields(self, request, obj=None) -> tuple[str, ...]:
        """
        Hook for specifying fields.
        """
        return self.fields

    def get_exclude(self, request, obj=None) -> tuple[str, ...]:
        """
        Hook for specifying fields.
        """
        return self.exclude

    def get_readonly_fields(self, request, obj=None) -> tuple[str, ...]:
        """
        Hook for specifying custom readonly fields.
        """
        readonly_types = (GeneratedField, FileField)
        readonly_fields = {f.name for f in self.model._meta.get_fields() if isinstance(f, readonly_types)}
        return tuple(set(self.readonly_fields) | readonly_fields)

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
        # dim covers the usual GeometryField(dim=3); the suffix covers custom geom_type subclasses
        is_3d = geom_field.dim >= 3 or geom_field.geom_type.endswith(("Z", "ZM"))
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
        elif geom_field.geom_type.startswith("CIRCULARSTRING"):
            # a CircularString longer than JSON-FG allows is served in parts, and comes back that way
            GeometryType = Annotated[
                CircularString[CoordType] | CircularStringParts[CoordType], Field(discriminator="type")
            ]
        elif geom_field.geom_type.startswith("COMPOUNDCURVE"):
            GeometryType = CompoundCurve[CoordType]
        elif geom_field.geom_type.startswith("CURVEPOLYGON"):
            GeometryType = CurvePolygon[CoordType]
        elif geom_field.geom_type.startswith("MULTICURVE"):
            GeometryType = MultiCurve[CoordType]
        elif geom_field.geom_type.startswith("MULTISURFACE"):
            GeometryType = MultiSurface[CoordType]
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
        *,
        extra: ExtraValues = "forbid",
    ) -> type[Schema]:
        # ninja caches model schemas by model, name and fields, but not by config: were the name the
        # same for every extra behaviour, the output schema built by a GET would be handed to the next
        # POST, which would then silently drop unknown properties instead of rejecting them
        name = f"Properties{extra.capitalize()}"

        class Meta:
            model = self.model
            fields = properties_fields
            fields_optional = optional_fields

        # qualified as nested in the schema, so that pydantic does not take it for a field
        Meta.__qualname__ = f"{name}.Meta"
        body = {
            "__module__": __name__,
            "__qualname__": name,
            "model_config": ConfigDict(**model_config, extra=extra),
            "Meta": Meta,
        }
        # the JSON of pydantic writes times to the microsecond, and durations its own way: they are written
        # as Django does, whether ninja renders the features or the endpoints serialize them themselves. The
        # fields are not there to check yet: ninja adds them to a subclass of the one the body makes
        temporal = [
            field.name
            for field in self.model._meta.concrete_fields
            if isinstance(field, (DateTimeField, TimeField, DurationField))
            and (properties_fields == "__all__" or field.name in properties_fields)
        ]
        if temporal:
            serialize = field_serializer(*temporal, when_used="json-unless-none", check_fields=False)
            body["serialize_temporal"] = serialize(DjangoJSONEncoder().default)
        return new_class(name, (ModelSchema,), exec_body=lambda namespace: namespace.update(body))

    def get_feature_input_schema(self, request: HttpRequest) -> type[Feature]:
        fields = without(self.get_fields(request), self.get_exclude(request), self.get_readonly_fields(request))
        PropertiesSchema = self.get_properties_schema(fields)
        GeometrySchema = self.get_geometry_schema()
        return Feature[GeometrySchema, PropertiesSchema]

    def get_feature_patch_schema(self, request: HttpRequest) -> type[FeaturePatch]:
        fields = without(self.get_fields(request), self.get_exclude(request), self.get_readonly_fields(request))
        PropertiesSchema = self.get_properties_schema(fields)
        GeometrySchema = self.get_geometry_schema()
        return FeaturePatch[GeometrySchema, PatchSchema[PropertiesSchema]]

    def get_feature_properties_schema(self, request: HttpRequest) -> type[Schema]:
        fields = without(self.get_fields(request), self.get_exclude(request))
        # extra="ignore" is required for the serialization to go through ninja DjangoGetter
        return self.get_properties_schema(fields, extra="ignore")

    def get_feature_output_schema(self, request: HttpRequest) -> type[Feature]:
        PropertiesSchema = self.get_feature_properties_schema(request)
        GeometrySchema = self.get_geometry_schema()
        return Feature[GeometrySchema, PropertiesSchema]

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
            geom_type = geom_type.removesuffix("m")
            geom_type = geom_type.removesuffix("z")
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

    def queryset_to_featurecollection(
        self,
        request: HttpRequest,
        qs: QuerySet,
        *,
        number_matched: int | None = None,
        links: list[OAPIFLink] | None = None,
    ) -> FeatureCollection:
        """
        Convert a queryset (as produced by `query()`) to a FeatureCollection. `number_matched` defaults
        to the number of features returned, for a queryset that is not a page of a larger one.
        """
        FeatureSchema = self.get_feature_output_schema(request)
        FeatureCollectionSchema = FeatureCollection[FeatureSchema]
        features = []
        # the boxes of the geometries, taken as they are read, so that the collection one takes no extra
        # query, nor reprojecting them all again
        boxes = []
        for obj in qs:
            features.append(self._model_to_feature(FeatureSchema, obj, boxes))
        bbox = None
        if boxes:
            xmins, ymins, xmaxs, ymaxs = zip(*boxes)
            bbox = (min(xmins), min(ymins), max(xmaxs), max(ymaxs))
        return FeatureCollectionSchema.model_construct(
            type="FeatureCollection",
            features=features,
            bbox=bbox,
            numberReturned=len(features),
            numberMatched=len(features) if number_matched is None else number_matched,
            links=links or [],
        )

    def get_arrow_properties_schema(self, properties_schema: type[Schema], properties: list[dict]) -> "pa.Schema":
        """Arrow schema of the feature properties, so that every page of a collection shares one."""
        fields = []
        for name, field in properties_schema.model_fields.items():
            annotation = field.annotation
            if optional := [arg for arg in get_args(annotation) if arg is not NoneType]:
                annotation = optional[0] if len(optional) == 1 else None
            arrow_type = ARROW_TYPES.get(annotation)
            if arrow_type is None:
                # not a type we know: let pyarrow work it out from the values, as it did before
                arrow_type = pa.array([row[name] for row in properties]).type if properties else pa.null()
            fields.append(pa.field(name, arrow_type))
        return pa.schema(fields)

    def queryset_to_arrow_stream(self, request: HttpRequest, qs: QuerySet, crs: CRS):
        """Convert a queryset (as produced by `query()`) to a pyarrow Table with a GeoArrow-WKB geometry column."""

        PropertiesSchema = self.get_feature_properties_schema(request)
        rows = list(qs)
        properties = [
            {
                name: str(value) if isinstance(value, UUID) else value
                for name, value in PropertiesSchema.from_orm(row).dict().items()
            }
            for row in rows
        ]
        table = pa.Table.from_pylist(properties, schema=self.get_arrow_properties_schema(PropertiesSchema, properties))

        if self.geometry_field:
            # the type has to be spelled out: a page whose geometries are all null would infer as null
            geometries = pa.array(
                [bytes(wkb) if (wkb := getattr(row, "_oapif_geometry", None)) else None for row in rows],
                type=pa.binary(),
            )
            table = table.append_column(
                "geometry",
                # query() has already reprojected the geometries, so tag the crs that was asked for
                ga.with_crs(ga.as_wkb(geometries), crs.auth_code()),
            )

        stream = pa.BufferOutputStream()
        with pa.ipc.new_stream(stream, table.schema) as writer:
            writer.write_table(table)
        return stream

    def model_to_feature(self, request: HttpRequest, obj: M) -> Feature:
        schema = self.get_feature_output_schema(request)
        return self._model_to_feature(schema, obj)

    def _model_to_feature(self, schema: type[Feature], obj: M, bounds: list | None = None) -> Feature:
        geometry_wkb = getattr(obj, "_oapif_geometry", None)
        return schema(
            type="Feature",
            id=str(obj.pk),
            geometry=jsonfg.loads(bytes(geometry_wkb), bounds) if geometry_wkb else None,
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
            errors = e.errors()
            for error in errors:
                error["loc"] = ("body", "feature", *error["loc"])
                # an exception raised by a validator is left in the context, where it would not serialize:
                # ninja turns it into its message for its own errors, and so must this
                if isinstance(error.get("ctx", {}).get("error"), Exception):
                    error["ctx"]["error"] = str(error["ctx"]["error"])
            raise ValidationError(errors)  # type: ignore


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
