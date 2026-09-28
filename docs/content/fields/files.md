# Files

A `FileField`, or an `ImageField`, is served as the URL of its file, given by its storage.

Given a model:

```python
class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4)
    file = models.FileField(upload_to="documents")
```

A feature of its collection looks like this:

```json
{
  "type": "Feature",
  "id": "5d8e2c1a-8f4b-4d7e-9a3c-2b6f1e0d4c7a",
  "geometry": null,
  "properties": {
    "id": "5d8e2c1a-8f4b-4d7e-9a3c-2b6f1e0d4c7a",
    "file": "/media/documents/report.pdf"
  }
}
```

Files cannot be written through the API: their fields are always [read-only](index.md#writing-properties),
and a write that carries one is rejected.
