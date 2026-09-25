from typing import Annotated, Any, Literal

from ninja import Field, Schema
from pydantic import AfterValidator, ConfigDict
from pydantic_core import PydanticCustomError

from django_oapif.schema import OAPIFLink

type Coordinate2D = tuple[float, float]
type Coordinate3D = tuple[float, float, float]
type Coordinate = Coordinate2D | Coordinate3D


class GeometryBase(Schema):
    # validate_assignment is required to skip passing values through DjangoGetter
    # which causes a bug on null geometries
    model_config = ConfigDict(from_attributes=True, validate_assignment=True)


class Point[C: Coordinate](GeometryBase):
    type: Literal["Point"]
    coordinates: C


class LineString[C: Coordinate](GeometryBase):
    type: Literal["LineString"]
    coordinates: Annotated[list[C], Field(min_length=0, max_length=0)] | Annotated[list[C], Field(min_length=2)]


class Polygon[C: Coordinate](GeometryBase):
    type: Literal["Polygon"]
    coordinates: list[Annotated[list[C], Field(min_length=4)]]


class MultiPoint[C: Coordinate](GeometryBase):
    type: Literal["MultiPoint"]
    coordinates: list[C]


class MultiLineString[C: Coordinate](GeometryBase):
    type: Literal["MultiLineString"]
    coordinates: list[Annotated[list[C], Field(min_length=0, max_length=0)] | Annotated[list[C], Field(min_length=2)]]


class MultiPolygon[C: Coordinate](GeometryBase):
    type: Literal["MultiPolygon"]
    coordinates: list[list[Annotated[list[C], Field(min_length=4)]]]


def arc_points[T: list](coordinates: T) -> T:
    """A CircularString is a sequence of arcs, each defined by a start, a middle and an end point."""
    if coordinates and (len(coordinates) < 3 or len(coordinates) % 2 == 0):
        # a PydanticCustomError, as a ValueError would end up in the error context and fail to serialize
        raise PydanticCustomError(
            "circularstring_points", "a CircularString must be empty or have an odd number of at least 3 points"
        )
    return coordinates


# JSON Schema cannot tell an odd length, so JSON-FG lists the lengths it allows, up to 11 points.
# The published schema says as much, while the validator also takes the longer arcs PostGIS stores.
MAX_ARC_POINTS = 11
ARC_LENGTHS = {"oneOf": [{"maxItems": 0}] + [{"minItems": n, "maxItems": n} for n in range(3, MAX_ARC_POINTS + 1, 2)]}


class CircularString[C: Coordinate](GeometryBase):
    type: Literal["CircularString"]
    coordinates: Annotated[list[C], AfterValidator(arc_points), Field(json_schema_extra=ARC_LENGTHS)]


class CompoundCurve[C: Coordinate](GeometryBase):
    type: Literal["CompoundCurve"]
    geometries: list[LineString[C] | CircularString[C]]


def joined_arcs[T: list](parts: T) -> T:
    """The parts of a CircularString must follow one another, to be joined back without changing the curve."""
    for previous, part in zip(parts, parts[1:]):
        if not previous.coordinates or not part.coordinates or previous.coordinates[-1] != part.coordinates[0]:
            raise PydanticCustomError("circularstring_parts", "each part must start on the last point of the previous")
    return parts


class CircularStringParts[C: Coordinate](GeometryBase):
    """A CircularString longer than JSON-FG allows, served as the CompoundCurve of its arcs."""

    type: Literal["CompoundCurve"]
    geometries: Annotated[list[CircularString[C]], Field(min_length=1), AfterValidator(joined_arcs)]

    def circular_string(self) -> dict:
        coordinates = self.geometries[0].coordinates + [c for part in self.geometries[1:] for c in part.coordinates[1:]]
        return {"type": "CircularString", "coordinates": coordinates}


class CurvePolygon[C: Coordinate](GeometryBase):
    type: Literal["CurvePolygon"]
    geometries: list[LineString[C] | CircularString[C] | CompoundCurve[C]]


class MultiCurve[C: Coordinate](GeometryBase):
    type: Literal["MultiCurve"]
    geometries: list[LineString[C] | CircularString[C] | CompoundCurve[C]]


class MultiSurface[C: Coordinate](GeometryBase):
    type: Literal["MultiSurface"]
    geometries: list[Polygon[C] | CurvePolygon[C]]


class GeometryCollection[C: Coordinate](GeometryBase):
    type: Literal["GeometryCollection"]
    geometries: list["Geometry[C]"]


type Geometry[C: Coordinate] = Annotated[
    Point[C]
    | MultiPoint[C]
    | LineString[C]
    | MultiLineString[C]
    | Polygon[C]
    | MultiPolygon[C]
    | CircularString[C]
    | CompoundCurve[C]
    | CurvePolygon[C]
    | MultiCurve[C]
    | MultiSurface[C]
    | GeometryCollection[C],
    Field(discriminator="type"),
]

GeometryCollection.model_rebuild()


class Feature[G: Geometry | None, P: Schema](Schema):
    type: Literal["Feature"]
    id: int | str | None = None
    geometry: G
    properties: P
    # JSON-FG members of a feature written: the geometry GeoJSON cannot carry, "geometry" being then its
    # fallback, and the CRS of its coordinates. They are not served.
    place: G | None = Field(None, exclude=True)
    coordRefSys: Any = Field(None, exclude=True)


class FeaturePatch[G: Geometry | None, P: Schema](Schema):
    type: Literal["Feature"] = "Feature"
    id: int | str | None = None
    geometry: G | None = None
    properties: P | None = None
    place: G | None = Field(None, exclude=True)
    coordRefSys: Any = Field(None, exclude=True)


class FeatureCollection[F: Feature](Schema):
    type: Literal["FeatureCollection"]
    features: list[F]
    bbox: tuple[float, float, float, float] | None
    links: list[OAPIFLink]
    numberReturned: int
    numberMatched: int


GenericGeometry = Geometry[Coordinate] | None
GenericFeature = Feature[GenericGeometry, Any]
GenericFeaturePatch = FeaturePatch[GenericGeometry, Any]
GenericFeatureCollection = FeatureCollection[GenericFeature]
