<h1>
  <img alt="Django-OAPIF" src="assets/logo-with-name.svg#only-light" width="520">
  <img alt="Django-OAPIF" src="assets/logo-with-name-dark.svg#only-dark" width="520">
</h1>

*Django-OAPIF* serves Django models through an [OGC API - Features](https://ogcapi.ogc.org/features/)
endpoint, built on [Django Ninja](https://django-ninja.dev/). Clients such as QGIS read and edit their features,
within the permissions of Django.

```python
from django_oapif import OAPIF

oapif = OAPIF()
oapif.register_collection(Building)
```

## Features

- Every registered model is a [collection](usage/collections.md) of features, which clients query by box,
  page and [coordinate reference system](usage/crs.md), and create, replace, update and delete.
- Features are served as [GeoJSON](formats/geojson.md), with curves as JSON-FG geometries, or as
  [GeoArrow](formats/geoarrow.md).
- Who may read and write each collection is decided by the model [permissions](usage/permissions.md) of
  Django, or by others.
- Each collection describes its features with a JSON Schema, and the API with an OpenAPI 3.1 document.

## Standards

The API declares these conformance classes:

| Standard                                                                                                                 | Conformance classes                         |
|--------------------------------------------------------------------------------------------------------------------------|---------------------------------------------|
| OGC API - Common - Part 1: Core                                                                                          | Core, JSON, Landing page                    |
| OGC API - Common - Part 2: Geospatial data                                                                               | Collections                                 |
| [OGC API - Features - Part 1: Core](https://docs.ogc.org/is/17-069r4/17-069r4.html)                                      | Core, GeoJSON, OpenAPI 3.1                  |
| [OGC API - Features - Part 2: Coordinate Reference Systems by Reference](https://docs.ogc.org/is/18-058r1/18-058r1.html) | Coordinate Reference Systems by Reference   |
| [OGC API - Features - Part 4: Create, Replace, Update and Delete](https://docs.ogc.org/DRAFTS/20-002r1.html)             | Create/Replace/Delete, Update, Features     |
| [OGC API - Features - Part 5: Schemas](https://docs.ogc.org/DRAFTS/23-058r1.html)                                        | Core roles for features, Feature references, Returnables and receivables, Schemas |

OpenAPI 3.1 is a class of the 1.1 draft of Part 1, as the published standards only have one for OpenAPI 3.0:
see [conformance](contributing/conformance.md#openapi-31).

## Get started

Follow the [quick start](quick-start.md) to serve your own models, or [try the demo](demo.md) to see an API
running.
