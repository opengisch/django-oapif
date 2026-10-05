# Geometries

## The geometry field

A collection takes the geometry of its features from the geometry field of its model. A model with several
geometry fields has to name the one to serve in [`geometry_field`](../usage/collections.md#options). A model
without one is served as a collection of features without geometry, whose `geometry` is `null`, like the
features whose geometry field is null.

## Geometry types

Geometries are written as in GeoJSON, but for curves, which GeoJSON does not have: they are written as in
[JSON-FG](https://docs.ogc.org/is/21-045r1/21-045r1.html), and served in JSON-FG or linearized, see
[curves](#curves).

| Field                                                          | Geometry                                        |
|----------------------------------------------------------------|-------------------------------------------------|
| `PointField`                                                   | `Point`                                         |
| `LineStringField`                                              | `LineString`                                    |
| `PolygonField`                                                 | `Polygon`                                       |
| `MultiPointField`, `MultiLineStringField`, `MultiPolygonField` | `MultiPoint`, `MultiLineString`, `MultiPolygon` |
| `GeometryCollectionField`                                      | `GeometryCollection`                            |
| `GeometryField`                                                | any of them, curves included                    |

GeoJSON and JSON-FG have no polyhedral surfaces, TINs or triangles, which a `GeometryField` column may hold:
they are served as MultiPolygons, MultiPolygons and Polygons, as GDAL does.

Writes take the geometry type of the field only, any type for a `GeometryField`, and reject another with a
`422 Unprocessable Content`, as they reject invalid geometries, such as polygons whose rings are not closed.

## Z coordinates

A field declared with `dim=3` serves and takes coordinates with a z, any other field coordinates without. A
write whose coordinates have the other dimension is rejected with a `422 Unprocessable Content`.

```python
class Pipe(models.Model):
    geom = models.LineStringField(srid=2056, dim=3)
```

## Curves

GeoDjango has no field for curves: declare a `GeometryField` of the type of the column, `CIRCULARSTRING`,
`COMPOUNDCURVE`, `CURVEPOLYGON`, `MULTICURVE` or `MULTISURFACE`:

```python
from django.contrib.gis.db import models


class CircularStringField(models.GeometryField):
    geom_type = "CIRCULARSTRING"


class Arc(models.Model):
    geom = CircularStringField(srid=2056)
```

GeoJSON cannot carry curves. A client asks for them in one of the two forms that can:

- as they are, in [JSON-FG](#json-fg), with `profile=jsonfg`;
- in GeoJSON, [linearized](#linearized-curves), with `linearize=true`.

A request for them in GeoJSON is refused with a `406 Not Acceptable`, rather than served features without
geometry, or with one that is not theirs. Its body links the two:

```json
{
  "detail": "GeoJSON cannot carry curves: ask for them in JSON-FG, with profile=jsonfg, or linearized, with linearize=true",
  "links": [
    {"rel": "alternate", "type": "application/geo+json", "profile": ["http://www.opengis.net/def/profile/ogc/0/jsonfg"], "href": "https://example.com/oapif/collections/my_app.arc/items?profile=jsonfg", "title": "This document as JSON-FG"},
    {"rel": "alternate", "type": "application/geo+json", "href": "https://example.com/oapif/collections/my_app.arc/items?linearize=true", "title": "This document as GeoJSON, the curves linearized"}
  ]
}
```

The items of a curve column are refused in GeoJSON on every page, even one without a feature. A
`GeometryField` column may hold curves too: its pages that have one are refused, and the others served as
GeoJSON. The HTML pages draw the curves, and [GeoArrow](../formats/geoarrow.md) has them as they are, in its WKB.

What a request for items gets, `/items` or `/items/{featureId}`:

| Request                                       | Curve column                    | `GeometryField` column, with a curve | Column without curves  |
|-----------------------------------------------|---------------------------------|--------------------------------------|------------------------|
| no parameter, or `profile=rfc7946`            | `406 Not Acceptable`            | `406 Not Acceptable`                 | GeoJSON                |
| `profile=jsonfg`                              | JSON-FG, the curves in `place`  | JSON-FG, the curves in `place`       | JSON-FG                |
| `linearize=true`                              | GeoJSON, the curves linearized  | GeoJSON, the curves linearized       | GeoJSON, as without it |
| `profile=jsonfg&linearize=true`               | `400 Bad Request`               | `400 Bad Request`                    | `400 Bad Request`      |
| `f=html`, or a browser                        | a page, the curves on its map   | a page, the curves on its map        | a page                 |
| `Accept: application/vnd.apache.arrow.stream` | GeoArrow, the curves in its WKB | GeoArrow, the curves in its WKB      | GeoArrow               |

The `profile` parameter of the media type in the `Accept` header, `application/geo+json; profile="…"`, asks as
the query parameter does, which chooses over it.

A JSON-FG CircularString has 5 arcs at most, 11 points. A longer one is served as the CompoundCurve of its
arcs, 5 at a time, each part starting on the last point of the previous one, which draws the same curve. A
CircularString field takes it back in this form too, and stores it as a single CircularString again.

Curves are read on any stack, but writing them takes GEOS 3.13 or newer, and a Django whose GEOS bindings
support curves, which no Django release does yet. Otherwise, writing a curve is answered with a
`501 Not Implemented`.

## JSON-FG

JSON-FG gives the curves in `place`, and `null` in `geometry`, in a document that declares its conformance
classes in `conformsTo`, and the CRS of `place`, the one of the response, in `coordRefSys`:

```json
{
  "type": "FeatureCollection",
  "conformsTo": [
    "http://www.opengis.net/spec/json-fg-1/1.0/conf/core",
    "http://www.opengis.net/spec/json-fg-1/1.0/conf/circular-arcs"
  ],
  "coordRefSys": "http://www.opengis.net/def/crs/EPSG/0/2056",
  "features": [
    {
      "type": "Feature",
      "id": "42",
      "geometry": null,
      "properties": {"name": "Arc"},
      "place": {
        "type": "CircularString",
        "coordinates": [[2508500.0, 1152000.0], [2508510.0, 1152010.0], [2508520.0, 1152000.0]]
      }
    }
  ],
  ...
}
```

The `CompoundCurve`, `CurvePolygon`, `MultiCurve` and `MultiSurface` geometries hold their parts in
`geometries`. A JSON-FG reader, such as GDAL since its 3.12, reads the curves as they are.

A request asks for JSON-FG with the `profile` query parameter of OGC API - Features - Part 5, by the name of
the profile, `jsonfg`, or by its URI, `http://www.opengis.net/def/profile/ogc/0/jsonfg`, or with the `profile`
parameter of the media type it accepts:

```bash
curl "https://example.com/oapif/collections/my_app.arc/items?profile=jsonfg"
curl -H 'Accept: application/geo+json; profile="http://www.opengis.net/def/profile/ogc/0/jsonfg"' \
  "https://example.com/oapif/collections/my_app.arc/items"
```

The query parameter chooses over the header. `profile=rfc7946` asks for GeoJSON, the default, and a profile the
API does not know is ignored, rather than failing the request. The response has the media type
`application/geo+json` in either profile, and links its profile in its `Link` header:

```http
Link: <http://www.opengis.net/def/profile/ogc/0/jsonfg>; rel="profile"
```

The OGC register writes the URIs with `OGC`, and QGIS only knows them with `ogc`: the API takes both, and gives
those of QGIS.

Any collection can be asked for in JSON-FG, and not only curves. JSON-FG gives `geometry` in CRS84: in another
CRS, the geometries are all in `place`.

A collection with a geometry links its items in JSON-FG, before its link to GeoJSON, with the `profile` of the
links of Features 1.1:

```json
{"rel": "items", "type": "application/geo+json", "profile": ["http://www.opengis.net/def/profile/ogc/0/jsonfg"], "href": "https://example.com/oapif/collections/my_app.arc/items?profile=jsonfg", "title": "Collection items as JSON-FG"}
```

The links of a page of items to the other pages have the profile it was asked for, and are in its `Link` header
as well, with the number of features in `OGC-NumberMatched`: QGIS reads them there in JSON-FG.

## Linearized curves

`linearize=true` asks for the curves in GeoJSON, linearized: made of segments by PostGIS, in the storage CRS,
where the arcs are drawn, and then reprojected to the CRS asked for. The features are plain GeoJSON, without
`place`, whose `geometry` is the linearization of their curve:

| Curve                              | Linearization     |
|------------------------------------|-------------------|
| `CircularString`, `CompoundCurve`  | `LineString`      |
| `CurvePolygon`                     | `Polygon`         |
| `MultiCurve`                       | `MultiLineString` |
| `MultiSurface`                     | `MultiPolygon`    |

```bash
curl "https://example.com/oapif/collections/my_app.arc/items?linearize=true&crs=http://www.opengis.net/def/crs/EPSG/0/2056"
```

The linearization is an approximation, which the API gives only when asked for. The parameter:

- takes `true` or `false`, the default;
- changes nothing of the collections without curves, whose features are served as they are;
- is refused with a `400 Bad Request` together with `profile=jsonfg`, which has the curves as they are;
- is ignored by GeoArrow and the HTML pages, which have the curves as they are;
- is kept by the links to the other pages, and gives a page the extent of its lines as `bbox`.

An empty geometry has none once linearized, as PostGIS fails on some empty curves.

PostGIS draws a quarter of a circle with 32 segments. [`linearization_tolerance`](../usage/collections.md#options)
sets instead the largest distance between an arc and its segments, in the unit of the storage CRS:

```python
@oapif.register(Parcel)
class ParcelCollection(OapifCollection):
    # a millimetre, in EPSG:2056
    linearization_tolerance = 0.001
```

The linearization is symmetric: an arc two polygons share, like the boundary of two parcels, is made of the same
points in both, whichever way round they run along it.

## Curves in QGIS

QGIS knows the profiles of JSON-FG since its 4.2: it reads JSON-FG through the link of the collection, when the
layer, or its connection, asks for the `application/fg+json` format (`outputformat=application/fg+json` in the
URI of a layer). It reads the curves with GDAL, which reads those of JSON-FG since its 3.12. QGIS 3 knows no
profiles, but adds the query of the URL of the connection, `https://example.com/oapif/?linearize=true`, to every
request of the connection.

| QGIS, with GDAL              | Asking for                              | A layer of curves                              |
|------------------------------|-----------------------------------------|------------------------------------------------|
| any                          | nothing                                 | fails to load, GeoJSON being refused           |
| any                          | `?linearize=true` in the connection URL | the curves linearized, in the CRS of the layer |
| 4.2, with GDAL 3.12 or newer | the `application/fg+json` format        | the curves                                     |
| 4.2, with an older GDAL      | the `application/fg+json` format        | features without geometry                      |

With `?linearize=true`, the other layers of the connection are served as they are.

A linearized feature edited in QGIS is written back linearized, which a curve column refuses: see
[JSON-FG features](#json-fg-features).

## JSON-FG features

A JSON-FG feature gives the geometries that GeoJSON cannot carry in `place`, and a GeoJSON approximation of
them, or `null`, in `geometry`. A `POST`, `PUT` or `PATCH` with a `place` stores it, and ignores the
`geometry`. Its `coordRefSys`, if any, has to be the CRS of the `Content-Crs` header, in which the coordinates
are read, or the write is rejected with a `400 Bad Request`:

```http
POST /oapif/collections/my_app.arc/items
Content-Type: application/json
Content-Crs: <http://www.opengis.net/def/crs/EPSG/0/2056>
```

```json
{
  "type": "Feature",
  "conformsTo": [
    "http://www.opengis.net/spec/json-fg-1/1.0/conf/core",
    "http://www.opengis.net/spec/json-fg-1/1.0/conf/circular-arcs"
  ],
  "coordRefSys": "http://www.opengis.net/def/crs/EPSG/0/2056",
  "place": {
    "type": "CircularString",
    "coordinates": [[2508500.0, 1152000.0], [2508510.0, 1152010.0], [2508520.0, 1152000.0]]
  },
  "geometry": {
    "type": "LineString",
    "coordinates": [[2508500.0, 1152000.0], [2508510.0, 1152010.0], [2508520.0, 1152000.0]]
  },
  "properties": {}
}
```

The feature written is returned in JSON-FG for a curve. A feature served in JSON-FG can be written back as it is,
with the `Content-Crs` of its `coordRefSys`. A curve column refuses a GeoJSON geometry without `place`, such as
a linearized curve, with a `422 Unprocessable Content` saying to send the curve in `place`.
