from django.core.management import BaseCommand
from django.db import transaction

from ...models import (
    DifferentSrid,
    HighlyPaginated,
    SimpleGeom,
    TestPermissionAllowAny,
    TestPermissionDefaultPermissionsSettings,
    TestPermissionIsAdminUserModel,
    VariousGeom,
)
from ...models import DifferentSrid, HighlyPaginated, SimpleGeom, VariousGeom


class Command(BaseCommand):
    """Adds some edge case test data"""

    @transaction.atomic
    def handle(self, *args, **options):
        # Add additional test data

        x = 7.4474
        y = 46.9480
        step = 0.1

        # Create data for SimpleGeom
        SimpleGeom.objects.create(geom=f"Point({x} {y})")

        # Create data for VariousGeom
        halfstep = 0.5 * step
        fourthstep = 0.25 * step
        VariousGeom.objects.create(
            geom=f"Polygon(({x} {y}, {x+fourthstep} {y+fourthstep}, {x+halfstep} {y}, {x} {y}))",
        )
        VariousGeom.objects.create(
            geom=f"Linestring({x} {y}, {x+fourthstep} {y+fourthstep}, {x+halfstep} {y})",
        )
        VariousGeom.objects.create(
            geom=f"Point({x} {y})",
        )

        # Create data for HighlyPaginated
        for i in range(100):
            HighlyPaginated.objects.create(geom=f"Point({x+i*step} {y})")

        # Create data for DifferentSrid
        DifferentSrid.objects.create(geom=f"Point(2600000 1200000)")

        # Create data for models whose permissions we are testing against
        TestPermissionAllowAny.objects.create(geom=f"Point(2600000 1200000)")
        TestPermissionDefaultPermissionsSettings.objects.create(
            geom=f"Point(2600000 1200000)"
        )
        TestPermissionIsAdminUserModel.objects.create(geom=f"Point(2600000 1200000)")

        print(f"🐻 Edge cases test data added too!")
