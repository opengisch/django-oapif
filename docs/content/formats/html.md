# HTML

Every resource but the API definition is also an HTML page, to browse the API in a browser: the landing page,
the conformance declaration, the collections, their schema and queryables, their items and each feature. The
items of a page and a feature are drawn on a map, and so is the extent of a collection. The API definition has
its own page, Swagger UI at `/docs`, which the landing page links with the `service-doc` relation.

## Content negotiation

A browser gets the pages, as its `Accept` header prefers `text/html`. The other clients get the JSON, which
stays the default for a request that accepts any type, `*/*`, and for one without an `Accept` header.

The `f` query parameter chooses instead of the `Accept` header: `f=html` asks for the page, and `f=json`
for the JSON. The JSON links its page this way, with the `alternate` relation, and a page links its JSON:

```json
{"rel": "alternate", "type": "text/html", "href": "https://example.com/oapif/collections?f=html", "title": "this document as HTML"}
```

As the same URL serves both, the responses carry a `Vary: Accept` header.

## Schemas

The pages of the schema and of the queryables of a collection have a row for each property, with all that its
JSON Schema says of it: its title and description, its type and format, its role, whether it is required or
read-only, its default, and its constraints, such as its bounds, length, pattern and choices. A foreign key
links the collections it references. A keyword without a column of its own is listed with the constraints,
including one that a collection adds to its schema.

## Maps

The maps are drawn with [Leaflet](https://leafletjs.com), over [OpenStreetMap](https://www.openstreetmap.org)
tiles, which the browser loads from jsDelivr and from the OpenStreetMap tile servers. As their
[tile usage policy](https://operations.osmfoundation.org/policies/tiles/) asks, the tiles are requested with
the origin of the page as `Referer`, whatever the `Referrer-Policy` of the site. Curves are drawn as
lines. The coordinates of a map are in CRS84: a page asked for in another CRS, with `crs`, has none.

## Changing the pages

The pages are Django templates, which a project replaces with its own templates of the same name, found
before those of django-oapif, such as in a directory of its `TEMPLATES` `DIRS`:

| Template                        | Page                                                   |
|---------------------------------|--------------------------------------------------------|
| `django_oapif/base.html`        | the layout of every page, with its header and styles   |
| `django_oapif/map.html`         | the map, included by the pages that have one           |
| `django_oapif/landing.html`     | `/`                                                    |
| `django_oapif/conformance.html` | `/conformance`                                         |
| `django_oapif/collections.html` | `/collections`                                         |
| `django_oapif/collection.html`  | `/collections/{collectionId}`                          |
| `django_oapif/schema.html`      | `/collections/{collectionId}/schema`                   |
| `django_oapif/queryables.html`  | `/collections/{collectionId}/queryables`               |
| `django_oapif/properties.html`  | the table of the properties, included by these two     |
| `django_oapif/items.html`       | `/collections/{collectionId}/items`                    |
| `django_oapif/item.html`        | `/collections/{collectionId}/items/{featureId}`        |

The collections of `django_oapif/collections.html` have no extent, which would take a query each, unlike the
collection of `django_oapif/collection.html`.

## Conformance

The pages do not make the API meet the HTML conformance classes of OGC API - Common and OGC API - Features,
which ask for every resource as HTML, the API definition included: the conformance declaration does not
list them.
