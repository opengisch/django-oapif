from itertools import islice
from typing import Iterable, Tuple

from django.core.management import call_command
from django.test import TestCase

from .models import Azimuth, Pole, Sign


def is_dense(it: Iterable[int]) -> bool:
    prev = 0
    for i in sorted(it):
        if i != prev + 1:
            return False
        prev += 1
    return True


class TestOfficialSigns(TestCase):
    def setUp(self):
        call_command("populate_vl")
        call_command("populate_signs_poles")

    def test_instances_exist(self):
        number_of_signs = Sign.objects.all().count()
        number_of_azimuth = Azimuth.objects.all().count()
        self.assertGreater(number_of_azimuth, 0)
        self.assertGreater(number_of_signs, 0)

    def test_dense_orders_signs(self):
        for pole in Pole.objects.all():
            values_list = pole.signs.values_list("order")
            order = [o[0] if isinstance(o, Tuple) else o for o in values_list]
            if not is_dense(order):
                raise self.failureException(
                    f"{pole} does not have a dense order: {pole.signs}. Culprit: {order}"
                )

    def test_deletion_preserves_order_density(self):
        azimuths = Azimuth.objects.all()
        perc_10 = round(10 / 100 * azimuths.count())
        for az in islice(azimuths, perc_10):
            az.delete()
        self.test_dense_orders_signs()
