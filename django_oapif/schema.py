
from typing import Optional

from ninja import Schema


class OAPIFBaseSchema(Schema):

    def model_dump(self, *, exclude_none=True, **kwargs):
        return super().model_dump(exclude_none=exclude_none, **kwargs)


class OAPIFLink(OAPIFBaseSchema):
    href: str
    rel: Optional[str] = None
    type: Optional[str] = None
    hreflang: Optional[str] = None
    title: Optional[str] = None
    length: Optional[int] = None


class OAPIFRoot(OAPIFBaseSchema):
    title: Optional[str] = None
    description: Optional[str] = None
    links: list[OAPIFLink]


class OAPIFSpatialExtent(OAPIFBaseSchema):
    bbox: list[tuple[float, float, float, float]]
    crs: str


class OAPIFExtent(OAPIFBaseSchema):
    spatial: OAPIFSpatialExtent
    
class OAPIFCollection(OAPIFBaseSchema):
    id: str
    title: Optional[str] = None
    description: Optional[str] = None
    links: list[OAPIFLink]
    crs: Optional[list[str]] = None
    storageCrs: Optional[str] = None
    extent: Optional[OAPIFExtent] = None
    itemType: str

class OAPIFCollections(OAPIFBaseSchema):
    links: list[OAPIFLink]
    collections: list[OAPIFCollection]

class OAPIFConformance(OAPIFBaseSchema):
    conformsTo: list[str]
