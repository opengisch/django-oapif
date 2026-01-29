from typing import Annotated, Any, Literal

from ninja import Field, Schema

from django_oapif.schema import OAPIFLink

type Coordinate2D = tuple[float, float]
type Coordinate3D = tuple[float, float, float]
type Coordinate = Coordinate2D | Coordinate3D


class GeometryBase(Schema):
    bbox: tuple[float, float, float, float] | None = None


class Point[C: Coordinate](GeometryBase):
    type: Literal["Point"]
    coordinates: C


class LineString[C: Coordinate](GeometryBase):
    type: Literal["LineString"]
    coordinates: (
        Annotated[list[Coordinate], Field(min_length=0, max_length=0)]
        | Annotated[list[Coordinate], Field(min_length=2)]
    )


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
    | GeometryCollection[C],
    Field(discriminator="type"),
]

GeometryCollection.model_rebuild()


class FeatureWithoutId[G: Geometry | None, P: Schema](Schema):
    type: Literal["Feature"]
    properties: P
    geometry: G


class Feature[G: Geometry | None, P: Schema](Schema):
    type: Literal["Feature"]
    id: int | str
    properties: P
    geometry: G

    @classmethod
    def from_orm(cls, obj: Any):
        return cls(
            type="Feature",
            id=str(obj.pk),
            geometry=getattr(obj, "_oapif_geometry", None),  # type: ignore
            properties=obj,
        )


class FeatureCollection[F: Feature](Schema):
    type: Literal["FeatureCollection"]
    features: list[F]
    bbox: tuple[float, float, float, float] | None
    links: list[OAPIFLink]
    numberReturned: int
    numberMatched: int
