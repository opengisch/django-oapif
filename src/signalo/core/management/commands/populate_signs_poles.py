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
        azimuths_per_pole = 3
        signs_per_azimuth = 4
        all_possible_sign_types = list(OfficialSignType.objects.all())
        all_possible_azimuths = [x * 5 for x in range(72)]

        poles = []
        signs = []
        azimuths = []
        for dx in range(magnitude):
            for dy in range(magnitude):
                # poles
                x = x_start + dx * step
                y = y_start + dy * step
                geom_wkt = f"Point({x:4f} {y:4f})"
                name = f"{dx}-{dy}"
                pole = Pole(geom=geom_wkt, name=name)
                poles.append(pole)

                # signs
                for _ in range(azimuths_per_pole):
                    azimuth_values = sorted(
                        random.sample(all_possible_azimuths, signs_per_azimuth)
                    )
                    for i, value in enumerate(azimuth_values):
                        azimuth = Azimuth(value=value)
                        azimuths.append(azimuth)
                        sign_type = random.sample(all_possible_sign_types, 1)[0]
                        signs.append(
                            Sign(
                                order=i + 1,
                                pole=pole,
                                sign_type=sign_type,
                                azimuth=azimuth,
                            )
                        )

        # Create objects in batches
        Pole.objects.bulk_create(poles)
        Sign.objects.bulk_create(signs)
        Azimuth.objects.bulk_create(azimuths)

        # Call 'update_data' to update computed properties
        call_command("updatedata")

        print(f"🤖 testdata added!")
