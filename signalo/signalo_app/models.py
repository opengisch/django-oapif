import uuid

from computedfields.models import ComputedFieldsModel, computed
from django.contrib.gis.db import models
from django.utils.translation import gettext as _

SRID = 4326


class Pole(ComputedFieldsModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField(srid=SRID, verbose_name=_("Geometry"))
    name = models.CharField(max_length=255, verbose_name=_("Name"))


class Sign(ComputedFieldsModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pole = models.ForeignKey(
        Pole, on_delete=models.CASCADE, blank=True, null=True, related_name="signs"
    )
    order = models.IntegerField(default=1)

    @computed(
        models.PointField(srid=SRID, verbose_name=_("Geometry"), null=True),
        depends=[("self", ["pole"]), ("pole", ["geom"])],
    )
    def geom(self):
        return self.pole.geom
