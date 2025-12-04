---
hide:
  - navigation
---

# Custom authentication & permissions

By default the viewsets use [`DjangoModelPermissionsOrAnonReadOnly`] django_oapif.permissions.DjangoModelPermissionsOrAnonReadOnly.

This can be altered in the DRF settings by adapting `DEFAULT_PERMISSION_CLASSES`.

You can also add custom permissions when registering their corresponding viewsets, as [`permission_classes`] django_oapif.permissions.
Example in `models.py`:

```python
from django.contrib.gis.db import models
from django_oapif import OAPIF
from django_oapif.permissions import OAPIF, DjangoModelPermissionsOrAnonReadOnly

ogc_api = OAPIF()

@ogc_api.register(auth=DjangoModelPermissionsOrAnonReadOnly)
class MyModel(models.Model):
    ...
```
