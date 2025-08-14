from typing import Annotated, Any, Generic, Literal, Optional, TypeAlias, TypeVar, Union

from ninja import Field, Schema

from django_oapif.schema import OAPIFLink

Coordinate2D: TypeAlias = tuple[float, float]
Coordinate3D: TypeAlias = tuple[float, float, float]

# Define a TypeVar constrained to only the two aliases
Coordinate = TypeVar("Coordinate", Coordinate2D, Coordinate3D)


class GeometryBase(Schema, Generic[Coordinate]):
    bbox: Optional[tuple[float, float, float, float]] = None


class Point(GeometryBase):
    type: Literal["Point"]
    coordinates: Coordinate


class LineString(GeometryBase):
    type: Literal["LineString"]
    # coordinates: Annotated[List[Coordinate], Field(min_length=2)]
    coordinates: Union[
        Annotated[list[Coordinate], Field(min_length=0, max_length=0)],
        Annotated[list[Coordinate], Field(min_length=2)],
    ]


class Polygon(GeometryBase):
    type: Literal["Polygon"]
    coordinates: list[Annotated[list[Coordinate], Field(min_length=4)]]


class MultiPoint(GeometryBase):
    type: Literal["MultiPoint"]
    coordinates: list[Coordinate]


class MultiLineString(GeometryBase):
    type: Literal["MultiLineString"]
    coordinates: list[list[Coordinate]]


class MultiPolygon(GeometryBase):
    type: Literal["MultiPolygon"]
    coordinates: list[list[list[Coordinate]]]


class GeometryCollection(GeometryBase):
    type: Literal["GeometryCollection"]
    geometries: list["Geometry"]


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

    @classmethod
    def from_orm(cls, obj: Any):
        return cls(
            type="Feature",
            id=str(obj.pk),
            geometry=getattr(obj, "_oapif_geometry", None),
            properties=obj,
        )


GenericFeature = TypeVar("GenericFeature", bound=Geometry)


class FeatureCollection(Schema, Generic[GenericFeature]):
    type: Literal["FeatureCollection"]
    features: list[GenericFeature]
    bbox: Optional[tuple[float, float, float, float]]
    links: list[OAPIFLink]
    numberReturned: int
    numberMatched: int
