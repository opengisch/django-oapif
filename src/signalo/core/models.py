import uuid
from os import environ

from computedfields.models import ComputedFieldsModel, computed
from django.contrib.gis.db import models
from django.utils.translation import gettext as _

from django_oapif.decorators import register_oapif_viewset


@register_oapif_viewset()
class Pole(ComputedFieldsModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField(
        srid=int(environ["GEOMETRY_SRID"]), verbose_name=_("Geometry")
    )
    name = models.CharField(max_length=255, verbose_name=_("Name"))

    @computed(
        models.CharField(null=True, max_length=1000),
        depends=[("self", ["id", "geom", "name"])],
    )
    def _serialized(self):
        return f'{{"id": "{str(self.id)}", "type": "Feature", "geometry": {self.geom.geojson}, "properties": {{"name": "{self.name}"}}}}'


@register_oapif_viewset()
class Sign(ComputedFieldsModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    pole = models.ForeignKey(
        Pole, on_delete=models.CASCADE, blank=True, null=True, related_name="signs"
    )
    order = models.IntegerField(default=1)

    @computed(
        models.PointField(
            srid=int(environ["GEOMETRY_SRID"]),
            verbose_name=_("Geometry"),
            null=True,
        ),
        depends=[("self", ["pole"]), ("pole", ["geom"])],
    )
    def geom(self):
        return self.pole.geom
