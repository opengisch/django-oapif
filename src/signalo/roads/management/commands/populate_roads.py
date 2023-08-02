from os import path
from typing import Generator, Iterable, List

from django.core.management.base import BaseCommand

from ...models import Road


def make_roads_batches(fh: Iterable) -> Generator[List[Road], None, None]:
    def batch():
        roads = []
        while len(roads) < 10000:
            line = next(fh, None)
            if line:
                geom, _ = line.rsplit(",", 1)
                geom = geom.strip('""')
                roads.append(Road(geom=geom))
            else:
                break
        return roads

    while True:
        yield batch()


class Command(BaseCommand):
    help = "Initialize db with testdata, roads"

    def handle(self, *args, **kwargs):
        roads_csv = path.relpath("./signalo/roads/data/roads.csv")
        with open(roads_csv, "r") as fh:
            next(fh)
            total = 0

            for batch in make_roads_batches(fh):
                if batch:
                    Road.objects.bulk_create(batch)
                    len_batch = len(batch)
                    total += len_batch
                    print(f"{len_batch} more roads...")
                else:
                    break

        print(f"🛣️ Added {total} roads!")
