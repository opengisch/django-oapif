---
hide:
  - navigation
---

# Custom authentication & permissions

By default the viewsets use [`DjangoModelPermissionsOrAnonReadOnly`](api/#django_oapif.handler.DjangoModelPermissionsOrAnonReadOnly).

You can also add custom permissions when registering their corresponding viewsets, as [`permission_classes`] django_oapif.permissions.
Example in `models.py`:

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
