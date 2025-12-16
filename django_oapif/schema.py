from ninja import Schema


class OAPIFBaseSchema(Schema):
    def model_dump(self, *, exclude_none=True, **kwargs):
        return super().model_dump(exclude_none=exclude_none, **kwargs)


class OAPIFLink(OAPIFBaseSchema):
    href: str
    rel: str
    type: str
    title: str


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
    title: str | None = None
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
