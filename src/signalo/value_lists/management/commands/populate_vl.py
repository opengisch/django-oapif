from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

import json
import os

from ...models import OfficialSignType


class Command(BaseCommand):
    help = "Populate value lists"

    def add_arguments(self, parser):
        parser.add_argument(
            "-c", "--clean", type=bool, default=False,
        )

    @transaction.atomic
    def handle(self, *args, **options):
        signs = []

        path = os.path.abspath(os.path.dirname(__file__))

        with open(f'{path}/../../data/official-signs.json') as csvfile:
            data = json.load(csvfile)
            for row in data:
                sign_instance = OfficialSignType(**row)
                signs.append(sign_instance)

        OfficialSignType.objects.bulk_create(signs)

