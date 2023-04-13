import argparse
import json
import os

from django.core.files.base import ContentFile
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
                sign_instance = OfficialSignType(**row)
                for lang in ("fr", "de", "it", "ro"):
                    field = f"img_{lang}"
                    with open(
                        f"{path}/../../data/images/official/original/{row[field]}"
                    ) as fi:
                        data = fi.read()
                        getattr(sign_instance, field).save(
                            row[field], ContentFile(data)
                        )
                signs.append(sign_instance)
        try:
            OfficialSignType.objects.bulk_create(signs, ignore_conflicts=True)
        except IntegrityError as e:
            print("you might need to clean the list of type of signs")
            raise IntegrityError(e)

        print(f"🚦 Added value lists for signs!")
