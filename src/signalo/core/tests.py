import cProfile
import logging
import os
import pstats
from itertools import islice
from typing import Callable, Iterable, Tuple

from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.test import APITestCase

from signalo.core.views import PoleSerializer

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
    @classmethod
    def setUpTestData(cls):
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


def serialize_with_profile(
    objects, serializer: Callable
) -> Tuple[cProfile.Profile, str]:
    with cProfile.Profile() as profile:
        for object in objects:
            _ = serializer(object).data
    return profile, serializer.__name__


class SpeedTestSerialization(APITestCase):
    @classmethod
    def setUpClass(cls):
        call_command("populate_vl")
        call_command("populate_signs_poles", magnitude=30)
        cls.poles = Pole.objects.all()
        cls.path = os.path.abspath("/unit_tests_outputs")
        super().setUpClass()

    def test_data(self):
        self.assertEqual(self.poles.count(), 900)

    def test_with_poleserializer(self):
        profile, name = serialize_with_profile(self.poles, PoleSerializer)
        path_to_bin = os.path.join(
            self.path,
            f"{name}.prof",
        )
        profile.dump_stats(path_to_bin)
        with open(os.path.join(self.path, f"{name}.txt"), "w") as fh:
            stats = pstats.Stats(path_to_bin, stream=fh)
            stats.print_stats()


class TestBasicAuth(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("populate_vl")
        call_command("populate_signs_poles")
        call_command("populate_users")

        cls.demo_viewer = User.objects.get(username="demo_viewer")
        cls.admin = User.objects.get(username="admin")

    def tearDown(self):
        self.client.force_authenticate(user=None)

    def test_auth_as_demo_viewer(self):
        collections_from_anonymous = self.client.get(
            "/oapif/collections", format="json"
        ).json()
        self.client.force_authenticate(user=self.demo_viewer)
        collection_response = self.client.get("/oapif/collections", format="json")
        oapif_response_code = self.client.get("/oapif/").status_code

        self.assertEqual(oapif_response_code, 200)
        self.assertEqual(collection_response.status_code, 200)
        self.assertEqual(
            len(collection_response.json()), len(collections_from_anonymous)
        )

    def test_auth_as_admin(self):
        collections_from_anonymous = self.client.get(
            "/oapif/collections", format="json"
        ).json()
        self.client.force_authenticate(user=self.admin)
        collection_response = self.client.get("/oapif/collections", format="json")
        oapif_response_code = self.client.get("/oapif/").status_code

        self.assertEqual(oapif_response_code, 200)
        self.assertEqual(collection_response.status_code, 200)
        self.assertEqual(
            len(collection_response.json()), len(collections_from_anonymous)
        )
