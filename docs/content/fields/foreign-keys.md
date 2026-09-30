# Foreign keys

A foreign key is served as the primary key of the row it references.

Given two models:

```python
class Parent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    geom = models.PointField(srid=4326)

class Child(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    geom = models.PointField(srid=4326)
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE)
```

```python
oapif.register_collection(Parent)
oapif.register_collection(Child)
```

A feature of the `Child` collection looks like this:

```json
{
  "type": "Feature",
  "id": "8a4b3a52-5b0e-4bd4-9c8f-0c5b1f6f3f2e",
  "geometry": {
    "type": "Point",
    "coordinates": [0.0, 0.0]
  },
  "properties": {
    "id": "8a4b3a52-5b0e-4bd4-9c8f-0c5b1f6f3f2e",
    "parent": "2310f561-39a4-4393-844c-19c99a12f45d"
  }
}
```

Writes take the same primary key, in `POST`, `PUT` and `PATCH`. A key that references no row is rejected with a
`422 Unprocessable Content`:

```json
{
  "detail": [
    {
      "loc": ["body", "feature", "properties", "parent"],
      "msg": "Foreign key not found",
      "type": "value_error"
    }
  ]
}
```

The reverse relations, the children of a parent here, are not served.

## Schema

The [schema](index.md#schema) of the collection gives the property the `reference` role of
[Part 5](https://docs.ogc.org/DRAFTS/23-058r1.html), with the collections of the referenced model that the user may
view in `x-ogc-collectionId`: a single id, or a list when the model has several collections.

```json
"parent": {
  "title": "Parent",
  "type": "string",
  "format": "uuid",
  "x-ogc-role": "reference",
  "x-ogc-collectionId": "my_app.parent",
  "x-ogc-propertySeq": 2
}
```

A key to a model without a collection, or to another field than its primary key, has no role.
