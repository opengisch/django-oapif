# Changelog

## 2.0.0rc1

First release candidate of django-oapif 2.0. It adds GeoArrow output and JSON-FG curves, fixes a permission check on delete, and changes several behaviours that clients or projects may rely on: read [upgrading from 1.x](#upgrading-from-1x) before trying it, and [from 2.0.0-beta1](#upgrading-from-200-beta1) for curves.

pip only installs it when asked for:

```bash
pip install "django-oapif==2.0.0rc1"
```

Please report anything that breaks in the [issues](https://github.com/opengisch/django-oapif/issues).

### Security

- **Deleting a feature now requires the delete permission.** 1.x checked the view permission, so anyone who could read a feature could also delete it. Upgrade, or check your permissions on 1.x if deleting matters to you.

### Upgrading from 2.0.0-beta1

- **Curves are no longer served in `geometry`**, which GeoJSON does not allow, and GeoJSON readers such as QGIS dropped. The features of a curve column, and the pages of a `GeometryField` column that have a curve, are served as JSON-FG features, with the curve in `place` and `null` in `geometry`, in a document that declares its classes in `conformsTo` and its CRS in `coordRefSys`. Read the curves in `place`, or ask for their linearization in `geometry` with the [`jsonfg-plus` profile](fields/geometries.md#linearized-curves). The documents without curves are unchanged.

### Upgrading from 1.x

#### Requirements

- Django 5.2 or newer is required (was 5.0). 5.2, 6.0 and 6.1 are tested.
- The PostgreSQL driver is no longer installed with django-oapif, which used to pull in `psycopg2-binary`. Install one yourself if your project does not already, preferably psycopg 3:

  ```bash
  pip install "psycopg[binary]"
  ```

#### API behaviour

- A `crs`, `bbox-crs` or `Content-Crs` that the collection does not list in its `crs` is now rejected with `400`, instead of being reprojected to. By default a collection lists CRS84 and its storage CRS. Override `OapifCollection.supported_crs()` to [offer more](usage/crs.md#offering-more-crs).
- The spatial extent of a collection is now always given in CRS84, instead of in its storage CRS.
- Feature responses are sent as `application/geo+json` instead of `application/json`, with a `Content-Crs` header. `GET` responses also carry `Vary: Accept`.
- Items follow the model's `Meta.ordering`, with the primary key as tie breaker, so that pages no longer overlap or skip features. A collection that sets `ordering` keeps exactly that ordering.
- Properties come in the order the fields are declared, instead of in an arbitrary order.
- `PUT` and `PATCH` ignore a primary key in the body: they always update the feature in the URL.
- The conformance declaration drops the HTML and OpenAPI 3.0 classes, which the API did not meet, and declares the OpenAPI 3.1 class of Features Part 1 1.1, matching the document actually served.

#### Code that subclasses `OapifCollection`

- `query()` now annotates `_oapif_geometry` with WKB, instead of a GeoJSON dictionary. This only matters if you override `query()` or read that annotation.
- The CRS a collection offers now come from two new hooks, `storage_crs()` and `supported_crs()`.

### New

- **GeoArrow**: `/items` and `/items/{featureId}` return an Apache Arrow stream, with GeoArrow WKB geometries, when the request's `Accept` header prefers `application/vnd.apache.arrow.stream`. Paging links come in a `Link` header and the total in `OGC-NumberMatched`. The collection links to this encoding of its items. This needs the new `arrow` extra (`pip install "django-oapif[arrow]"`); without it such requests get a `406`. See [GeoArrow](formats/geoarrow.md).
- **[Curves](fields/geometries.md#curves)**: CircularString, CompoundCurve, CurvePolygon, MultiCurve and MultiSurface columns are served as JSON-FG features, the curves in `place`, and so are the pages of a `GeometryField` column that have a curve. A CircularString of more than 5 arcs, the most JSON-FG allows, is served as a CompoundCurve of its arcs, and accepted back in that form. Writing curves needs GEOS 3.13 and a Django whose GEOS bindings support curves, which no Django release has yet; otherwise writing one returns `501`.
- **[GeoJSON profiles](fields/geometries.md#profiles)**: the `profile` query parameter, or the `profile` of `application/geo+json` in the `Accept` header, asks for GeoJSON (`rfc7946`), JSON-FG (`jsonfg`), or JSON-FG with GeoJSON geometries in CRS84, the curves linearized (`jsonfg-plus`), which QGIS 3 asks for with the URL of its connection. The responses link their profile in a `Link` header, and the pages of items their other pages and their number of features in the headers too, where QGIS reads them in JSON-FG. A collection links its items in the JSON-FG profiles, as QGIS 4.2 finds them, and the conformance declaration lists the classes of JSON-FG and the profile query parameter.
- `linearization_tolerance` sets how closely the linearized curves follow the arcs, and `require_jsonfg` answers the requests of the items of a curve column in GeoJSON with a `406` that links them in JSON-FG: see the [options](usage/collections.md#options) of the collections.
- **[JSON-FG input](fields/geometries.md#json-fg-features)**: `POST`, `PUT` and `PATCH` accept a `place`, which is stored instead of the `geometry` fallback, and a `coordRefSys`, which must match the `Content-Crs`. A curve column sent a GeoJSON geometry, such as a linearized curve, answers that the curve goes in `place`.
- **[HTML](formats/html.md)**: browsers get an HTML page of every resource but the API definition, with a map of the features, which the JSON links with the `alternate` relation. `f=html` and `f=json` choose the encoding instead of the `Accept` header. The landing page links Swagger UI with the `service-doc` relation.
- PolyhedralSurface and TIN geometries are served as MultiPolygons, and Triangles as Polygons.
- CRS URIs are accepted with `https://`, and a `Content-Crs` is accepted in angle brackets, the way the responses send it.
- The items `limit` is published under `components/parameters` in the OpenAPI document, which is where QGIS reads the page size from.
- Feature collections carry the `bbox` of the page.
- The schema gives the choices of a field as the `enum` of its property, and the bounds of a number, from its validators and the range of its column, as its `minimum` and `maximum`. The validators of a string give its `minLength`, `maxLength` and `pattern`. URLs, emails, files, and IP addresses of a single version have their `format`.
- The schema gives the primary key the `id` role, and a [foreign key](fields/foreign-keys.md) the `reference` role, with the collections it references in `x-ogc-collectionId`. The conformance declaration lists the feature references class of Part 5.

### Fixes

- Unknown properties in `POST` and `PUT` are always rejected. After a `GET`, they used to be dropped silently.
- Invalid geometries, such as polygons with unclosed rings, and errors raised by validators now return `422`, instead of a server error.
- LineString coordinates are checked against the dimension of the column, like those of the other geometry types.
- Geometry fields declared with `dim=3` accept and serve Z coordinates.
- The schema of a collection is served, and linked from the collection, as `application/schema+json`, as Part 5 requires, instead of `application/json`.
- Decimals are described in the schema as the strings they are served as. They had no type, and QGIS made no field of them.
- Read-only properties are marked `readOnly` in the schema, so QGIS no longer lets them be edited, only to have the write rejected.
- The schema leaves out the fields of `exclude`, which it described although they are neither served nor written.
- The conformance declaration lists the returnables and receivables class of Part 5, which the collections already met by linking their schema.
- The `$id` of a schema is its URI without the query parameters of the request, such as `f=json`.
- The schema gives the position of each property, which QGIS orders the fields of a layer by, instead of alphabetically.

### Performance

- GeoJSON is serialized directly by pydantic, instead of being validated again by django-ninja and then written with `json.dumps`.
- Geometries are read from the database as WKB, and the bbox of a page is computed from them as they are read.
- Collection extents are computed in the storage CRS, and only their outline is reprojected, instead of every geometry.
- The documentation now has a [deployment](usage/deployment.md) page. Use persistent database connections: PostGIS prepares each reprojection once per connection, which costs about 130 ms, so without them every request in a CRS other than the storage one pays that again.

## 1.x and earlier

The releases before 2.0 are listed on [GitHub](https://github.com/opengisch/django-oapif/releases).
