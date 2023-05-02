import logging
import uuid

from computedfields.models import ComputedFieldsModel, computed
from django.conf import settings
from django.contrib.gis.db import models
from django.db import transaction
from django.db.models import Sum, signals
from django.dispatch import receiver
from django.utils.translation import gettext as _

from django_oapif.decorators import register_oapif_viewset
from signalo.value_lists.models import OfficialSignType

logger = logging.getLogger(__name__)


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
class Azimuth(ComputedFieldsModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    value = models.SmallIntegerField(default=0, null=False, blank=False)
    pole = models.ForeignKey(
        Pole, on_delete=models.CASCADE, blank=False, null=False, related_name="azimuths"
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


@register_oapif_viewset()
class Sign(ComputedFieldsModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sign_type = models.ForeignKey(
        OfficialSignType,
        models.SET_NULL,
        blank=True,
        null=True,
        related_name="official_sign",
    )
    azimuth = models.ForeignKey(
        Azimuth, models.CASCADE, blank=False, null=False, related_name="signs"
    )
    order = models.IntegerField(null=False, blank=False)

    def save(self, *args, **kwargs):
        """
        Custom default value for instances set at initialization:
        sum of all other signs
        """
        if self.order is None:
            pole_id = self.azimuth.pole.id
            signs_on_pole = Sign.objects.filter(azimuth__pole__id=pole_id)
            other_signs_on_pole = signs_on_pole.exclude(id=self.id)
            self.order = (
                other_signs_on_pole.filter(azimuth__value=self.azimuth.value).count()
                + 1
            )

        super().save(*args, **kwargs)

    @computed(
        models.PointField(
            srid=settings.GEOMETRY_SRID,
            verbose_name=_("Geometry"),
            null=True,
        ),
        depends=[
            ("self", ["azimuth"]),
            ("azimuth", ["geom"]),
        ],
    )
    def geom(self):
        return self.azimuth.geom

    @computed(
        models.IntegerField(default=0),
        depends=[
            ("self", ["azimuth"]),
            ("sign_type", ["img_height"]),
        ],
    )
    def offset_px(self) -> int:
        default_padding_px = 5
        previous_signs_on_pole = Sign.objects.filter(
            azimuth__pole__id=self.azimuth.pole.id, order__lt=self.order
        )
        sum_heights = (
            previous_signs_on_pole.aggregate(height=Sum("sign_type__img_height"))[
                "height"
            ]
            or 0
        )
        return (
            previous_signs_on_pole.count() * default_padding_px
            + default_padding_px
            + sum_heights
        )


@receiver(signals.pre_delete, sender=Sign)
@transaction.atomic()
def ensure_sign_order_on_delete(sender, instance, *args, **kwargs):
    """
    Ensure dense ranking of sign orders despite deletions on same pole
    """
    pole_id = instance.azimuth.pole.id
    signs_on_pole = Sign.objects.filter(azimuth__pole__id=pole_id)

    signs_to_update = []
    for new_order, sign in enumerate(
        signs_on_pole.exclude(id=instance.id).order_by("order"), 1
    ):
        sign.order = new_order
        signs_to_update.append(sign)

    Sign.objects.bulk_update(signs_to_update, ["order"])
    logger.debug(
        f"Sign {instance.id} is about to get deleted! Updated {len(signs_to_update)} signs to avoid gappy or missing order."
    )
