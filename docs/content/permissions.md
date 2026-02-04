---
hide:
  - navigation
---

# Custom authentication & permissions

By default the viewsets use [`DjangoModelPermissionsOrAnonReadOnly`](api/#django_oapif.handler.DjangoModelPermissionsOrAnonReadOnly).

Example:

```python
# models.py

from django.contrib.gis.db import models

class MyModel(models.Model):
    ...
```


```python
# ogc.py

from .models import MyModel
from django_oapif import OAPIF
from django_oapif.handler import DjangoModelPermissionsOrAnonReadOnly

ogc_api = OAPIF()

ogc_api.register(MyModel, handler=DjangoModelPermissionsOrAnonReadOnly)
```

It is also possible to write your own handler to implement custom permission or queryset logic. All `OapifCollection` functions have the same signature as django's `ModelAdmin`, meaning that logic can be shared between the two easily with a mixin class:

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
# ogc.py

from .models import MyModel
from django_oapif import OAPIF
from django_oapif.handler import DjangoModelPermissionsOrAnonReadOnly
from .permissions import MyModelPermissionsMixin

ogc_api = OAPIF()

class MyModelHandler(OapifCollection, MyModelPermissionsMixin):
  ...

ogc_api.register(MyModel, handler=MyModelHandler)
```
