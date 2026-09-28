# Geometries

## The geometry field

A collection takes the geometry of its features from the geometry field of its model. A model with several
geometry fields has to name the one to serve in [`geometry_field`](../usage/collections.md#options). A model
without one is served as a collection of features without geometry, whose `geometry` is `null`, like the
features whose geometry field is null.

## Geometry types

Geometries are written as in GeoJSON, but for curves, which GeoJSON does not have: they are written as in
[JSON-FG](https://docs.ogc.org/is/21-045r1/21-045r1.html).

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

Curves are served in the `geometry` of the features, as JSON-FG geometries:

```json
{
  "type": "CircularString",
  "coordinates": [[2508500.0, 1152000.0], [2508510.0, 1152010.0], [2508520.0, 1152000.0]]
}
```

The `CompoundCurve`, `CurvePolygon`, `MultiCurve` and `MultiSurface` geometries hold their parts in
`geometries`.

A JSON-FG CircularString has 5 arcs at most, 11 points. A longer one is served as the CompoundCurve of its
arcs, 5 at a time, each part starting on the last point of the previous one, which draws the same curve. A
CircularString field takes it back in this form too, and stores it as a single CircularString again.

Curves are read on any stack, but writing them takes GEOS 3.13 or newer, and a Django whose GEOS bindings
support curves, which no Django release does yet. Otherwise, writing a curve is answered with a
`501 Not Implemented`.

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

The API serves curves in `geometry` itself, and does not write `place` nor `coordRefSys`.
