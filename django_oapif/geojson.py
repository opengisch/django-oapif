
from typing import (
    Annotated,
    Generic,
    List,
    Literal,
    Optional,
    Tuple,
    TypeAlias,
    TypeVar,
    Union,
)

from ninja import Field, Schema

from django_oapif.schema import OAPIFLink

Coordinate2D: TypeAlias = Tuple[float, float]
Coordinate3D: TypeAlias = Tuple[float, float, float]

# Define a TypeVar constrained to only the two aliases
Coordinate = TypeVar("Coordinate", Coordinate2D, Coordinate3D)

class GeometryBase(Schema, Generic[Coordinate]):
    bbox: Optional[Tuple[float, float, float, float]] = None

class Point(GeometryBase):
    type: Literal["Point"]
    coordinates: Coordinate

class LineString(GeometryBase):
    type: Literal["LineString"]
    # coordinates: Annotated[List[Coordinate], Field(min_length=2)]
    coordinates: Union[
        Annotated[List[Coordinate], Field(min_length=0, max_length=0)],
        Annotated[List[Coordinate], Field(min_length=2)],
    ]

class Polygon(GeometryBase):
    type: Literal["Polygon"]
    coordinates: List[Annotated[List[Coordinate], Field(min_length=4)]]

class MultiPoint(GeometryBase):
    type: Literal["MultiPoint"]
    coordinates: List[Coordinate]

class MultiLineString(GeometryBase):
    type: Literal["MultiLineString"]
    coordinates: List[List[Coordinate]]

class MultiPolygon(GeometryBase):
    type: Literal["MultiPolygon"]
    coordinates: List[List[Coordinate]]

class GeometryCollection(GeometryBase):
    type: Literal["GeometryCollection"]
    geometries: List["Geometry"]

Geometry: TypeAlias = Annotated[
    Union[
        Point,
        MultiPoint,
        LineString,
        MultiLineString,
        Polygon,
        MultiPolygon,
        GeometryCollection,
    ],
    Field(discriminator="type"),
]

GeometryCollection.model_rebuild()


FeatureProperties = TypeVar("FeatureProperties", bound=Schema)
FeatureGeometry = TypeVar("FeatureGeometry", bound=Union[Geometry, None])


class NewFeature(Schema, Generic[FeatureGeometry, FeatureProperties]):
    type: Literal["Feature"]
    properties: FeatureProperties
    geometry: FeatureGeometry

class Feature(Schema, Generic[FeatureGeometry, FeatureProperties]):
    type: Literal["Feature"]
    id: int | str
    properties: FeatureProperties
    geometry: FeatureGeometry

GenericFeature = TypeVar("GenericFeature", bound=Geometry)

class FeatureCollection(Schema, Generic[GenericFeature]):
    type: Literal["FeatureCollection"]
    features: List[GenericFeature]
    bbox: Optional[Tuple[float, float, float, float]]
    links: list[OAPIFLink]
    numberReturned: int
    numberMatched: int
