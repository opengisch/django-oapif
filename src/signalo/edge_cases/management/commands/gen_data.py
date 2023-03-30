from django.db import transaction

from ....core.management.commands.gen_data import Command as OriginalGenDataCommand
from ...models import VariousGeom


class Command(OriginalGenDataCommand):
    """Calls the original gen_data command, but adds some edge case test data"""

    def add_arguments(self, parser):
        parser.add_argument("-m", "--magnitude", type=int, default=10)

    @transaction.atomic
    def handle(self, *args, **options):
        super().handle(*args, **options)

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
        print(f"🐻 edgecase testdata added!")
