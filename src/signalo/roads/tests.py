from django.contrib.gis.db.models.functions import AsWKB
from django.core.management import call_command
from django.db import connection
from psycopg2 import sql
from rest_framework.test import APITestCase

from .models import Road


class TestRoads(APITestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("populate_roads")

    def test_valid(self):
        query = "SELECT ST_IsValid(geom) FROM signalo_roads_road"
        with connection.cursor() as cur:
            cur.execute(query)

    def test_geom_wkb_with_geodjango(self):
        wkbs = Road.objects.annotate(wkb=AsWKB("geom")).values_list("wkb", flat=True)
        self.assertGreater(len(wkbs), 1000)

    def test_geom_wkb(self):
        instances = Road.objects.all()[:1000]
        ids = tuple([instance.id for instance in instances])
        with connection.cursor() as cur:
            query = sql.SQL(
                "SELECT ST_AsBinary(geom) FROM {table} WHERE id IN %s"
            ).format(table=sql.Identifier(Road._meta.db_table))
            cur.execute(query, (ids,))
            entries = cur.fetchall()
            self.assertEqual(len(entries), 1000)

    def test_geom_fgb(self):
        instances = Road.objects.all()[:1000]
        pks = tuple([instance.id for instance in instances])
        with connection.cursor() as cur:
            query = sql.SQL(
                """
                WITH rows AS (SELECT geom FROM {table} WHERE id IN %s)
                SELECT encode(ST_AsFlatGeobuf(rows), 'base64') FROM rows
            """
            ).format(table=sql.Identifier(Road._meta.db_table))
            cur.execute(query, (pks,))
            entries = cur.fetchall()
            # Should be a single entity
            self.assertEqual(len(entries), 1)
