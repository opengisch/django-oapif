import datetime
import math
import random
import string
import uuid
from copy import deepcopy
from typing import Any

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection, transaction
from django_oapif_tests.tests.models import (
    Arc_2056_10fields,
    CurvePolygon_2056,
    LayerWithDate,
    LayerWithForeignKey,
    Line_2056_10fields,
    NoGeom_10fields,
    NoGeom_100fields,
    Point_2056_10fields,
    SecretLayer,
)


class Command(BaseCommand):
    help = "Populate db with testdata"

    def add_arguments(self, parser):
        parser.add_argument("-s", "--size", type=int, default=1000)

    @transaction.atomic
    def handle(self, *args, **options):
        """Populate db with testdata"""
        size = options["size"]
        x_start = 2508500
        y_start = 1152000
        step = 100

        magnitude = math.ceil(math.sqrt(size))

        points = []
        secret_points = []
        lines = []
        arcs = []
        curve_polygons = []
        no_geoms = []
        no_geoms_100fields = []

        letters = string.ascii_lowercase

        for dx in range(magnitude):
            for dy in range(magnitude):
                x = x_start + dx * step
                y = y_start + dy * step
                geom_pt_wkt = f"Point({x:4f} {y:4f})"
                geom_line_wkt = (
                    f"LineString("
                    f"{x:4f} {y:4f}, "
                    f"{x + random.randint(10, 50):4f} {y + random.randint(10, 50):4f},"
                    f"{x + random.randint(10, 50):4f} {y + random.randint(10, 50):4f})"
                )
                circularstring_wkt = (
                    f"CircularString("
                    f"{x:4f} {y:4f}, "
                    f"{x + random.randint(10, 50):4f} {y + random.randint(10, 50):4f},"
                    f"{x + random.randint(10, 50):4f} {y + random.randint(10, 50):4f})"
                )

                fields: dict[str, Any] = {"field_int": random.randint(1, 999)}
                for f in range(10):
                    fields[f"field_str_{f}"] = "".join(random.choice(letters) for i in range(10))

                no_geom = NoGeom_10fields(**fields)
                no_geoms.append(no_geom)

                no_geom_100fields = deepcopy(fields)
                for f in range(90):
                    no_geom_100fields[f"field_str_{10 + f}"] = "".join(random.choice(letters) for i in range(10))
                no_geom_100fields = NoGeom_100fields(**no_geom_100fields)
                no_geoms_100fields.append(no_geom_100fields)

                fields["geom"] = geom_pt_wkt
                point = Point_2056_10fields(**fields)
                points.append(point)
                secret_point = SecretLayer(**fields)
                secret_points.append(secret_point)

                fields["geom"] = geom_line_wkt
                line = Line_2056_10fields(**fields)
                lines.append(line)

                arcs.append((uuid.uuid4(), circularstring_wkt))
                # a square with a rounded corner
                size, radius = random.randint(20, 50), random.randint(5, 15)
                curve_polygon_wkt = (
                    f"CurvePolygon(CompoundCurve(("
                    f"{x} {y}, {x + size} {y}, {x + size} {y + size - radius}), "
                    f"CircularString({x + size} {y + size - radius}, "
                    f"{x + size - radius * (1 - math.sqrt(0.5)):4f} {y + size - radius * (1 - math.sqrt(0.5)):4f}, "
                    f"{x + size - radius} {y + size}), "
                    f"({x + size - radius} {y + size}, {x} {y + size}, {x} {y})))"
                )
                curve_polygons.append((
                    uuid.uuid4(),
                    "".join(random.choice(letters) for i in range(10)),
                    curve_polygon_wkt,
                ))

        # Create objects in batches
        # The GEOS version used by geodjango does not support curves
        arc_table_name = connection.ops.quote_name(Arc_2056_10fields._meta.db_table)
        curve_polygon_table_name = connection.ops.quote_name(CurvePolygon_2056._meta.db_table)
        with connection.cursor() as cursor:
            cursor.executemany(
                f"INSERT INTO {arc_table_name} (id, geom) VALUES (%s, ST_GeomFromText(%s, 2056))",
                [(arc_id, wkt) for arc_id, wkt in arcs],
            )
            cursor.executemany(
                f"INSERT INTO {curve_polygon_table_name} (id, name, geom) VALUES (%s, %s, ST_GeomFromText(%s, 2056))",
                curve_polygons,
            )
        Point_2056_10fields.objects.bulk_create(points, batch_size=10000)
        SecretLayer.objects.bulk_create(secret_points, batch_size=10000)
        NoGeom_10fields.objects.bulk_create(no_geoms, batch_size=10000)
        NoGeom_100fields.objects.bulk_create(no_geoms_100fields, batch_size=10000)
        Line_2056_10fields.objects.bulk_create(lines, batch_size=10000)
        LayerWithForeignKey.objects.create(point=Point_2056_10fields.objects.first())
        LayerWithDate.objects.create(date=datetime.date.today(), time=datetime.datetime.now(datetime.UTC))
        # Call 'update_data' to update computed properties
        call_command("updatedata")
        print("🤖 testdata added!")
