import argparse
import os
import time
from pathlib import Path

import matplotlib
import polars as pl
import requests
import urllib3

matplotlib.use("Agg")
import matplotlib.pyplot as plt

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


COLLECTIONS = [
    "tests.nogeom_10fields",
    "tests.nogeom_100fields",
    "tests.point_2056_10fields",
    "tests.line_2056_10fields",
    "tests.polygon_2056",
]

LIMITS = [
    10,
    100,
    500,
]

ACCEPTS = [
    "application/geo+json",
    "application/vnd.apache.arrow.stream",
]

LABELS = {
    "application/geo+json": "GeoJSON",
    "application/vnd.apache.arrow.stream": "GeoArrow",
}

# the collections are stored in EPSG:2056: served in CRS84, the default, they are reprojected
CRSS = {
    "CRS84": None,
    "EPSG:2056": "http://www.opengis.net/def/crs/EPSG/0/2056",
}

ITERATIONS = 20

# a change of less than this, either way, is taken for noise
THRESHOLD = 0.1

# Django itself, on the port the dev compose file publishes: the Caddy of the test stack only has a
# certificate for OGCAPIF_HOST, and timing it would add TLS and proxying to what is measured
URL = f"http://localhost:{os.getenv('DJANGO_DEV_PORT', '7180')}/oapif/collections"

OUTPUT_PATH = Path(__file__).parent / "output"

# "head" for the server timed, "base" for the one it is compared with
KEY = ["server", "accept", "crs", "layer", "limit"]


def items_url(collections_url: str, layer: str, limit: int, crs: str) -> str:
    url = f"{collections_url}/{layer}/items?limit={limit}"
    return f"{url}&crs={CRSS[crs]}" if CRSS[crs] else url


def wait_for(session: requests.Session, url: str, timeout: float = 30) -> None:
    """Waits for a server that is starting to accept connections."""
    deadline = time.monotonic() + timeout
    while True:
        try:
            session.get(url, verify=False)
            return
        except requests.ConnectionError:
            if time.monotonic() > deadline:
                raise
            time.sleep(1)


def fetch(session: requests.Session, url: str, accept: str) -> requests.Response:
    response = session.get(url, headers={"Accept": accept}, verify=False)
    response.raise_for_status()
    assert response.status_code == 200
    return response


def time_request(session: requests.Session, url: str, accept: str) -> float:
    started = time.perf_counter()
    fetch(session, url, accept)
    return (time.perf_counter() - started) * 1000


def media_format(response: requests.Response) -> str:
    """JSON, whichever media type says so, or else the media type."""
    media_type = response.headers.get("Content-Type", "").split(";")[0].strip()
    return "json" if media_type == "application/json" or media_type.endswith("+json") else media_type


def format_time(median: float, base: float | None) -> str:
    if base is None:
        return f"{median:.1f}"
    change = median / base - 1
    marker = "🟢" if change < -THRESHOLD else "🔴" if change > THRESHOLD else "⚪"
    return f"{median:.1f} {marker} {change:+.0%}"


def write_markdown(summary_df: pl.DataFrame, features: dict[str, int], base_name: str | None) -> None:
    """A table of the median response times, compared with the base if any, for a pull request comment."""
    columns = [(accept, crs) for accept in ACCEPTS for crs in CRSS]
    medians = {tuple(row[column] for column in KEY): row["median_ms"] for row in summary_df.iter_rows(named=True)}
    lines = [
        "## ⏱️ Benchmark",
        "",
        f"`/items` response time in ms, median of {ITERATIONS} requests after a warm-up one. The collections are"
        " stored in EPSG:2056, and reprojected to be served in CRS84.",
    ]
    compared = (summary_df["server"] == "base").sum()
    if compared:
        lines += [
            "",
            f"Compared with the `django_oapif` of {base_name}, served on the same runner and data, a request to each"
            f" in turn: 🟢 faster and 🔴 slower by more than {THRESHOLD:.0%}, ⚪ within {THRESHOLD:.0%}.",
        ]
        if compared < (summary_df["server"] == "head").sum():
            lines[-1] += " Without a marker, the cases it does not serve, or not in the same format."
    elif base_name:
        lines += ["", f"The `django_oapif` of {base_name} could not serve the collections, so there is no comparison."]
    lines += [
        "",
        f"| Collection | Features | Limit | {' | '.join(f'{LABELS[accept]}, {crs}' for accept, crs in columns)} |",
        f"|---|---:|---:|{'---:|' * len(columns)}",
    ]
    for layer in COLLECTIONS:
        for index, limit in enumerate(LIMITS):
            times = [
                format_time(
                    medians["head", accept, crs, layer, limit], medians.get(("base", accept, crs, layer, limit))
                )
                for accept, crs in columns
            ]
            collection, count = (f"`{layer}`", str(features[layer])) if index == 0 else ("", "")
            lines.append(f"| {collection} | {count} | {limit} | {' | '.join(times)} |")
    (OUTPUT_PATH / "result.md").write_text("\n".join(lines) + "\n")


def plot(summary_df: pl.DataFrame) -> None:
    y_max = (
        max(
            mean + standard_deviation
            for mean, standard_deviation in zip(
                summary_df["mean_ms"].to_list(),
                summary_df["stddev_ms"].fill_null(0).to_list(),
            )
        )
        * 1.1
    )

    panels = [(accept, crs) for accept in ACCEPTS for crs in CRSS]
    # constrained, as a tight layout would let the title run over the first panel
    fig, axes = plt.subplots(len(panels), 1, figsize=(14, 6 * len(panels)), squeeze=False, layout="constrained")
    bar_width = 0.24
    positions = list(range(len(COLLECTIONS)))
    for panel_index, (accept, crs) in enumerate(panels):
        ax = axes[panel_index, 0]
        panel_summary = summary_df.filter((pl.col("accept") == accept) & (pl.col("crs") == crs))
        for index, limit in enumerate(LIMITS):
            # in the order of the tick labels
            values = {row["layer"]: row for row in panel_summary.filter(pl.col("limit") == limit).iter_rows(named=True)}
            means = [values[layer]["mean_ms"] for layer in COLLECTIONS]
            standard_deviations = [values[layer]["stddev_ms"] or 0 for layer in COLLECTIONS]
            x_positions = [position + (index - 1) * bar_width for position in positions]
            bars = ax.bar(
                x_positions,
                means,
                width=bar_width,
                yerr=standard_deviations,
                capsize=4,
                label=f"limit={limit}",
            )
            ax.bar_label(bars, fmt="%.1f ms", padding=3, fontsize=8)

        ax.set_xticks(positions)
        ax.set_xticklabels(COLLECTIONS, rotation=25, ha="right")
        ax.set_ylabel("Mean response time (ms)")
        ax.set_ylim(0, y_max)
        ax.set_title(f"Accept: {accept}, CRS: {crs}")
        ax.legend(title="Query limit")

    fig.suptitle("/items response time by accept format, CRS, layer, and limit")
    fig.savefig(OUTPUT_PATH / "result.png", dpi=150)
    plt.close(fig)


def main(url: str, base_url: str | None, base_name: str) -> None:
    cases = [
        (layer, limit, accept, crs) for layer in COLLECTIONS for limit in LIMITS for accept in ACCEPTS for crs in CRSS
    ]
    with requests.Session() as session:
        wait_for(session, url)
        features = {
            layer: session.get(
                f"{url}/{layer}/items?limit=1", headers={"Accept": "application/geo+json"}, verify=False
            ).json()["numberMatched"]
            for layer in COLLECTIONS
        }
        # untimed, so that caches filled by the first request do not weigh on the results
        formats = {
            (layer, limit, accept, crs): media_format(fetch(session, items_url(url, layer, limit, crs), accept))
            for layer, limit, accept, crs in cases
        }
        # the cases the base serves in the same format: its library may not know them all
        compared = set()
        if base_url:
            try:
                wait_for(session, base_url)
                for layer, limit, accept, crs in cases:
                    try:
                        response = fetch(session, items_url(base_url, layer, limit, crs), accept)
                    except requests.HTTPError:
                        continue
                    if media_format(response) == formats[layer, limit, accept, crs]:
                        compared.add((layer, limit, accept, crs))
                print(f"{len(compared)} of {len(cases)} cases compared with {base_name}")
            except requests.ConnectionError as error:
                print(f"No comparison, as the server of {base_name} does not answer: {error}")
        rows = []
        # a pass over every case at a time, so that a slow spell of the runner does not fall on one of them,
        # and each case on both servers in a row, the first of them in turn
        for iteration in range(ITERATIONS):
            for layer, limit, accept, crs in cases:
                servers = {"head": url} | ({"base": base_url} if (layer, limit, accept, crs) in compared else {})
                for server in reversed(servers) if iteration % 2 else servers:
                    rows.append({
                        "server": server,
                        "layer": layer,
                        "limit": limit,
                        "accept": accept,
                        "crs": crs,
                        "time_ms": time_request(session, items_url(servers[server], layer, limit, crs), accept),
                        "iteration": iteration,
                    })
        result_df = pl.DataFrame(rows)

    summary_df = (
        result_df.group_by(KEY)
        .agg(
            # the median, which one slow request does not move, is what the servers are compared on
            pl.col("time_ms").median().alias("median_ms"),
            pl.col("time_ms").mean().alias("mean_ms"),
            pl.col("time_ms").min().alias("min_ms"),
            pl.col("time_ms").max().alias("max_ms"),
            pl.col("time_ms").std().alias("stddev_ms"),
        )
        .sort(KEY)
    )

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    summary_df.write_csv(OUTPUT_PATH / "result.csv")
    write_markdown(summary_df, features, base_name if base_url else None)
    plot(summary_df.filter(pl.col("server") == "head"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark OAPIF /items response times.")
    parser.add_argument("--url", default=URL, help=f"the collections endpoint to time (default: {URL})")
    parser.add_argument(
        "--base-url",
        help="the collections endpoint of a server to compare with, on the same data: the requests go to each in turn",
    )
    parser.add_argument(
        "--base-name", default="the base branch", help="what the server to compare with runs, for the comment"
    )
    args = parser.parse_args()
    main(args.url, args.base_url, args.base_name)
