# Fields

The fields of a model are the properties of its features, except its geometry field, whose value is their
[geometry](geometries.md).

## Properties

Every field is served as a property, the primary key included, in the order the model declares them,
unless the [options](../usage/collections.md#options) of the collection choose others. The primary key is also the `id` of the feature, as a string. Reverse relations are not served.

The values are written as JSON:

| Field                                               | Property                                                                   |
|-----------------------------------------------------|----------------------------------------------------------------------------|
| `BooleanField`                                      | boolean                                                                    |
| `IntegerField`, and the other integer fields        | integer                                                                    |
| `FloatField`                                        | number                                                                     |
| `DecimalField`                                      | string: `"1.50"`                                                           |
| `CharField`, `TextField`, and the other text fields | string                                                                     |
| `UUIDField`, `GenericIPAddressField`                | string                                                                     |
| `DateField`                                         | string: `"2026-09-28"`                                                     |
| `DateTimeField`                                     | string, to the millisecond: `"2026-09-28T12:34:56.789Z"`                   |
| `TimeField`                                         | string, to the millisecond: `"12:34:56.789"`                               |
| `DurationField`                                     | string, in ISO 8601: `"P1DT02H00M03S"`                                     |
| `JSONField`                                         | the JSON value                                                             |
| `ForeignKey`                                        | the primary key of the referenced row, see [foreign keys](foreign-keys.md) |
| `FileField`, `ImageField`                           | the URL of the file, see [files](files.md)                                 |

Dates, times and durations are written as Django's `DjangoJSONEncoder` writes them.

## Writing properties

A `POST` or a `PUT` takes the properties of a whole feature: those of the fields that have no default and
cannot be null are required. A `PATCH` takes only the properties it changes.

Read-only fields are served, but not written: the fields of files, generated fields, and those listed in
`readonly_fields`. A write that carries a read-only field, or a property that the collection does not have,
is rejected with a `422 Unprocessable Content`, as is a write with an invalid value. A client that writes
back a feature it has read has to leave out its read-only properties.

The primary key of a `POST` is the one of the feature created, and defaults as the model defines it. `PUT` and
`PATCH` ignore it: they always change the feature of the URL.

## Schema

`/collections/{collectionId}/schema` returns the [JSON Schema](https://json-schema.org/) of the features of a
collection, as defined by
[OGC API - Features - Part 5](https://docs.ogc.org/DRAFTS/23-058r1.html): the type of each property, its
maximum length, its position, the required and read-only ones, and the geometry, with the `primary-geometry` role and
its type as `format`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://example.com/oapif/collections/my_app.building/schema",
  "title": "my_app.Building",
  "type": "object",
  "properties": {
    "id": {"title": "ID", "type": "integer", "x-ogc-propertySeq": 1},
    "name": {"title": "Name", "type": "string", "maxLength": 100, "x-ogc-propertySeq": 2},
    "geom": {"title": "geometry", "x-ogc-role": "primary-geometry", "format": "geometry-polygon", "x-ogc-propertySeq": 3}
  },
  "required": ["name"],
  "additionalProperties": false
}
```
