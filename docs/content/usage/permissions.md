# Authentication and permissions

## Authentication

By default, a request is authenticated as Django authenticates it: its user is the one logged in to the
Django site in its session, and it is anonymous otherwise. Writes with a session need the CSRF token of Django,
as Django forms do.

Clients such as QGIS authenticate with HTTP Basic instead, which `BasicAuth` checks against the
authentication backends of Django. Serve it over HTTPS only:

```python
from django_oapif import OAPIF
from django_oapif.auth import BasicAuth, DjangoAuth

oapif = OAPIF(auth=[BasicAuth(), DjangoAuth()])
```

`auth` takes any authentication of Django Ninja: see its
[documentation](https://django-ninja.dev/guides/authentication/).

## Permissions

The class a collection is registered with decides who may do what with its features, anonymous users
included:

| Class                                                                                                | Read                                                      | Write                                                    |
|------------------------------------------------------------------------------------------------------|-----------------------------------------------------------|----------------------------------------------------------|
| [`OapifCollection`](../api.md#django_oapif.OapifCollection), the default                             | users with the view or change permission of the model     | users with the add, change or delete permission          |
| [`AnonReadOnlyCollection`](../api.md#django_oapif.AnonReadOnlyCollection)                            | everyone                                                  | users with the add, change or delete permission          |
| [`AuthenticatedCollection`](../api.md#django_oapif.AuthenticatedCollection)                          | authenticated users                                       | authenticated users                                      |
| [`AuthenticatedOrReadOnlyCollection`](../api.md#django_oapif.AuthenticatedOrReadOnlyCollection)      | everyone                                                  | authenticated users                                      |
| [`AllowAnyCollection`](../api.md#django_oapif.AllowAnyCollection)                                    | everyone                                                  | everyone                                                 |

The permissions of `OapifCollection` are the model permissions of Django, which the admin site checks too:
`POST` takes the add permission, `PUT` and `PATCH` the change one, and `DELETE` the delete one.

```python
from django_oapif import OAPIF, AnonReadOnlyCollection

from .models import MyModel

oapif = OAPIF()

oapif.register_collection(MyModel, AnonReadOnlyCollection)
```

A collection that a user may not read is left out of the list of collections, and its other resources are
answered with a `403 Forbidden`, as are the writes they may not do. An `OPTIONS` request on
`/collections/{collectionId}/items`, or on one of its features, lists in its `Allow` header the methods that
the user may use.

## Custom permissions

To implement other permissions, override the `has_*_permission` methods of a collection. They are those of
Django's `ModelAdmin`, so the logic can be shared with the admin site in a mixin. Put it first in the bases,
so that its methods take precedence over those of `ModelAdmin` and `OapifCollection`:

```python
# permissions.py

from django.db.models import Model
from django.http import HttpRequest

class MyModelPermissionsMixin[M: Model]:
    def has_view_permission(self, request: HttpRequest, obj: M | None = None) -> bool:
        return my_custom_view_permission()

    def has_add_permission(self, request: HttpRequest, obj: M | None = None) -> bool:
        return my_custom_add_permission()

    def has_change_permission(self, request: HttpRequest, obj: M | None = None) -> bool:
        return my_custom_change_permission()

    def has_delete_permission(self, request: HttpRequest, obj: M | None = None) -> bool:
        return my_custom_delete_permission()
```

```python
# admin.py

from django.contrib import admin
from .models import MyModel
from .permissions import MyModelPermissionsMixin

@admin.register(MyModel)
class MyModelAdmin(MyModelPermissionsMixin, admin.ModelAdmin):
    ...
```

```python
# oapif.py

from .models import MyModel
from django_oapif import OAPIF, OapifCollection
from .permissions import MyModelPermissionsMixin

oapif = OAPIF()

@oapif.register(MyModel)
class MyModelHandler(MyModelPermissionsMixin, OapifCollection):
    ...
```
