import io
from typing import OrderedDict

import fiona
import orjson
import ujson
from django.conf import settings
from django.http import StreamingHttpResponse
from fiona.crs import CRS
from json_stream_generator import json_generator
from rest_framework import renderers


class FGBRenderer(renderers.BaseRenderer):
    format = "fgb"
    media_type = "application/event-stream"
    # FIXME: This should be sent by the model.
    schema = {"geometry": "Point", "properties": {"name": "str", "_serialized": "str"}}

    def render(self, data: OrderedDict, accepted_media_type=None, renderer_context=None) -> StreamingHttpResponse:
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
        return StreamingHttpResponse(buffer_wrapper)


class JSONStreamingRenderer(renderers.BaseRenderer):
    format = "json"
    media_type = "application/x-ndjson"

    def render(self, data: OrderedDict, accepted_media_type=None, renderer_context=None) -> StreamingHttpResponse:
        """Renders JSON encoded stream."""
        features_data = data["features"] if "features" in data else data["results"]["features"]
        generate = json_generator(feature for feature in features_data)
        return StreamingHttpResponse(generate)


class JSONorjson(renderers.BaseRenderer):
    format = "json"
    media_type = "application/json"

    def render(self, data: OrderedDict, accepted_media_type=None, renderer_context=None) -> bytes:
        return orjson.dumps(data)


class JSONujson(renderers.BaseRenderer):
    format = "json"
    media_type = "application/json"

    def render(self, data: OrderedDict, accepted_media_type=None, renderer_context=None) -> bytes:
        return ujson.dumps(data)
