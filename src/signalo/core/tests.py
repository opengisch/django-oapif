import logging
from itertools import islice
from typing import Iterable, Tuple

from django.core.management import call_command
from rest_framework.test import APITestCase

from .models import Azimuth, Pole, Sign

logger = logging.getLogger(__name__)


def is_dense_partial_order(sorted_it: Iterable[int]) -> bool:
    prev = 0
    for i in sorted_it:
        if i == prev + 1:
            prev += 1
            continue
        elif i == prev:
            continue
        else:
            return False
    return True


class TestValuesListSignsPoles(APITestCase):
    def setUp(self):
        call_command("populate_vl")
        call_command("populate_signs_poles")

    def test_instances_exist(self):
        number_of_signs = Sign.objects.all().count()
        number_of_azimuth = Azimuth.objects.all().count()
        self.assertGreater(number_of_azimuth, 0)
        self.assertGreater(number_of_signs, 0)

    def test_dense_orders_signs(self):
        poles = Pole.objects.all()
        azimuths = Azimuth.objects.all()
        signs = Sign.objects.all()

        for pole in poles:
            azimuths_ids_on_pole = azimuths.filter(pole=pole).values_list("pk")
            signs_on_pole = signs.filter(azimuth__id__in=azimuths_ids_on_pole)
            signs_orders_on_pole = signs_on_pole.values_list("order")
            order = sorted(
                [o[0] if isinstance(o, Tuple) else o for o in signs_orders_on_pole]
            )
            if not is_dense_partial_order(order):
                raise self.failureException(
                    f"{pole} does not have a dense order: {order}"
                )

    def test_deletion_preserves_order_density_first(self):
        poles = Pole.objects.all()
        perc_10 = round(10 / 100 * poles.count())
        self.assertGreater(poles.count(), perc_10)

        for pole in islice(poles, perc_10):
            signs = Sign.objects.filter(azimuth__pole__id=pole.id, order=1)
            for found in signs:
                found.delete()

        logger.info(f"Deleted {perc_10} signs; checking order density")
        self.test_dense_orders_signs()

    def test_deletion_preserves_order_density_second(self):
        poles = Pole.objects.all()
        perc_10 = round(10 / 100 * poles.count())
        self.assertGreater(poles.count(), perc_10)

        for pole in islice(poles, perc_10):
            signs = Sign.objects.filter(azimuth__pole__id=pole.id, order=2)
            for found in signs:
                found.delete()

        logger.info(f"Deleted {perc_10} signs; checking order density")
        self.test_dense_orders_signs()

    def test_deletion_preserves_order_density_last(self):
        poles = Pole.objects.all()
        perc_10 = round(10 / 100 * poles.count())
        self.assertGreater(poles.count(), perc_10)

        for pole in islice(poles, perc_10):
            signs_on_pole = Sign.objects.filter(azimuth__pole__id=pole.id)
            last = signs_on_pole.count()
            signs = signs_on_pole.filter(order=last)
            for sign in signs:
                sign.delete()

        logger.info(f"Deleted {perc_10} signs; checking order density")
        self.test_dense_orders_signs()
