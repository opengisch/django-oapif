#!/usr/bin/env python

import csv

import plotly.graph_objects as go
from plotly.subplots import make_subplots

output_path = "tests/benchmark/results"


def tr(layer: str) -> str:
    dictionary = {
        "point_2056_10fields": "Point, 10 string fields, geometry serialized in DB",
        "point_2056_10fields_local_geom": "Point with 12 fields",
        "line_2056_10fields": "Line, 10 string fields, geometry serialized in DB",
        "line_2056_10fields_local_geom": "Line (3 points) and 12 fields",
        "polygon_2056": "Polygon, geometry serialized in DB",
        "polygon_2056_local_geom": "Complex polygon (Swiss Municipalities)",
        "nogeom_10fields": "No geometry, 12 fields",
        "nogeom_100fields": "No geometry, 100 fields",
    }
    return dictionary[layer]


data = {}
with open(f"{output_path}/benchmark.dat") as csvfile:
    reader = csv.reader(csvfile, delimiter=",")
    for row in reader:
        size = int(row[0])
        layer = row[1]
        time = float(row[2])
        std = float(row[3])
        if layer not in data:
            data[layer] = {}
        data[layer][size] = (time, std)


def create_fig(title: str = None, showlegend: bool = True) -> go.Figure:
    _fig = go.Figure()
    configure(_fig, title, showlegend)
    return _fig


def configure(_fig: go.Figure, title: str = None, showlegend: bool = True):
    if title:
        fig.update_layout(title_text=title)
    _fig.update_layout(margin=dict(l=5, r=5, t=5, b=5))
    _fig.update_layout(
        plot_bgcolor="white",
        showlegend=showlegend,
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
fig.update_xaxes(title_text="Number of features", type="log", tickvals=[1, 10, 100, 1000, 10000, 100000])
fig.update_yaxes(title_text="Fetching time (s)", type="log", tickvals=[0.1, 1, 10, 100, 1000])
fig.update_layout(legend=dict(yanchor="top", y=0.99, xanchor="left", x=0.01))
for layer, plot in plots.items():
    fig.add_trace(go.Scatter(x=plot[0], y=plot[1], mode="lines+markers", name=tr(layer)))
fig.write_image(f"{output_path}/total_time_vs_size.png", scale=6)

fig = create_fig()
fig.update_xaxes(title_text="Number of features", type="log")
fig.update_yaxes(title_text="Fetching time per feature (s)")
for layer, plot in plots.items():
    fig.add_trace(go.Scatter(x=plot[0], y=plot[2], mode="lines+markers", name=tr(layer)))
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
        plots[geom][layer] = ([], [], [])

    for size, d__ in d_.items():
        plots[geom][layer][0].append(size)
        plots[geom][layer][1].append(d__[0])
        plots[geom][layer][2].append(d__[1])

fig.update_xaxes(title_text="Number of features", type="log")
fig.update_yaxes(title_text="Fetching time (s)")
fig = make_subplots(rows=2, cols=3, row_heights=[0.7, 0.3])
configure(fig, title="Geometry serialization", showlegend=True)
fig.update_layout(legend=dict(yanchor="top", y=0.94, xanchor="left", x=0.02))
fig.update_layout(margin=dict(l=5, r=5, t=30, b=5))
c = 0
for geom, data in plots.items():
    c += 1
    fig.update_xaxes(type="log", tickmode="array", tickvals=[1, 10, 100, 1000, 10000, 100000], row=1, col=c)
    fig.update_yaxes(type="log", tickvals=[0.1, 1, 10, 100], row=1, col=c)

    fig.update_xaxes(
        title_text=geom, type="log", tickmode="array", tickvals=[1, 10, 100, 1000, 10000, 100000], row=2, col=c
    )

    colors = ["royalblue", "firebrick"]
    names = ["Postgis", "Django"]

    values = list(data.values())
    ratio = [100 * (j - i) / i for i, j in zip(values[0][1], values[1][1])]

    for layer, plot in data.items():
        fig.add_trace(go.Scatter(x=plot[0], y=ratio, showlegend=False, line=dict(color="red")), row=2, col=c)

        fig.add_trace(
            go.Scatter(
                x=plot[0],
                y=plot[1],
                error_y=dict(type="data", array=plot[2], visible=False),
                mode="lines+markers",
                name=names.pop(0),
                line=dict(color=colors.pop(0)),
                showlegend=(c == 1),
            ),
            row=1,
            col=c,
        )
fig.layout.yaxis4.range = [0, 210]
fig.layout.yaxis5.range = [0, 210]
fig.layout.yaxis6.range = [0, 210]
fig.layout.yaxis1.title.text = "Fetching time per feature (s)"
fig.layout.yaxis4.title.text = "Gain (%)"

fig.update_layout(legend=dict(traceorder="reversed"))
fig.write_image(f"{output_path}/local_vs_db_geom_serialization.png", scale=6)
