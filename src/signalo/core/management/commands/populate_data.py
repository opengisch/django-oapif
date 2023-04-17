import random

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from signalo.core.models import Azimuth, Pole, Sign
from signalo.value_lists.models import OfficialSignType


class Command(BaseCommand):
    help = "Populate db with testdata"

    def add_arguments(self, parser):
        parser.add_argument("-m", "--magnitude", type=int, default=10)

    @transaction.atomic
    def handle(self, *args, **options):
        """Populate db with testdata"""
        magnitude = options["magnitude"]

        x_start = 2508500
        y_start = 1152000
        step = 100

        signs_per_pole = 3
        poles = []
        signs = []
        sign_types = list(OfficialSignType.objects.all())
        sample_azimuths = [x * 5 for x in range(72)]

        for dx in range(0, magnitude):
            for dy in range(0, magnitude):
                # poles
                x = x_start + dx * step
                y = y_start + dy * step
                geom_wkt = f"Point({x:4f} {y:4f})"
                name = f"{dx}-{dy}"
                pole_instance = Pole(geom=geom_wkt, name=name)
                poles.append(pole_instance)

                # signs

                for s in range(0, signs_per_pole):
                    order = s + 1
                    signs.append(
                        Sign(
                            order=order,
                            pole=pole_instance,
                            sign_type=random.sample(sign_types, 1)[0],
                            azimuth=Azimuth.objects.create(
                                value=random.sample(sample_azimuths, 1)
                            ),
                        )
                    )

        # Create objects in batches
        Pole.objects.bulk_create(poles)
        Sign.objects.bulk_create(signs)

        # Call 'update_data' to update computed properties
        call_command("updatedata")

        print(f"🤖 testdata added!")
