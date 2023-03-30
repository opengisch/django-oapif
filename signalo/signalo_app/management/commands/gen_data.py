from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.db import transaction
from signalo_app.models import Pole, Sign


class Command(BaseCommand):
    help = "Generate test data directly from django models"

    def add_arguments(self, parser):
        parser.add_argument(
            "-s", "--srid", type=int, default=4326, choices=(4326, 2056)
        )
        parser.add_argument("-m", "--magnitude", type=int, default=10)

    @transaction.atomic
    def handle(self, *args, **options):
        """
        Run command inside a transaction to
        avoid broken state should some commits fail
        """
        magnitude = options["magnitude"]
        if magnitude > 1000:
            raise ValueError("magnitude > 1000")

        if options["srid"] == 2056:
            x_start = 2508500
            y_start = 1152000
            step = 100
        else:
            x_start = 45
            y_start = 7
            step = 0.01

        signs_per_pole = 3
        poles = []
        signs = []

        for dx in range(0, magnitude):
            for dy in range(0, magnitude):
                # pole
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
                        )
                    )

        # Create objects in batches
        Pole.objects.bulk_create(poles)
        Sign.objects.bulk_create(signs)

        # Call 'update_data' to update computed properties
        call_command("updatedata")

        print(f"🤖 testdata added!")