from ninja import Schema
from pydantic import model_serializer


class OAPIFBaseSchema(Schema):
    def model_dump(self, *, exclude_none=True, **kwargs):
        return super().model_dump(exclude_none=exclude_none, **kwargs)


class OAPIFLink(OAPIFBaseSchema):
    href: str
    rel: str
    type: str
    title: str
    # the profiles of the resource linked, which Features 1.1 adds to tell JSON-FG from GeoJSON
    profile: list[str] | None = None

    @model_serializer(mode="wrap")
    def leave_out_no_profile(self, serialize):
        # the feature collections are serialized as they are, where None would be written as null
        link = serialize(self)
        if self.profile is None:
            link.pop("profile", None)
        return link


class OAPIFRoot(OAPIFBaseSchema):
    title: str
    description: str
    links: list[OAPIFLink]


class OAPIFSpatialExtent(OAPIFBaseSchema):
    bbox: list[tuple[float, float, float, float]]
    crs: str


class OAPIFExtent(OAPIFBaseSchema):
    spatial: OAPIFSpatialExtent


class OAPIFCollection(OAPIFBaseSchema):
    id: str
    title: str
    description: str | None = None
    links: list[OAPIFLink]
    crs: list[str] | None = None
    storageCrs: str | None = None
    extent: OAPIFExtent | None = None
    itemType: str


class OAPIFCollections(OAPIFBaseSchema):
    links: list[OAPIFLink]
    collections: list[OAPIFCollection]


class OAPIFConformance(OAPIFBaseSchema):
    conformsTo: list[str]
