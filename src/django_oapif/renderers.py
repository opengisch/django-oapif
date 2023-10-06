import io
from typing import Any, Generator, OrderedDict

import fiona
import orjson
import ujson
from django.conf import settings
from fiona.crs import CRS
from json_stream_generator import json_generator
from rest_framework import renderers


class FGBRenderer(renderers.BaseRenderer):
    format = "fgb"
    media_type = "application/event-stream"
    # FIXME: This should be sent by the model.
    schema = {"geometry": "Point", "properties": {"name": "str", "_serialized": "str"}}

    def render(self, data: OrderedDict, accepted_media_type=None, renderer_context=None) -> io.BytesIO:
        """Renders pre-serialized Python objects as a flatgeobuf binary stream"""
        features_data = data["features"] if "features" in data else data["results"]["features"]
        features = (fiona.Feature.from_dict(obj) for obj in features_data)
        buffer_wrapper = io.BytesIO()

        with fiona.open(
            buffer_wrapper,
            mode="w",
            driver="FlatGeobuf",
            schema=self.schema,
            crs=CRS.from_epsg(settings.GEOMETRY_SRID),
        ) as fh:
            for feature in features:
                fh.write(feature)

        buffer_wrapper.seek(0)
        return buffer_wrapper


class JSONStreamingRenderer(renderers.BaseRenderer):
    format = "json"
    media_type = "application/x-ndjson"

    def render(self, data: OrderedDict, accepted_media_type=None, renderer_context=None) -> Generator[Any, None, None]:
        """Renders JSON encoded stream."""
        features_data = data["features"] if "features" in data else data["results"]["features"]
        return json_generator(feature for feature in features_data)


class JSONorjson(renderers.BaseRenderer):
    format = "json"
    media_type = "application/json"

    def render(self, data: OrderedDict, accepted_media_type=None, renderer_context=None) -> bytes:
        features_data = data["features"] if "features" in data else data["results"]["features"]
        return orjson.dumps(features_data)


class JSONujson(renderers.BaseRenderer):
    format = "json"
    media_type = "application/json"

    def render(self, data: OrderedDict, accepted_media_type=None, renderer_context=None) -> str:
        features_data = data["features"] if "features" in data else data["results"]["features"]
        return ujson.dumps(features_data)
