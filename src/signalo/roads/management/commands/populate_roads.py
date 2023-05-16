from os import path
from typing import Generator, Iterable, List

from django.core.management.base import BaseCommand

from ...models import Road


def make_roads_batches(fh: Iterable) -> Generator[List[Road], None, None]:
    roads = []
    counter = 0

    for line in fh:
        geom, _ = line.rsplit(",", 1)
        geom = geom.strip('""')
        roads.append(Road(geom=geom))
        counter += 1

    if counter == 1000 or next(fh, None) is None:
        yield roads
        counter = 0


class Command(BaseCommand):
    help = "Initialize db with testdata, roads"

    def handle(self, *args, **kwargs):
        roads_csv = path.relpath("./signalo/roads/data/roads.csv")
        with open(roads_csv, "r") as fh:
            next(fh)
            total = 0
            for batch in make_roads_batches(fh):
                Road.objects.bulk_create(batch)
            total += len(batch)
        print(f"🛣️ Added {total} roads!")
