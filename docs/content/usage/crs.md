# Coordinate reference systems

Features are served in [CRS84](http://www.opengis.net/def/crs/OGC/1.3/CRS84), longitude and latitude on
WGS 84, unless a request asks for another coordinate reference system (CRS) that the collection offers, as
defined by [OGC API - Features - Part 2](https://docs.ogc.org/is/18-058r1/18-058r1.html).

## The CRS of a collection

The description of a collection lists the CRS it offers in `crs`, and gives the one its geometries are stored
in, the SRID of its geometry field, as `storageCrs`:

```json
{
  "id": "my_app.building",
  "crs": [
    "http://www.opengis.net/def/crs/OGC/1.3/CRS84",
    "http://www.opengis.net/def/crs/EPSG/0/2056"
  ],
  "storageCrs": "http://www.opengis.net/def/crs/EPSG/0/2056",
  ...
}
```

By default, a collection offers CRS84 and its storage CRS, or CRS84 alone when its geometries are stored in
EPSG:4326. A collection without geometry offers none, and ignores the CRS parameters. The spatial extent of a
collection is always given in CRS84.

## Reading in a CRS

The `crs` parameter of `/collections/{collectionId}/items` and `/collections/{collectionId}/items/{featureId}`
asks for the features in another CRS, and `bbox-crs` gives the CRS of the `bbox` parameter:

```bash
curl "https://example.com/oapif/collections/my_app.building/items?crs=http://www.opengis.net/def/crs/EPSG/0/2056"
```

Both default to CRS84. The response gives the CRS of its coordinates in its `Content-Crs` header, with the URI
in angle brackets:

```http
Content-Crs: <http://www.opengis.net/def/crs/EPSG/0/2056>
```

## Writing in a CRS

The `Content-Crs` header of a `POST`, `PUT` or `PATCH` gives the CRS of the coordinates of the feature sent,
with or without angle brackets, and defaults to CRS84 too. The feature returned is in CRS84.

## CRS URIs

A CRS is given by its URI, `http://www.opengis.net/def/crs/OGC/1.3/CRS84` or
`http://www.opengis.net/def/crs/EPSG/0/{code}`, which is also accepted with `https://`.

A CRS that the collection does not offer is rejected with a `400 Bad Request`, whether in `crs`, `bbox-crs`
or `Content-Crs`. In particular, EPSG:4326 is not CRS84: its axis order is latitude first, which the API
does not follow, and a client that sent coordinates latitude first would have them stored swapped.

## Offering more CRS

Override `supported_crs()` to offer other CRS:

```python
from django_oapif import OapifCollection
from django_oapif.crs import CRS


@oapif.register(Building)
class BuildingCollection(OapifCollection):
    def supported_crs(self):
        return (*super().supported_crs(), CRS("EPSG", 3857))
```

The features are reprojected by PostGIS, which writes the coordinates x first, whatever the axis order of the
CRS: offer only CRS whose first axis is the easting or the longitude.

Reprojecting the features of a request takes a prepared transformation, which PostGIS keeps for the lifetime
of the database connection: see [deployment](deployment.md) to keep connections open.
