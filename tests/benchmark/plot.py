#!/usr/bin/env python

import csv

import plotly.graph_objects as go

data = {}

layers = []
sizes = []


with open("benchmark.dat") as csvfile:
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

fig = go.Figure()

fig.update_layout(plot_bgcolor="white")
fig.update_layout(
    showlegend=True,
    autosize=False,
    width=600,
    height=600,
)

fig.update_xaxes(
    mirror=True,
    ticks="outside",
    showline=True,
    linecolor="black",
    gridcolor="lightgrey",
    tickfont=dict(size=8, color="black"),
    showgrid=False,
    type="log",
)
fig.update_yaxes(
    mirror=True,
    ticks="outside",
    showline=True,
    linecolor="black",
    gridcolor="lightgrey",
    tickfont=dict(size=8, color="black"),
)


plots = {}
for (layer, size), d_ in data.items():
    if layer == "secretlayer" or "local_geom" in layer:
        continue
    if layer not in plots:
        plots[layer] = ([], [])
    limit = max(d_.keys())
    plots[layer][0].append(size)
    plots[layer][1].append(d_[limit][0])

for layer, plot in plots.items():
    # print(layer, plot)
    fig.add_trace(go.Scatter(x=plot[0], y=plot[1], mode="lines", name=layer))

fig.show()
