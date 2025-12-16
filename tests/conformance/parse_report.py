#!/usr/bin/env python
"""This program writes a json file to record results of conformance reports. It
expects the followings paths as arguments:
- path of the conformance report
- path of the resulting JSON file (this doesn't need to exist; it will be created if it doesn't)
Optional:
- path of a diff output file (writes passing/failing/skipping changes compared to baseline)
It will terminate with exit code:
- 0 if the current result is ** equal ** to the baseline (baseline = the previous recorded result).
- 1 if the current result ** surpasses ** the baseline.
- 2 if the current result is ** below ** the baseline.
"""

import json
import argparse
from enum import Enum
from itertools import islice
from os import path
from sys import exit
from typing import NamedTuple

from lxml import etree  # type: ignore


class Cmp(str, Enum):
    EQUAL = 0
    BETTER = 1
    WORSE = 2

    @classmethod
    def emoji(cls, cmp) -> str:
        if cmp == Cmp.EQUAL:
            return "🤓"
        if cmp == Cmp.BETTER:
            return "🍻"
        return "☠️"


class Result(NamedTuple):
    passed: list[str]
    skipped: list[str]
    failed: list[str]

    @classmethod
    def load(cls, _path) -> "Result":
        with open(_path) as fh:
            results = json.load(fh)
        return cls(**results)

    @classmethod
    def parse(cls, _path) -> "Result":
        ids = {"0", "1"}
        statuses = {"failed", "passed", "skipped"}
        xpaths_statuses = {
            (f'//tbody[@id="t{_id}"]/tr[contains(@class, "{status}")]', status) for _id in ids for status in statuses
        }
        results = {k: [] for k in statuses}

        parser = etree.HTMLParser()
        tree = etree.parse(_path, parser)
        root = tree.getroot()

        for xp, status in xpaths_statuses:
            trs = root.xpath(xp)
            for tr in trs:
                children = tr.getchildren()
                found = [e.text.split(".", 5)[-1] for e in islice(children, 2) if e.text is not None and "." in e.text]
                results[status] += found
        return cls(**results)

    def write(self):
        with open(baseline_path, "w") as fh:
            json.dump(self._asdict(), fh, indent=2)
            fh.write("\n")
        print("Results written to disk.")

    def diff(self, other: "Result") -> dict[str, dict[str, list[str]]]:
        """Return changes vs another result.

        The returned dict is stable-json-friendly and uses sorted lists.
        """

        def _delta(new: list[str], old: list[str]) -> dict[str, list[str]]:
            new_set = set(new)
            old_set = set(old)
            return {
                "added": sorted(new_set - old_set),
                "removed": sorted(old_set - new_set),
            }

        return {
            "passed": _delta(self.passed, other.passed),
            "failed": _delta(self.failed, other.failed),
            "skipped": _delta(self.skipped, other.skipped),
        }

    def compare(self, other: "Result") -> Cmp:
        """Compares the result with another one and returns if it is better, equal or worse than the other one"""
        if len(self.passed) < len(other.passed):
            return Cmp.WORSE
        if len(self.passed) > len(other.passed):
            return Cmp.BETTER
        if len(self.skipped) + len(self.failed) > len(other.skipped) + len(other.failed):
            return Cmp.WORSE
        if len(self.skipped) + len(self.failed) < len(other.skipped) + len(other.failed):
            return Cmp.BETTER
        return Cmp.EQUAL


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report_path", help="Path to the conformance HTML report")
    parser.add_argument("baseline_path", help="Path to the baseline JSON file")
    parser.add_argument(
        "--diff-out",
        dest="diff_out",
        default=None,
        help="Optional path to write a JSON diff vs baseline",
    )
    args = parser.parse_args()

    report_path = path.relpath(args.report_path)
    baseline_path = path.relpath(args.baseline_path)

    _current = Result.load(baseline_path)

    assert path.exists(report_path)
    _new = Result.parse(report_path)

    if args.diff_out:
        diff_path = path.relpath(args.diff_out)
        with open(diff_path, "w") as fh:
            json.dump(_new.diff(_current), fh, indent=2)
            fh.write("\n")
        print(f"Diff written to {diff_path}.")

    _new.write()

    _cmp = _new.compare(_current)
    print(f"{Cmp.emoji(_cmp)} Conformance is {_cmp.name}")
    exit(int(_cmp.value))
