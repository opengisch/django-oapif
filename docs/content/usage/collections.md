# Collections

Each model registered with `OAPIF` is served as a collection of features: its rows are the features, its
geometry field their geometry, and its other fields their properties.

## Registering models

`register_collection` takes a model, or a list of models, and the class that serves them, which defaults to
[`OapifCollection`](../api.md#django_oapif.OapifCollection):

```python
from django_oapif import OAPIF, AnonReadOnlyCollection

from .models import Building, Parcel, Road

oapif = OAPIF()

oapif.register_collection(Building)
oapif.register_collection([Parcel, Road], AnonReadOnlyCollection)
```

To configure a collection, subclass `OapifCollection`, or one of the classes of
[permissions](permissions.md), and register it with the `register` decorator:

```python
from django_oapif import OapifCollection


@oapif.register(Building)
class BuildingCollection(OapifCollection):
    id = "buildings"
    title = "Buildings"
    description = "The buildings of the city"
    fields = ("name", "height", "roof")
    readonly_fields = ("height",)
    ordering = ("name",)
```

A model can be registered more than once, as long as each collection has an `id` of its own: to serve a subset
of its fields, for instance.

## Options

| Attribute                 | Default                                                          | Description                                                                                                                                                   |
|---------------------------|------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `id`                      | the model label in lower case, `my_app.building`                 | The identifier of the collection in the URLs: `/collections/{id}/items`.                                                                                      |
| `title`                   | the model label, `my_app.Building`                               | The title of the collection.                                                                                                                                  |
| `description`             | none                                                             | The description of the collection.                                                                                                                            |
| `geometry_field`          | the geometry field of the model                                  | The field of the feature geometries. `None` serves the collection without geometry.                                                                           |
| `fields`                  | every field of the model, but the geometry and reverse relations | The fields served as properties, in this order.                                                                                                               |
| `readonly_fields`         | none                                                             | Fields that are served, but not accepted in writes.                                                                                                           |
| `exclude`                 | none                                                             | Fields that are not served.                                                                                                                                   |
| `ordering`                | the model `Meta.ordering`, then the primary key                  | The order of the features.                                                                                                                                    |
| `linearization_tolerance` | none, 32 segments a quarter of a circle                          | The largest distance between an arc and its segments when [curves are linearized](../fields/geometries.md#linearized-curves), in the unit of the storage CRS. |

A model with several geometry fields has to name one in `geometry_field`, and cannot be registered
otherwise. The [fields](../fields/index.md) pages describe how each kind of field is served.

The primary key completes the ordering of the model so that pages of features never overlap, nor skip one: an
`ordering` set on the collection is taken as it is, and should end with a unique field as well.

## Hooks

The methods of `OapifCollection` can be overridden to adapt a collection to each request, the way those of
Django's `ModelAdmin` are:

| Method                                                                          | Returns                                                                                                       |
|---------------------------------------------------------------------------------|---------------------------------------------------------------------------------------------------------------|
| `get_queryset(request)`                                                         | The rows it serves, changes and deletes, computes its extent from, and that foreign keys to it may reference. |
| `get_fields(request, obj=None)`                                                 | The fields served as properties, `fields` by default.                                                         |
| `get_exclude(request, obj=None)`                                                | The fields not served, `exclude` by default.                                                                  |
| `get_readonly_fields(request, obj=None)`                                        | The fields not accepted in writes: `readonly_fields`, generated fields and files.                             |
| `get_ordering(request)`                                                         | The order of the features.                                                                                    |
| `get_queryables(request)`                                                       | The fields the features can be [filtered](filtering.md#queryables) on.                                        |
| `save_model(request, obj, change)`                                              | Saves a created or changed row.                                                                               |
| `delete_model(request, obj)`                                                    | Deletes a row.                                                                                                |
| `has_view_permission(request, obj=None)`, and the add, change and delete ones   | See [permissions](permissions.md).                                                                            |
| `storage_crs()`, `supported_crs()`                                              | See [coordinate reference systems](crs.md).                                                                   |

For instance, to serve each user their own features only, and to record who created one:

```python
@oapif.register(Observation)
class ObservationCollection(OapifCollection):
    readonly_fields = ("author",)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(author=request.user)

    def save_model(self, request, obj, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, change)
```

The [API reference](../api.md#django_oapif.OapifCollection) lists them all.
