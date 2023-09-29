import cProfile
import inspect
import io
import logging
import os
import pstats
from itertools import islice
from operator import itemgetter
from timeit import default_timer
from typing import Callable, Iterable, Tuple

import fiona
from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.test import APITestCase

from django_oapif.renderers import FGBRenderer
from signalo.core.models import Azimuth, Pole, Sign
from signalo.core.views import PoleSerializer

logger = logging.getLogger(__name__)

collections_url = "/oapif/collections"


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
            order = sorted([o[0] if isinstance(o, Tuple) else o for o in signs_orders_on_pole])
            if not is_dense_partial_order(order):
                raise self.failureException(f"{pole} does not have a dense order: {order}")

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


def serialize_with_profile(objects, serializer: Callable) -> Tuple[cProfile.Profile, str]:
    with cProfile.Profile() as profile:
        for object in objects:
            _ = serializer(object).data
    return profile, serializer.__name__


class SpeedTestSerialization(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("populate_vl")
        call_command("populate_signs_poles", magnitude=30)
        cls.poles = Pole.objects.all()
        cls.path = os.path.abspath("/unit_tests_outputs")

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
        cls.collection_url = collections_url + "/signalo_core.pole"
        cls.items_url = cls.collection_url + "/items"

    def tearDown(self):
        self.client.force_authenticate(user=None)

    def test_get_as_viewer(self):
        collections_from_anonymous = self.client.get(collections_url, format="json").json()
        self.client.force_authenticate(user=self.demo_viewer)
        collection_response = self.client.get(collections_url, format="json")

        self.assertEqual(collection_response.status_code, 200)
        self.assertEqual(len(collection_response.json()), len(collections_from_anonymous))

    def test_post_as_admin(self):
        self.client.force_authenticate(user=self.admin)
        data = {"geom": "Point(1300000 600000)", "name": "test123"}
        post_to_items = self.client.post(self.items_url, data, format="json")
        self.assertIn(post_to_items.status_code, (200, 201))

    def test_anonymous_items_options(self):
        # Anonymous user
        expected = {"GET", "OPTIONS", "HEAD"}
        response = self.client.options(self.items_url)

        allowed_headers = set(s.strip() for s in response.headers["Allow"].split(","))
        allowed_body = set(response.json()["actions"].keys())

        self.assertEqual(allowed_body, expected)
        self.assertEqual(allowed_headers, allowed_body)

    def test_admin_items_options(self):
        # Authenticated user with admin permissions
        expected = {"POST", "GET", "OPTIONS", "HEAD"}
        self.client.force_authenticate(user=self.admin)
        response = self.client.options(self.items_url)

        allowed_headers = set(s.strip() for s in response.headers["Allow"].split(","))
        allowed_body = set(response.json()["actions"].keys())

        self.assertEqual(allowed_body, expected)
        self.assertEqual(allowed_headers, allowed_body)


class TestRenderers(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("populate_vl")
        call_command("populate_signs_poles")

        cls.collection_url = collections_url + "/signalo_core.pole"
        cls.items_url = cls.collection_url + "/items"

    def test_flatgeobuf(self):
        json_features = self.client.get(self.items_url, {"format": "json"}).json()["features"]
        json_coordinates = [tuple(json_feature["geometry"]["coordinates"]) for json_feature in json_features]
        output_stream = io.BytesIO(self.client.get(self.items_url, {"format": "fgb"}, streaming=True).content)

        with fiona.open(output_stream, mode="r", driver="FlatGeobuf", schema=FGBRenderer.schema) as fgb_features:
            fgb_coordinates = [fgb_feature.geometry["coordinates"] for fgb_feature in fgb_features]

        self.assertEqual(
            set(fgb_coordinates),
            set(json_coordinates),
            msg="The two sources map to the same set of coordinates.",
        )

        fgb_coordinates.sort(key=itemgetter(0, 1))
        json_coordinates.sort(key=itemgetter(0, 1))

        self.assertEqual(
            fgb_coordinates,
            json_coordinates,
            msg="Once sorted, the two sources map to the same list of coordinates.",
        )


class TestJSON(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.timings = {}

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        p = os.path.abspath("/unit_tests_outputs/rendering_performance.txt")
        with open(p, "a+") as fh:
            for k, v in cls.timings.items():
                fh.write(f"{k}: {v}")

    @classmethod
    def setUpTestData(cls):
        call_command("populate_roads")
        cls.collection_url = collections_url + "/signalo_roads.road"
        cls.items_url = cls.collection_url + "/items"

    def test_roads_json(self):
        t0 = default_timer()
        response_content = self.client.get(self.items_url, {"format": "json"}).content
        t1 = default_timer()

        self.assertTrue(response_content)
        self.timings[inspect.currentframe().f_code.co_name] = round(t1 - t0, 2)

    def test_roads_json_streaming(self):
        t0 = default_timer()
        response_content = self.client.get(
            self.items_url, {"format": "json", "streaming": True}, streaming=True
        ).content
        t1 = default_timer()

        self.assertTrue(response_content)
        self.timings[inspect.currentframe().f_code.co_name] = round(t1 - t0, 2)


class TestFGB(APITestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.timings = {}

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        p = os.path.abspath("/unit_tests_outputs/rendering_performance.txt")
        with open(p, "a+") as fh:
            for k, v in cls.timings.items():
                fh.write(f"{k}: {v}")

    @classmethod
    def setUpTestData(cls):
        call_command("populate_roads")
        cls.collection_url = collections_url + "/signalo_roads.road"
        cls.items_url = cls.collection_url + "/items"

    def test_roads_fgb(self):
        t0 = default_timer()
        FGBRenderer.schema = {"geometry": "MultiLineString", "properties": {}}
        response_content = self.client.get(self.items_url, {"format": "fgb"}, streaming=True).content
        t1 = default_timer()

        self.assertTrue(response_content)
        self.timings[inspect.currentframe().f_code.co_name] = round(t1 - t0, 2)
