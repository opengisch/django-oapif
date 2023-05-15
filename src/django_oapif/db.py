from typing import Callable, Dict, Generator, Iterable


def mk_gen_items(
    it: Iterable, get_geom: Callable, get_id: Callable = None
) -> Generator[Dict[str, str], None, None]:
    return (
        {
            "id": str(v.id if not get_id else get_id(v)),
            "type": "Feature",
            "geometry": str(get_geom(v)),
            "properties": {},  # assuming no other properties for the POC
        }
        for v in it
    )
