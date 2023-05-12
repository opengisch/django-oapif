from django.contrib.gis.db.models.functions import AsWKB
from django.core.management import call_command
from django.db import connection
from rest_framework.test import APITestCase

from ..settings import GEOMETRY_SRID
from .models import Road


class TestRoads(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("populate_roads")

    def test_geom_wkb(self):
        wkbs = Road.objects.annotate(wkb=AsWKB("geom")).values_list("wkb", flat=True)
        self.assertGreater(len(wkbs), 1000)

    def test_geom_fgb(self):
        instances = Road.objects.all()[:1000]
        pks = tuple([instance.id for instance in instances])
        with connection.cursor() as cur:
            # FIXME: This query is almost valid!
            query = """
                WITH rows AS (SELECT ST_GeomFromText(geom, %s) FROM signalo_roads_road WHERE id IN %s)
                SELECT encode(ST_AsFlatGeobuf(rows), 'base64') FROM rows
            """
            cur.execute(
                query,
                (
                    GEOMETRY_SRID,
                    pks,
                ),
            )
            self.assertGreater(len(list(cur)), 1000)
