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

    def test_deletion_preserves_order_density(self):
        signs = Sign.objects.all()
        signs_count = signs.count()
        perc_10 = round(10 / 100 * signs_count)
        self.assertGreater(signs_count, perc_10)
        for sig in islice(signs, perc_10):
            sig.delete()
        print(f"Deleted {perc_10} signs; checking order density")
        self.test_dense_orders_signs()
