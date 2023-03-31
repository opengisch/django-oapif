from django.core.management.base import BaseCommand
from django.db import transaction

from ...models import DifferentSrid, HighlyPaginated, VariousGeom


class Command(BaseCommand):
    """Adds some edge case test data"""

    def add_arguments(self, parser):
        parser.add_argument("-m", "--magnitude", type=int, default=10)

    @transaction.atomic
    def handle(self, *args, **options):
        x = 2508500
        y = 1152000
        step = 100
        halfstep = 0.5 * step
        fourthstep = 0.25 * step
        VariousGeom.objects.create(
            geom=f"Polygon(({x:4f} {y:4f}, {x+fourthstep:4f} {y+fourthstep:4f}, {x+halfstep:4f} {y:4f}, {x:4f} {y:4f}))",
        )
        VariousGeom.objects.create(
            geom=f"Linestring({x:4f} {y:4f}, {x+fourthstep:4f} {y+fourthstep:4f}, {x+halfstep:4f} {y:4f})",
        )
        VariousGeom.objects.create(
            geom=f"Point({x:4f} {y:4f})",
        )

        for i in range(100):
            HighlyPaginated.objects.create(
                geom=f"Point({x+i*step:4f} {y:4f})",
            )

        DifferentSrid.objects.create(geom=f"Point(1150000 6600000)")

        print(f"🐻 edgecase testdata added!")
