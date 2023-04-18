import uuid

from computedfields.models import ComputedFieldsModel, computed
from django.conf import settings
from django.contrib.gis.db import models
from django.db import transaction
from django.db.models import Count, Q, signals
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
def ensure_sign_order_on_delete(sender, my_azimuth, *args, **kwargs):
    """
    Bump to last rank with respect to their common pole
    all signs such that any of the sign on that pole references a deleted azimuth.
    See https://github.com/opengisch/signalo/blob/0cda9329a6718c2d47a90aff6ecbbcab15f809c1/data_model/changelogs/0001/0001_1.sql#L1343
    and https://github.com/opengisch/signalo/blob/0cda9329a6718c2d47a90aff6ecbbcab15f809c1/data_model/changelogs/0001/0001_1.sql#L56-L63
    """
    # FIXME This is likely very inefficient without using pre_fetch or fetch_related

    signs = Sign.objects.all()
    poles = Pole.objects.all()

    for pole in poles:
        signs_on_pole = signs.filter(pole__id=pole.id)
        azimuths_used_on_pole = signs_on_pole.values_list("order")
        gen_reorder = iter(range(len(signs_on_pole)))

        if my_azimuth.value in azimuths_used_on_pole:
            signs_on_pole.order_by("order").asc().update(order=next(gen_reorder))


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
    order = models.IntegerField(
        default=Count("signs", filter=Q(signs__pole=pole)) + 1, null=False, blank=False
    )

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
