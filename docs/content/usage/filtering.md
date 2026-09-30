# Filtering

The items of a collection can be filtered with a [CQL2](https://docs.ogc.org/is/21-065r2/21-065r2.html)
expression, as defined by [OGC API - Features - Part 3](https://docs.ogc.org/is/19-079r2/19-079r2.html). QGIS
sends the filter of a layer this way, instead of downloading every feature to filter them itself.

## The filter parameters

The `filter` parameter of `/collections/{collectionId}/items` takes an expression in the text encoding of CQL2:

```bash
curl "https://example.com/oapif/collections/my_app.building/items" \
  --get \
  --data-urlencode "filter=floors >= 3 AND name LIKE 'Maison%'"
```

- `filter-lang` can only be `cql2-text`, its default: the JSON encoding of CQL2 is not supported.
- `filter-crs` gives the CRS of the geometries in the filter, and defaults to CRS84. Like the
  [other CRS parameters](crs.md#crs-uris), it takes a CRS that the collection offers.

A filter applies with the other parameters: the items match both the `filter` and the `bbox`, and the
`numberMatched` and the paging links account for it.

A filter that cannot be applied is rejected with a `400 Bad Request`, which says why. This covers a syntax error,
a property that is not a [queryable](#queryables), a value of the wrong type, and an operator or function that is
not supported.

## Supported expressions

| Conformance class             | Expressions                                                                          |
|-------------------------------|--------------------------------------------------------------------------------------|
| Basic CQL2                    | `=`, `<>`, `<`, `<=`, `>`, `>=`, `IS [NOT] NULL`, `AND`, `OR`, `NOT`, `DATE('…')`, `TIMESTAMP('…')` |
| Advanced comparison operators | `[NOT] LIKE`, `[NOT] BETWEEN`, `[NOT] IN`                                            |
| Case-insensitive comparison   | `CASEI(…)`, with `=`, `<>`, `LIKE` and `IN`                                          |
| Basic spatial functions       | `S_INTERSECTS`, with `POINT`, `LINESTRING`, `POLYGON`, their multi-parts and `BBOX`  |

`S_DISJOINT`, `S_CONTAINS`, `S_WITHIN`, `S_TOUCHES`, `S_CROSSES`, `S_OVERLAPS` and `S_EQUALS` are accepted as well.
Arithmetic, and the temporal and array functions, are not supported.

Comparisons follow the three-valued logic of CQL2: a comparison with a null value is neither true nor false, and
neither is its negation. `NOT (floors = 3)` does not match the buildings whose `floors` is null, just as QGIS
would not.

In `LIKE`, `%` stands for any characters, `_` for a single one, and a backslash makes the next character an
ordinary one: `'100\%'` matches `100%`. A quote in a string is written twice, `'Route d''Oron'`.

## Queryables

The properties that a filter can take are the queryables of the collection, described by a JSON Schema at
`/collections/{collectionId}/queryables`, which the collection links to:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/oapif/collections/my_app.building/queryables",
  "type": "object",
  "title": "my_app.Building",
  "properties": {
    "name": {"title": "Name", "maxLength": 255, "type": "string", "x-ogc-propertySeq": 2},
    "floors": {"title": "Floors", "type": "integer", "x-ogc-propertySeq": 3},
    "geom": {
      "title": "geometry",
      "x-ogc-role": "primary-geometry",
      "format": "geometry-polygon",
      "x-ogc-propertySeq": 4,
      "$ref": "https://geojson.org/schema/Polygon.json"
    }
  },
  "additionalProperties": false
}
```

The geometry refers to its GeoJSON schema, the only way QGIS recognizes a geometry queryable by. QGIS only sends
the parts of a filter that take queryables, and filters the features on the others itself.

By default, the queryables are the properties of the features, the ones in `fields` and not in `exclude`, and the
geometry. Override `get_queryables()` to restrict them, for instance to the fields that have an index:

```python
@oapif.register(Building)
class BuildingCollection(OapifCollection):
    def get_queryables(self, request):
        return ("name", "floors", "geom")
```

The queryables are among the fields of the collection: a property that is not exposed cannot be filtered on,
and neither can the fields of a related model.
