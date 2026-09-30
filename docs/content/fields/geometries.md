# Geometries

## The geometry field

A collection takes the geometry of its features from the geometry field of its model. A model with several
geometry fields has to name the one to serve in [`geometry_field`](../usage/collections.md#options). A model
without one is served as a collection of features without geometry, whose `geometry` is `null`, like the
features whose geometry field is null.

## Geometry types

Geometries are written as in GeoJSON, but for curves, which GeoJSON does not have: they are written as in
[JSON-FG](https://docs.ogc.org/is/21-045r1/21-045r1.html), and served in the features of JSON-FG, see
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

GeoJSON cannot carry curves, so the features of a curve column are served as JSON-FG features, which give the
curve in `place`, and `null` in `geometry`:

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

The document declares the conformance classes of JSON-FG in `conformsTo`, and the CRS of `place`, the one of the
response, in `coordRefSys`. A JSON-FG reader, such as GDAL, reads the curves as they are, and a GeoJSON reader
gets features without geometry, rather than a geometry that is not theirs. The API never linearizes the curves
unless a client asks for it, with the [jsonfg-plus profile](#linearized-curves).

The `CompoundCurve`, `CurvePolygon`, `MultiCurve` and `MultiSurface` geometries hold their parts in
`geometries`.

A JSON-FG CircularString has 5 arcs at most, 11 points. A longer one is served as the CompoundCurve of its
arcs, 5 at a time, each part starting on the last point of the previous one, which draws the same curve. A
CircularString field takes it back in this form too, and stores it as a single CircularString again.

A page of features of a `GeometryField` column is JSON-FG when it has a curve, and GeoJSON otherwise. In JSON-FG,
`geometry` is in CRS84: asked for in another CRS, the features of the page have all their geometries in `place`.

The documents without curves stay GeoJSON, in the CRS they are asked for, as the clients of the API read them.
This is a choice of django-oapif: GeoJSON allows another CRS than CRS84 when a client asks for it, and JSON-FG
would give the geometries in `place` in another CRS, where GeoJSON readers would find none. JSON-FG recommends
GeoJSON by default, which the API departs from for curves only, as GeoJSON would give them no geometry.

Curves are read on any stack, but writing them takes GEOS 3.13 or newer, and a Django whose GEOS bindings
support curves, which no Django release does yet. Otherwise, writing a curve is answered with a
`501 Not Implemented`.

## Profiles

JSON-FG names three profiles of GeoJSON, which a request asks for with the `profile` query parameter, by name
or by URI, or with the `profile` parameter of the media type it accepts:

| Profile       | URI                                                    | Features                                                                                         |
|---------------|--------------------------------------------------------|--------------------------------------------------------------------------------------------------|
| `rfc7946`     | `http://www.opengis.net/def/profile/ogc/0/rfc7946`     | GeoJSON: a curve has no geometry.                                                                |
| `jsonfg`      | `http://www.opengis.net/def/profile/ogc/0/jsonfg`      | JSON-FG, the default of curves.                                                                  |
| `jsonfg-plus` | `http://www.opengis.net/def/profile/ogc/0/jsonfg-plus` | JSON-FG, with a GeoJSON geometry in `geometry` too, the [curves linearized](#linearized-curves). |

```bash
curl "https://example.com/oapif/collections/my_app.parcel/items?profile=jsonfg"
curl -H 'Accept: application/geo+json; profile="http://www.opengis.net/def/profile/ogc/0/jsonfg"' \
  "https://example.com/oapif/collections/my_app.parcel/items"
```

The query parameter chooses over the header, and a profile the API does not know is ignored, rather than
failing the request. Without one, a document is GeoJSON, or JSON-FG with curves. The response has the media type
`application/geo+json` in any profile, and links the profile of the document in its `Link` header:

```http
Link: <http://www.opengis.net/def/profile/ogc/0/jsonfg>; rel="profile"
```

The OGC register writes the URIs with `OGC`, and QGIS only knows them with `ogc`: the API takes both, and gives
those of QGIS.

A collection with a geometry links its items in the JSON-FG profiles, before its link to GeoJSON, with the
`profile` of the links of Features 1.1:

```json
{"rel": "items", "type": "application/geo+json", "profile": ["http://www.opengis.net/def/profile/ogc/0/jsonfg"], "href": "https://example.com/oapif/collections/my_app.parcel/items?profile=jsonfg", "title": "Collection items as JSON-FG"}
```

The links of a page of items to the other pages have the profile it was asked for, and are in its `Link` header
as well, with the number of features in `OGC-NumberMatched`: QGIS reads them there in JSON-FG.

## Linearized curves

In the `jsonfg-plus` profile, a feature has a GeoJSON geometry in CRS84 in `geometry` too, for the GeoJSON
readers: its curves linearized by PostGIS in the storage CRS, and reprojected. JSON-FG readers take `place`.
Asking for the profile is consenting to the approximation: nothing else linearizes the curves, nor GeoArrow,
whose WKB has them.

PostGIS draws a quarter of a circle with 32 segments. [`linearization_tolerance`](../usage/collections.md#options)
sets instead the largest distance between an arc and its segments, in the unit of the storage CRS:

```python
@oapif.register(Parcel)
class ParcelCollection(OapifCollection):
    # a millimetre, in EPSG:2056
    linearization_tolerance = 0.001
```

The linearization is symmetric: an arc two polygons share, like the boundary of two parcels, is made of the same
points in both, whichever way round they run along it. An empty geometry has none, as PostGIS fails on some.

## Requiring JSON-FG

A collection of a curve column can serve its items in JSON-FG only, instead of giving GeoJSON readers features
without geometry:

```python
@oapif.register(Parcel)
class ParcelCollection(OapifCollection):
    require_jsonfg = True
```

Its items asked for without a profile, or in `rfc7946`, are then answered with a `406 Not Acceptable`, which
links them in the JSON-FG profiles:

```json
{
  "detail": "The items of this collection are curves, which GeoJSON cannot carry: ask for them in JSON-FG",
  "links": [
    {"rel": "alternate", "type": "application/geo+json", "profile": ["http://www.opengis.net/def/profile/ogc/0/jsonfg"], "href": "https://example.com/oapif/collections/my_app.parcel/items?profile=jsonfg", "title": "This document as JSON-FG"},
    {"rel": "alternate", "type": "application/geo+json", "profile": ["http://www.opengis.net/def/profile/ogc/0/jsonfg-plus"], "href": "https://example.com/oapif/collections/my_app.parcel/items?profile=jsonfg-plus", "title": "This document as JSON-FG, with GeoJSON geometries, the curves linearized"}
  ]
}
```

The HTML pages and GeoArrow are served as they are. The option does not apply to a `GeometryField` column, whose
curves are only known feature by feature.

## Curves in QGIS

QGIS reads the items with GDAL, which tells JSON-FG from GeoJSON, and reads the curves of `place` since its 3.12:

- QGIS 3 knows no profiles. Its layers of curves have no geometry, unless the URL of the connection asks for
  the `jsonfg-plus` profile, `https://example.com/oapif/?profile=jsonfg-plus`, as QGIS adds its query to every
  request. The features are then the linearized curves, which GDAL reprojects from CRS84 to the CRS of the layer.
- QGIS 4.2 reads JSON-FG through the links of the collection, when the layer asks for the `application/fg+json`
  format.

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

A feature served in JSON-FG can be written back as it is, with the `Content-Crs` of its `coordRefSys`. A curve
column refuses a GeoJSON geometry without
`place`, such as the linearization that a GeoJSON client read, with a `422 Unprocessable Content` saying to send
the curve in `place`.
