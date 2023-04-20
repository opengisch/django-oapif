import uuid

from computedfields.models import ComputedFieldsModel, computed
from django.conf import settings
from django.contrib.gis.db import models
from django.db import transaction
from django.db.models import signals
from django.dispatch import receiver
from django.utils.translation import gettext as _

from django_oapif.decorators import register_oapif_viewset
from signalo.value_lists.models import OfficialSignType


@register_oapif_viewset()
class Azimuth(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    value = models.SmallIntegerField(default=0, null=False, blank=False)


@receiver(signals.pre_delete, sender=Azimuth)
@transaction.atomic()
def ensure_sign_order_on_delete(sender, instance, *args, **kwargs):
    """
    Ensure dense ranking of Sign orders in spite of deletion of related Azimuth
    """
    signs_to_update = []
    for pole in Pole.objects.all():
        signs_on_pole = pole.signs
        using_azimuth = list(signs_on_pole.filter(azimuth__value=instance.value))
        if not using_azimuth:
            continue
        for i, sign in enumerate(
            signs_on_pole.exclude(azimuth__id=instance.id).order_by("azimuth__value")
        ):
            sign.order = i + 1
            signs_to_update.append(sign)
    Sign.objects.bulk_update(signs_to_update, ["order"])


@register_oapif_viewset()
class Pole(ComputedFieldsModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    geom = models.PointField(srid=settings.GEOMETRY_SRID, verbose_name=_("Geometry"))
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
    sign_type = models.ForeignKey(
        OfficialSignType,
        models.SET_NULL,
        blank=True,
        null=True,
        related_name="official_sign",
    )
    azimuth = models.ForeignKey(
        Azimuth,
        models.SET_NULL,
        blank=True,
        null=True,
        related_name="signs",
    )

    order = models.IntegerField(null=False, blank=False)

    @computed(
        models.PointField(
            srid=settings.GEOMETRY_SRID,
            verbose_name=_("Geometry"),
            null=True,
        ),
        depends=[("self", ["pole"]), ("pole", ["geom"])],
    )
    def geom(self):
        return self.pole.geom

    def save(self, *args, **kwargs):
        """
        Custom default value for instances set at initialization:
        sum of all other signs
        """
        if self.order is None:
            signs_on_pole = Pole.objects.get(id=self.pole.id).sign_set
            other_signs_on_pole = signs_on_pole.exclude(id=self.id)
            self.order = (
                other_signs_on_pole.filter(azimuth__value=self.azimuth.value).count()
                + 1
            )

        super().save(*args, **kwargs)
