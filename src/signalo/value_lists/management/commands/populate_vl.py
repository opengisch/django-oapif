import argparse
import json
import os

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.utils import IntegrityError

from ...models import OfficialSignType


class Command(BaseCommand):
    help = "Populate value lists"

    def add_arguments(self, parser):
        parser.add_argument("--clean", action=argparse.BooleanOptionalAction)
        parser.set_defaults(clean=False)

    @transaction.atomic
    def handle(self, *args, **options):
        if options["clean"]:
            print("cleaning all types of signs")
            OfficialSignType.objects.all().delete()

        signs = []

        path = os.path.abspath(os.path.dirname(__file__))
        with open(f"{path}/../../data/official-signs.json") as csvfile:
            data = json.load(csvfile)
            for row in data:
                sign_instance = OfficialSignType(
                    active=row["active"],
                    value_de=row["value_de"],
                    value_fr=row["value_fr"],
                    value_it=row["value_it"],
                    value_ro=row["value_ro"],
                    description_de=row["description_de"],
                    description_fr=row["description_fr"],
                    description_it=row["description_it"],
                    description_ro=row["description_ro"],
                    img=row["img_de"],
                    img_height=row["img_height"],
                    img_width=row["img_width"],
                    no_dynamic_inscription=row["no_dynamic_inscription"],
                    default_inscription1=row["default_inscription1"],
                    default_inscription2=row["default_inscription2"],
                    default_inscription3=row["default_inscription3"],
                    default_inscription4=row["default_inscription4"],
                )
                signs.append(sign_instance)
        try:
            OfficialSignType.objects.bulk_create(signs, ignore_conflicts=True)
        except IntegrityError as e:
            print("you might need to clean the list of type of signs")
            raise IntegrityError(e)

        print(f"🚦 Added value lists for signs!")
