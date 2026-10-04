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
- **The extent of a collection no longer covers the features its [`get_queryset()`](usage/collections.md#hooks) hides.** 1.x and the 2.0 betas computed it from every row of the model, so a collection serving each user their own features gave them the extent of everyone's, whose corners can be the coordinates of someone else's feature. Upgrade if that matters to you.
- **A `POST` no longer overwrites the feature whose id it carries.** 1.x and the 2.0 betas saved it over that feature when the primary key has no default, like the `id` Django gives a model, so anyone who could add features could change any of them, even those they could not see. It is now refused with a `409 Conflict`, instead of a server error when the key has a default, such as a UUID. Upgrade, or on 1.x give the add permission only to users who may change every feature.
- **A [foreign key](fields/foreign-keys.md) can no longer reference a feature that [`get_queryset()`](usage/collections.md#hooks) hides from the user.** 1.x and the 2.0 betas accepted the key of any row of the referenced model, so a user could link a feature to someone else's, in a collection serving each user their own features, and tell from a `201` or a `422` which keys exist. Upgrade if that matters to you.

### Upgrading from 2.0.0-beta1

- **Curves are no longer served in `geometry`**, which GeoJSON does not allow, and which GeoJSON readers such as QGIS dropped. A request for them in GeoJSON is refused with a `406`, which links them in JSON-FG, with the curves in `place`, and in GeoJSON, linearized: ask for one or the other with `profile=jsonfg` or `linearize=true`. QGIS 3 asks for the linearized curves with `?linearize=true` in the URL of its connection. The features without curves are unchanged. See [curves](fields/geometries.md#curves).

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
- `get_queryset()` also gives the extent of a collection, so `/collections` calls it too, for every collection the user may view: one that fails for a user, an anonymous one for instance, now fails their list of collections too, and not only the items of that collection.
- `get_queryset()` also limits the rows a foreign key to its model may reference, so `POST`, `PUT` and `PATCH` call it too, for the collections the key references: one that fails for a user now fails their writes of such a key too, and not only the items of that collection.

### New

- **[Filtering](usage/filtering.md)**: `/items` takes a CQL2 text `filter`, as defined by Features Part 3, and each collection describes the properties it can be filtered on at `/queryables`. QGIS sends the filter of a layer to the server this way, instead of filtering every feature itself. Comparisons, `LIKE`, `BETWEEN`, `IN`, `CASEI` and the spatial functions are supported. This adds pygeofilter to the requirements.
- **GeoArrow**: `/items` and `/items/{featureId}` return an Apache Arrow stream, with GeoArrow WKB geometries, when the request's `Accept` header prefers `application/vnd.apache.arrow.stream`. Paging links come in a `Link` header and the total in `OGC-NumberMatched`. The collection links to this encoding of its items. This needs the new `arrow` extra (`pip install "django-oapif[arrow]"`); without it such requests get a `406`. See [GeoArrow](formats/geoarrow.md).
- **[Curves](fields/geometries.md#curves)**: CircularString, CompoundCurve, CurvePolygon, MultiCurve and MultiSurface columns are served in JSON-FG, the curves in `place`, or in GeoJSON [linearized](fields/geometries.md#linearized-curves) by PostGIS, in the CRS asked for, with the `linearize` parameter and the `linearization_tolerance` of the collection. GeoJSON refuses them otherwise, with a `406` that links both, and so it does the pages of a `GeometryField` column that have a curve. A CircularString of more than 5 arcs, the most JSON-FG allows, is served as a CompoundCurve of its arcs, and accepted back in that form. Writing curves needs GEOS 3.13 and a Django whose GEOS bindings support curves, which no Django release has yet; otherwise writing one returns `501`.
- **[JSON-FG](fields/geometries.md#json-fg)**: the `profile` query parameter, or the `profile` of `application/geo+json` in the `Accept` header, asks for the features of any collection in JSON-FG (`jsonfg`), or in GeoJSON (`rfc7946`), the default. The responses link their profile in a `Link` header, and the pages of items their other pages and their number of features in the headers too, where QGIS reads them in JSON-FG. A collection links its items in JSON-FG, as QGIS 4.2 finds them, and the conformance declaration lists the classes of JSON-FG and the profile query parameter.
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
- A write that leaves a feature out of the rows of [`get_queryset()`](usage/collections.md#hooks), such as one moved out of the area of the user, now returns a `201` with its `Location` for a `POST`, and a `204` for a `PUT` or `PATCH`, without the feature. It used to be saved and answered with a server error, which a client could take for a failure and send again, or, with `ATOMIC_REQUESTS`, refused with one.
- LineString coordinates are checked against the dimension of the column, like those of the other geometry types.
- Geometry fields declared with `dim=3` accept and serve Z coordinates.
- `POST`, `PUT` and `PATCH` no longer fail with a server error when a foreign key references a model that has no `objects` manager.
- A foreign key to another field than the primary key, with `to_field`, is written as it is served: the value of that field. It was looked up as a primary key, so the value read was refused, or linked the row whose primary key it is.
- The schema of a collection is served, and linked from the collection, as `application/schema+json`, as Part 5 requires, instead of `application/json`.
- Decimals are described in the schema as the strings they are served as. They had no type, and QGIS made no field of them.
- Read-only properties are marked `readOnly` in the schema, so QGIS no longer lets them be edited, only to have the write rejected.
- The schema leaves out the fields of `exclude`, which it described although they are neither served nor written.
- The conformance declaration lists the returnables and receivables class of Part 5, which the collections already met by linking their schema.
- The `$id` of a schema is its URI without the query parameters of the request, such as `f=json`.
- The schema gives the position of each property, which QGIS orders the fields of a layer by, instead of alphabetically.
- The members a collection has no value for, such as its `description` or `extent`, are left out instead of being `null`, which OGC API - Features does not allow.
- `/collections` and `/collections/{collectionId}` no longer fail with a server error when the model of a collection has no `objects` manager.
- `/collections` and `/collections/{collectionId}` no longer fail with a server error when the features of a collection stored in a CRS other than EPSG:4326 lie on one horizontal or vertical line, such as two points side by side, as they did in the 2.0 betas.

### Performance

- GeoJSON is serialized directly by pydantic, instead of being validated again by django-ninja and then written with `json.dumps`.
- Geometries are read from the database as WKB, and the bbox of a page is computed from them as they are read.
- Collection extents are computed in the storage CRS, and only their outline is reprojected, instead of every geometry.
- The documentation now has a [deployment](usage/deployment.md) page. Use persistent database connections: PostGIS prepares each reprojection once per connection, which costs about 130 ms, so without them every request in a CRS other than the storage one pays that again.

## 1.x and earlier

The releases before 2.0 are listed on [GitHub](https://github.com/opengisch/django-oapif/releases).
