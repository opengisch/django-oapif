from itertools import islice
from typing import Iterable, Tuple

from django.core.management import call_command
from rest_framework.test import APITestCase

from .models import Azimuth, Pole, Sign


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
        for pole in Pole.objects.all():
            values_list = pole.signs.values_list("order")
            order = sorted([o[0] if isinstance(o, Tuple) else o for o in values_list])
            if not is_dense_partial_order(order):
                raise self.failureException(
                    f"{pole} does not have a dense order: {pole.signs}. Culprit: {order}"
                )

    def test_deletion_preserves_order_density(self):
        azimuths = Azimuth.objects.all()
        azimuths_count = azimuths.count()
        perc_10 = round(10 / 100 * azimuths_count)
        self.assertGreater(azimuths_count, perc_10)
        for az in islice(azimuths, perc_10):
            az.delete()
        self.test_dense_orders_signs()

    def test_adding_api(self):
        pass

    def test_deleting_api(self):
        pass
