import uuid
from functools import reduce

from computedfields.models import ComputedFieldsModel, computed
from django.conf import settings
from django.contrib.gis.db import models
from django.db import transaction
from django.db.models import F, signals
from django.dispatch import receiver
from django.utils.translation import gettext as _

from django_oapif.decorators import register_oapif_viewset
from signalo.value_lists.models import OfficialSignType


@register_oapif_viewset()
class Azimuth(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    value = models.SmallIntegerField(default=0, null=False, blank=False)

    @transaction.atomic()
    def save(self, *args, **kwargs):
        """
        Increment rank of Signs referencing this instance after atomically
        saving the azimuth instance.
        See https://github.com/opengisch/signalo/blob/0cda9329a6718c2d47a90aff6ecbbcab15f809c1/data_model/changelogs/0001/0001_1.sql#L1357
        and https://github.com/opengisch/signalo/blob/0cda9329a6718c2d47a90aff6ecbbcab15f809c1/data_model/changelogs/0001/0001_1.sql#L36-L50
        """
        super().save(*args, **kwargs)
        (
            Sign.objects.filter(azimuth__id=self.id)
            .order_by("order")
            .update(order=F("order") + 1)
        )


@receiver(signals.pre_delete, sender=Azimuth)
@transaction.atomic()
def re_order_on_delete(sender, my_azimuth, *args, **kwargs):
    """
    Bump to last rank with respect to their common pole
    all signs such that any of the sign on that pole references a deleted azimuth.
    See https://github.com/opengisch/signalo/blob/0cda9329a6718c2d47a90aff6ecbbcab15f809c1/data_model/changelogs/0001/0001_1.sql#L1343
    and https://github.com/opengisch/signalo/blob/0cda9329a6718c2d47a90aff6ecbbcab15f809c1/data_model/changelogs/0001/0001_1.sql#L56-L63
    """

    # FIXME This is likely very inefficient without using pre_fetch or fetch_related
    def collect(acc, sign):
        acc[0].add(sign.azimuth.value)
        acc[1].add(sign.order)
        return acc

    signs = Sign.objects.all()
    poles = Pole.objects.all()

    for pole in poles:
        signs_on_pole = signs.filter(pole__id=pole.id)
        azimuths, orders = reduce(collect, signs_on_pole, (set(), set()))

        if my_azimuth.value in azimuths:
            signs_on_pole.filter(azimuth__id=my_azimuth.id).update(
                order=max(orders) + 1
            )


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
        related_name="azimuths",
        related_query_name="azimuth",
    )
    order = models.IntegerField(default=1)

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
