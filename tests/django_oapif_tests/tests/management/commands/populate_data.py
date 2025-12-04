import math
import random
import string
from copy import deepcopy

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django_oapif_tests.tests.models import (
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
                    f"{x+random.randint(10,50):4f} {y+random.randint(10,50):4f})"
                    f"{x+random.randint(10,50):4f} {y+random.randint(10,50):4f})"
                )

                fields = {"field_int": random.randint(1, 999)}
                for f in range(10):
                    fields[f"field_str_{f}"] = "".join(random.choice(letters) for i in range(10))

                no_geom = NoGeom_10fields(**fields)
                no_geoms.append(no_geom)

                no_geom_100fields = deepcopy(fields)
                for f in range(90):
                    no_geom_100fields[f"field_str_{10+f}"] = "".join(random.choice(letters) for i in range(10))
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

        # Create objects in batches
        Point_2056_10fields.objects.bulk_create(points, batch_size=10000)
        SecretLayer.objects.bulk_create(secret_points, batch_size=10000)
        NoGeom_10fields.objects.bulk_create(no_geoms, batch_size=10000)
        NoGeom_100fields.objects.bulk_create(no_geoms_100fields, batch_size=10000)
        Line_2056_10fields.objects.bulk_create(lines, batch_size=10000)

        # Call 'update_data' to update computed properties
        call_command("updatedata")
        print("🤖 testdata added!")
