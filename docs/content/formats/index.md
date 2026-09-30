# Formats

Features are served as GeoJSON, or as GeoArrow, as the request asks for with its `Accept` header, and as
HTML pages to a browser:

| Format                    | Media type                              | Resources                                                                            | Writes   |
|---------------------------|-----------------------------------------|--------------------------------------------------------------------------------------|----------|
| [GeoJSON](geojson.md)     | `application/geo+json`                  | every resource of features                                                           | yes      |
| [GeoArrow](geoarrow.md)   | `application/vnd.apache.arrow.stream`   | `/collections/{collectionId}/items`, `/collections/{collectionId}/items/{featureId}` | no       |
| [HTML](html.md)           | `text/html`                             | every resource but the API definition                                                | no       |

The other resources are JSON, and HTML to a browser: the landing page, the conformance declaration, the
collections and their schema. The API definition is an OpenAPI 3.1 document served at `/openapi.json`, which
Swagger UI shows at `/docs`.

## Content negotiation

GeoJSON is the default, served to a request that accepts `application/geo+json`, `application/json` or any
type, `*/*`, and to one without an `Accept` header. GeoArrow is served to a request whose `Accept` header
prefers it explicitly, and needs the `arrow` extra of django-oapif: without it, such a request is answered with
a `406 Not Acceptable`. HTML is served to a request that prefers `text/html`, as browsers do, or that asks for
it with `f=html`, `f=json` asking for the JSON instead: see [HTML](html.md#content-negotiation).

GeoJSON is served in the [GeoJSON profile](../fields/geometries.md#profiles) a request asks for with the
`profile` query parameter, or the `profile` parameter of `application/geo+json` in its `Accept` header: GeoJSON,
or JSON-FG, the default of curves.

As the same URL serves several encodings, the responses carry a `Vary: Accept` header, for caches to keep them apart.

A collection links its items in each format it serves, with the same URL and the `items` relation, and in the
profiles of JSON-FG, with the `profile` of the link:

```json
{
  "id": "my_app.building",
  "links": [
    {"rel": "items", "type": "application/geo+json", "profile": ["http://www.opengis.net/def/profile/ogc/0/jsonfg"], "href": "https://example.com/oapif/collections/my_app.building/items?profile=jsonfg", "title": "Collection items as JSON-FG"},
    {"rel": "items", "type": "application/geo+json", "profile": ["http://www.opengis.net/def/profile/ogc/0/jsonfg-plus"], "href": "https://example.com/oapif/collections/my_app.building/items?profile=jsonfg-plus", "title": "Collection items as JSON-FG, with GeoJSON geometries, the curves linearized"},
    {"rel": "items", "type": "application/geo+json", "href": "https://example.com/oapif/collections/my_app.building/items", "title": "Collection items"},
    {"rel": "items", "type": "application/vnd.apache.arrow.stream", "href": "https://example.com/oapif/collections/my_app.building/items", "title": "Collection items as GeoArrow"},
    ...
  ],
  ...
}
```
