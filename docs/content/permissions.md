# Custom authentication & permissions

By default the viewsets use `DjangoModelPermissionsOrAnonReadOnly` [permissions class from DRF](https://www.django-rest-framework.org/api-guide/permissions/#djangomodelpermissionsoranonreadonly).

This can be altered in the DRF settings by adapting `DEFAULT_PERMISSION_CLASSES`.

You can also add custom permissions when registering their corresponding viewsets, as [`permission_classes`](https://www.django-rest-framework.org/api-guide/permissions/#api-reference). Example:

```python
models.py
---------
from rest_framework import permissions
from django.contrib.gis.db import models
from django_oapif import register_oapif_viewset


@register_oapif_viewset(
    custom_viewset_attrs={
        "permission_classes": (permissions.DjangoModelPermissionsOrAnonReadOnly,)
    }
)
class MyModel(models.Model):
    ...
```
