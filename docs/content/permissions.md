---
hide:
  - navigation
---

# Custom authentication & permissions

By default the collection will be registered with [`OapifCollection`](api/#django_oapif.OapifCollection), which uses the same permissions logic as Django's `ModelAdmin`. Other utility classes are provided for common permissions patterns, such as [`AnonReadOnlyCollection`](api/#django_oapif.AnonReadOnlyCollection) which provides read-only access to the collection but protected create/update operations.

Example:

```python
# models.py

from django.contrib.gis.db import models

class MyModel(models.Model):
    ...
```


```python
# oapif.py

from .models import MyModel
from django_oapif import OAPIF
from django_oapif.handler import AnonReadOnlyCollection

oapif = OAPIF()

oapif.register_collection(MyModel, AnonReadOnlyCollection)
```

It is also possible to write your own collection handler to implement custom permission or queryset logic. `OapifCollection` implements most of django's `ModelAdmin` permission and query related functions, meaning that logic can be shared between the two easily with a mixin class:
```python
# permissions.py

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
class MyModelAdmin(admin.ModelAdmin, MyModelPermissionsMixin):
    ...
```

```python
# oapif.py

from .models import MyModel
from django_oapif import OAPIF
from django_oapif.handler import DjangoModelPermissionsOrAnonReadOnly
from .permissions import MyModelPermissionsMixin

oapif = OAPIF()

@oapif.register(MyModel)
class MyModelHandler(OapifCollection, MyModelPermissionsMixin):
  ...
```
