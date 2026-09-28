# Formats

Features are served as GeoJSON, or as GeoArrow, as the request asks for with its `Accept` header:

| Format                    | Media type                              | Resources                                                                            | Writes   |
|---------------------------|-----------------------------------------|--------------------------------------------------------------------------------------|----------|
| [GeoJSON](geojson.md)     | `application/geo+json`                  | every resource of features                                                           | yes      |
| [GeoArrow](geoarrow.md)   | `application/vnd.apache.arrow.stream`   | `/collections/{collectionId}/items`, `/collections/{collectionId}/items/{featureId}` | no       |

The other resources are JSON: the landing page, the conformance declaration, the collections, their schema,
and the API definition, an OpenAPI 3.1 document served at `/openapi.json`, which Swagger UI shows at `/docs`.

## Content negotiation

GeoJSON is the default, served to a request that accepts `application/geo+json`, `application/json` or any
type, `*/*`, and to one without an `Accept` header. GeoArrow is served to a request whose `Accept` header
prefers it explicitly, and needs the `arrow` extra of django-oapif: without it, such a request is answered with
a `406 Not Acceptable`.

As the same URL serves both, the responses carry a `Vary: Accept` header, for caches to keep them apart.

A collection links its items in each format it serves, with the same URL and the `items` relation:

```json
{
  "id": "my_app.building",
  "links": [
    {"rel": "items", "type": "application/geo+json", "href": "https://example.com/oapif/collections/my_app.building/items", "title": "Collection items"},
    {"rel": "items", "type": "application/vnd.apache.arrow.stream", "href": "https://example.com/oapif/collections/my_app.building/items", "title": "Collection items as GeoArrow"},
    ...
  ],
  ...
}
```
