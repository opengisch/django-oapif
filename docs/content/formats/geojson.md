# GeoJSON

Features are served as [GeoJSON](https://datatracker.ietf.org/doc/html/rfc7946), with the media type
`application/geo+json`, and the members that
[OGC API - Features](https://docs.ogc.org/is/17-069r4/17-069r4.html) adds to it. Their geometries are those of
GeoJSON. Curves, which GeoJSON does not have, are refused, and served in
[JSON-FG](../fields/geometries.md#json-fg), with the same media type, or
[linearized](../fields/geometries.md#linearized-curves), when a client asks for either.

## Feature collections

`/collections/{collectionId}/items` returns a page of the features of a collection:

```json
{
  "type": "FeatureCollection",
  "features": [...],
  "bbox": [7.43, 46.94, 7.45, 46.96],
  "links": [
    {"rel": "self", "type": "application/geo+json", "href": "https://example.com/oapif/collections/my_app.building/items?offset=100", "title": "items (self)"},
    {"rel": "prev", "type": "application/geo+json", "href": "https://example.com/oapif/collections/my_app.building/items", "title": "items (prev)"},
    {"rel": "next", "type": "application/geo+json", "href": "https://example.com/oapif/collections/my_app.building/items?offset=200", "title": "items (next)"}
  ],
  "numberReturned": 100,
  "numberMatched": 1234
}
```

- `bbox` is the extent of the geometries of the page, in the CRS of the response, or `null` without any.
- `links` has the `prev` and `next` pages, when there are.
- `numberReturned` is the number of features of the page, and `numberMatched` the number of features that
  match the query, across all pages.

The `limit` parameter sets the number of features of a page, 100 by default, and `offset` the number of
features before it. `bbox` restricts the features to those that intersect a box, `xmin,ymin,xmax,ymax`, in the
CRS given by `bbox-crs`, and `crs` asks for the features in another [CRS](../usage/crs.md). `profile=jsonfg`
asks for them in [JSON-FG](../fields/geometries.md#json-fg), and `linearize=true` for their curves
[linearized](../fields/geometries.md#linearized-curves).

The links of the page are in its `Link` header as well, with the number of features that match the query in
`OGC-NumberMatched`, as a client of JSON-FG such as QGIS reads them there.

## Features

`/collections/{collectionId}/items/{featureId}` returns a single feature:

```json
{
  "type": "Feature",
  "id": "42",
  "geometry": {"type": "Point", "coordinates": [7.44, 46.95]},
  "properties": {"id": 42, "name": "Federal Palace"}
}
```

The `id` of a feature is its primary key, as a string. Its `geometry` and `properties` are described in
[fields](../fields/index.md).

Both responses give the CRS of their coordinates in a `Content-Crs` header, and their GeoJSON profile in a
`Link` header, with the `profile` relation. Both take `profile` and `linearize` as well.

## Writing features

The collections are writable, as defined by
[OGC API - Features - Part 4](https://docs.ogc.org/DRAFTS/20-002r1.html), for the users allowed to by their
[permissions](../usage/permissions.md):

| Request                                                  | Effect                                                                           |
|----------------------------------------------------------|----------------------------------------------------------------------------------|
| `POST /collections/{collectionId}/items`                 | Creates a feature, and returns it with a `201 Created` and its `Location`.       |
| `PUT /collections/{collectionId}/items/{featureId}`      | Replaces a feature, and returns it.                                              |
| `PATCH /collections/{collectionId}/items/{featureId}`    | Changes the geometry or the properties that it is sent, and returns the feature. |
| `DELETE /collections/{collectionId}/items/{featureId}`   | Deletes a feature.                                                               |

A write that leaves the feature out of the rows of [`get_queryset()`](../usage/collections.md#hooks), such as a
feature moved out of the area of the user, is saved, and answered without it: a `POST` with a `201 Created` and
its `Location` only, a `PUT` or `PATCH` with a `204 No Content`.

The body of a `POST`, `PUT` or `PATCH` is a GeoJSON feature, whose coordinates are in the CRS of the
`Content-Crs` header, CRS84 by default. The feature returned is in CRS84, and in JSON-FG for a curve:

```bash
curl -X POST "https://example.com/oapif/collections/my_app.building/items" \
  -u editor \
  -H "Content-Type: application/json" \
  -H "Content-Crs: <http://www.opengis.net/def/crs/EPSG/0/2056>" \
  -d '{"type": "Feature", "geometry": {"type": "Point", "coordinates": [2600000, 1200000]}, "properties": {"name": "Federal Palace"}}'
```

What properties a write takes, and which it rejects, is described in
[writing properties](../fields/index.md#writing-properties), and how to write curves in
[JSON-FG features](../fields/geometries.md#json-fg-features).
