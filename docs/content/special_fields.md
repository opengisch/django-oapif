# Foreign Keys

Model relations are handle by displaying the primary key of the referenced objects.

Given two models:

```py
class Parent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    geom = models.PointField(srid=4326)

class Child(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    geom = models.PointField(srid=4326)
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE)
```
```py
oapif.register_collection(Parent)
oapif.register_collection(Child)
```

A GeoJSON feature for a collection mapped to the Child model would look like this:

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [0, 0],
  },
  "properties": {
    "parent": "2310f561-39a4-4393-844c-19c99a12f45d"
  }
}
```

This behavior is shared for all `GET`, `POST`, `PUT`, `PATCH` operations.

# Files

Django `FileFields` are returned using their `url` property. `FileFields` properties updates are currently not possible, they are therefore marked as readonly by default.

Given a model:

```py
class File(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    file = models.FileField(upload_to="/file_data")
```

A GeoJSON feature for a collection mapped to the File model would look like this:

```json
{
  "type": "Feature",
  "geometry": null,
  "properties": {
    "file": "/media/file_data/item.txt"
  }
}
```
