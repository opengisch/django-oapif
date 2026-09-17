import argparse
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

ITERATIONS = 20

BASE_URL = "https://localhost/oapif/collections"

OUTPUT_PATH = Path(__file__).parent / "output"


def time_request(session: requests.Session, url: str, accept: str) -> float:
    started = time.perf_counter()
    response = session.get(url, headers={"Accept": accept}, verify=False)
    response.raise_for_status()
    assert response.status_code == 200
    return (time.perf_counter() - started) * 1000


def main() -> None:
    with requests.Session() as session:
        result_df = pl.DataFrame([
            {
                "layer": layer,
                "limit": limit,
                "accept": accept,
                "time_ms": time_request(
                    session,
                    f"{BASE_URL}/{layer}/items?limit={limit}",
                    accept,
                ),
                "iteration": iteration,
            }
            for layer in COLLECTIONS
            for limit in LIMITS
            for accept in ACCEPTS
            for iteration in range(ITERATIONS)
        ])

    summary_df = (
        result_df.group_by(["accept", "layer", "limit"])
        .agg(
            pl.col("time_ms").mean().alias("mean_ms"),
            pl.col("time_ms").min().alias("min_ms"),
            pl.col("time_ms").max().alias("max_ms"),
            pl.col("time_ms").std().alias("stddev_ms"),
        )
        .sort(["accept", "layer", "limit"])
    )

    OUTPUT_PATH.mkdir(parents=True, exist_ok=True)
    summary_df.write_csv(OUTPUT_PATH / "result.csv")

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

    fig, axes = plt.subplots(len(ACCEPTS), 1, figsize=(14, 7 * len(ACCEPTS)), squeeze=False)
    bar_width = 0.24
    positions = list(range(len(COLLECTIONS)))
    for accept_index, accept in enumerate(ACCEPTS):
        ax = axes[accept_index, 0]
        accept_summary = summary_df.filter(pl.col("accept") == accept)
        for index, limit in enumerate(LIMITS):
            values = accept_summary.filter(pl.col("limit") == limit).sort("layer")
            means = values["mean_ms"].to_list()
            standard_deviations = values["stddev_ms"].fill_null(0).to_list()
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
        ax.set_ylabel("Response time (ms)")
        ax.set_ylim(0, y_max)
        ax.set_title(f"Accept: {accept}")
        ax.legend(title="Query limit")

    fig.suptitle("/items response time by accept format, layer, and limit")
    fig.tight_layout()
    fig.savefig(OUTPUT_PATH / "result.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Benchmark OAPIF /items response times.")
    args = parser.parse_args()
    main()
