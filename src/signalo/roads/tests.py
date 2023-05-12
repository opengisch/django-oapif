from django.core.management import call_command
from rest_framework.test import APITestCase

from .models import Road


class TestRoads(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("populate_roads")

    def test_geom(self):
        instances = list(Road.objects.all())
        self.assertGreater(len(instances), 0)
        wkbs = [instance.get_geom() for instance in instances]
        wkts = [instance.get_geom("wkt") for instance in instances]
        self.assertTrue(wkts)
        self.assertTrue(wkbs)
