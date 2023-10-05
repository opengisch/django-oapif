import math
import random
import string

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from tests.models import (
    Line_2056_10fields,
    NoGeom_10fields,
    Point_2056_10fields,
    Point_2056_10fields_local_json,
)


class Command(BaseCommand):
    help = "Populate db with testdata"

    def add_arguments(self, parser):
        parser.add_argument("-s", "--size", type=int, default=10000)

    @transaction.atomic
    def handle(self, *args, **options):
        """Populate db with testdata"""
        size = options["size"]
        x_start = 2508500
        y_start = 1152000
        step = 100

        magnitude = math.ceil(math.sqrt(size))

        points = []
        points_local_json = []
        lines = []
        no_geoms = []

        letters = string.ascii_lowercase

        for dx in range(magnitude):
            for dy in range(magnitude):
                x = x_start + dx * step
                y = y_start + dy * step
                geom_pt_wkt = f"Point({x:4f} {y:4f})"
                geom_line_wkt = f"LineString({x:4f} {y:4f}, {x+random.randint(10,50):4f} {y+random.randint(10,50):4f})"

                fields = {}
                for f in range(10):
                    fields[f"field_{f}"] = "".join(random.choice(letters) for i in range(10))

                no_geom = NoGeom_10fields(**fields)
                no_geoms.append(no_geom)

                fields["geom"] = geom_pt_wkt
                point = Point_2056_10fields(**fields)
                points.append(point)
                point_local_json = Point_2056_10fields_local_json(**fields)
                points_local_json.append(point_local_json)

                fields["geom"] = geom_line_wkt
                line = Line_2056_10fields(**fields)
                lines.append(line)

        # Create objects in batches
        Point_2056_10fields.objects.bulk_create(points)
        Point_2056_10fields_local_json.objects.bulk_create(points_local_json)
        NoGeom_10fields.objects.bulk_create(no_geoms)
        Line_2056_10fields.objects.bulk_create(lines)

        # Call 'update_data' to update computed properties
        call_command("updatedata")
        print(f"🤖 testdata added!")
