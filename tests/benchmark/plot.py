#!/usr/bin/env python

import csv

import plotly.graph_objects as go

output_path = "tests/benchmark/results"


def tr(layer: str) -> str:
    dictionary = {
        "point_2056_10fields": "Point, 10 string fields, geometry serialized in DB",
        "point_2056_10fields_local_geom": "Point, 10 string fields",
        "line_2056_10fields": "Line, 10 string fields, geometry serialized in DB",
        "line_2056_10fields_local_geom": "Line, 10 string fields",
        "polygon_2056": "Polygon, geometry serialized in DB",
        "polygon_2056_local_geom": "Polygon",
        "nogeom_10fields": "No geometry, 10 fields",
        "nogeom_100fields": "No geometry, 100 fields",
    }
    return dictionary[layer]


data = {}
with open(f"{output_path}/benchmark.dat") as csvfile:
    reader = csv.reader(csvfile, delimiter=",")
    for row in reader:
        size = int(row[0])
        layer = row[1]
        time = float(row[2]) * 1000
        std = float(row[3])
        if layer not in data:
            data[layer] = {}
        data[layer][size] = (time, std)


def create_fig(title: str = None) -> go.Figure:
    _fig = go.Figure()
    if title:
        _fig.update_layout(title_text=title)
    _fig.update_layout(
        plot_bgcolor="white",
        showlegend=True,
        autosize=False,
        width=600,
        height=600,
    )

    _fig.update_xaxes(
        mirror=True,
        ticks="outside",
        showline=True,
        linecolor="black",
        gridcolor="lightgrey",
        tickfont=dict(size=8, color="black"),
        showgrid=False,
    )
    _fig.update_yaxes(
        mirror=True,
        ticks="outside",
        showline=True,
        linecolor="black",
        gridcolor="lightgrey",
        tickfont=dict(size=8, color="black"),
    )
    return _fig


# Time vs Size
plots = {}
for layer, d_ in data.items():
    if "local_geom" not in layer and "nogeom" not in layer:
        continue
    plots[layer] = ([], [], [])
    for size, d__ in d_.items():
        plots[layer][0].append(size)
        plots[layer][1].append(d__[0])
        plots[layer][2].append(d__[0] / size)

fig = create_fig()
fig.update_xaxes(title_text="Number of features", type="log")
fig.update_yaxes(title_text="Fetching time (ms)", type="log")
for layer, plot in plots.items():
    fig.add_trace(go.Scatter(x=plot[0], y=plot[1], mode="lines", name=tr(layer)))
fig.write_image(f"{output_path}/total_time_vs_size.png", scale=6)

fig = create_fig()
fig.update_xaxes(title_text="Number of features", type="log")
fig.update_yaxes(title_text="Fetching time per feature (ms)")
for layer, plot in plots.items():
    fig.add_trace(go.Scatter(x=plot[0], y=plot[2], mode="lines", name=tr(layer)))
fig.write_image(f"{output_path}/time_per_feature_vs_size.png", scale=6)


# local vs non local geom serialization
plots = {}
for layer, d_ in data.items():
    if layer == "secretlayer" or "nogeom" in layer:
        continue

    geom = layer.split("_")[0]
    if geom not in plots:
        plots[geom] = {}
    if layer not in plots[geom]:
        plots[geom][layer] = ([], [])

    for size, d__ in d_.items():
        plots[geom][layer][0].append(size)
        plots[geom][layer][1].append(d__[0])

for geom, data in plots.items():
    fig = create_fig(title="Local Django vs DB serialization of geometry")
    fig.update_xaxes(title_text="Number of features", type="log")
    fig.update_yaxes(title_text="Fetching time (ms)")
    for layer, plot in data.items():
        fig.add_trace(go.Scatter(x=plot[0], y=plot[1], mode="lines", name=tr(layer)))
        fig.write_image(f"{output_path}/local_vs_db_geom_serialization_{geom}.png", scale=6)
