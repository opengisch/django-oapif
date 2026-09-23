---
hide:
  - navigation
---

# GeoArrow

Features can be read as an [Apache Arrow](https://arrow.apache.org/) stream instead of GeoJSON, with the geometries encoded as [GeoArrow](https://geoarrow.org/) WKB. It is faster to produce and to load than GeoJSON, and goes straight into Arrow-based tools.

## Installation

Arrow support is an optional extra:

```bash
pip install "django-oapif[arrow]"
```

Without it, a request for Arrow is answered with a `406 Not Acceptable`.

## Requesting Arrow

Ask for the Arrow stream media type:

```bash
curl -H "Accept: application/vnd.apache.arrow.stream" \
  "https://example.com/oapif/collections/my_app.my_model/items"
```

This works on `/collections/{collectionId}/items`, and on `/collections/{collectionId}/items/{featureId}`, which returns a single row. The `Accept` header has to prefer Arrow explicitly: `*/*` still gets GeoJSON.

## What the stream contains

Each property is a column, followed by a `geometry` column when the collection has a geometry.

The column types come from the property types rather than from the values, so that every page of a collection has the same schema:

| Property      | Arrow type           |
|---------------|----------------------|
| boolean       | `bool`               |
| integer       | `int64`              |
| float         | `float64`            |
| string        | `string`             |
| UUID          | `string`             |
| date          | `date32`             |
| datetime      | `timestamp[us, UTC]` |
| time          | `time64[us]`         |

Foreign keys hold the primary key of the referenced object and files their URL, as in GeoJSON (see [Special fields](special_fields.md)). Other types are inferred from the values of each page, so their column type can differ from one page to the next.

The geometry column is GeoArrow WKB (`geoarrow.wkb`), tagged with the CRS its coordinates are in: `OGC:CRS84` by default, or `EPSG:<srid>` when the storage CRS is requested with `crs=`. The same CRS is given in the `Content-Crs` response header. Only the CRS a collection advertises can be requested; any other is rejected with a `400`.

Import `geoarrow.pyarrow` for pyarrow to recognise the geometry column. Without it, the column reads as plain `binary`, with its GeoArrow type and CRS left in the field metadata.

## Pagination

Arrow responses are paginated like GeoJSON ones, with the same `limit` (100 by default) and `offset` parameters. As an Arrow stream has no room for them in its payload, the paging information is in the response headers:

- `Link`: the `self`, `prev` and `next` pages, the same as the GeoJSON `links`
- `OGC-NumberMatched`: the number of features matching the query, across all pages

There is no header for the number of features returned: it is the row count of the table.

Pages can be concatenated into one table. To fetch a whole collection, follow the `next` links:

```python
import geoarrow.pyarrow  # registers the GeoArrow types with pyarrow
import pyarrow as pa
import requests

url = "https://example.com/oapif/collections/my_app.my_model/items?limit=1000"
pages = []
while url:
    response = requests.get(url, headers={"Accept": "application/vnd.apache.arrow.stream"})
    response.raise_for_status()
    pages.append(pa.ipc.open_stream(response.content).read_all())
    url = response.links.get("next", {}).get("url")

table = pa.concat_tables(pages)
```
