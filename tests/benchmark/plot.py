#!/usr/bin/env python

import csv

import plotly.graph_objects as go

output_path = "tests/benchmark/results/"

data = {}
with open(f"{output_path}/benchmark.dat") as csvfile:
    reader = csv.reader(csvfile, delimiter=",")
    for row in reader:
        size = int(row[0])
        limit = int(row[1])
        layer = row[2]
        time = float(row[3])
        std = float(row[4])
        if (layer, size) not in data:
            data[(layer, size)] = {}
        data[(layer, size)][limit] = (time, std)


def create_fig() -> go.Figure:
    _fig = go.Figure()
    _fig.update_layout(plot_bgcolor="white")
    _fig.update_layout(
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
for (layer, size), d_ in data.items():
    if layer == "secretlayer" or "local_geom" in layer:
        continue
    if layer not in plots:
        plots[layer] = ([], [], [])
    limit = max(d_.keys())
    plots[layer][0].append(size)
    plots[layer][1].append(d_[limit][0])
    plots[layer][2].append(d_[limit][0] / size)

fig = create_fig()
fig.update_xaxes(type="log")
for layer, plot in plots.items():
    fig.add_trace(go.Scatter(x=plot[0], y=plot[1], mode="lines", name=layer))
fig.write_image(f"{output_path}/total_time_vs_size.png", scale=6)

fig = create_fig()
fig.update_xaxes(type="log")
for layer, plot in plots.items():
    fig.add_trace(go.Scatter(x=plot[0], y=plot[2], mode="lines", name=layer))
fig.write_image(f"{output_path}/time_per_feature_vs_size.png", scale=6)
