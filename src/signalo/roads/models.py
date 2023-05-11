import uuid

from django.db import models
from django.db.models import fields

from django_oapif.decorators import register_oapif_viewset


@register_oapif_viewset()
class Road(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = fields.BinaryField()
