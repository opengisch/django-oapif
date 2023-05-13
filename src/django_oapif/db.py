from typing import Any, Callable, Generator, Iterable


def mk_gen_items(
    it: Iterable, get_geom: Callable, get_id: Callable = None
) -> Generator[Any, None, None]:
    return (
        {
            "id": v.id if not get_id else get_id(v),
            "type": "Feature",
            "geometry": get_geom(v),
            "properties": {},  # assuming no other properties for the POC
        }
        for v in it
    )
