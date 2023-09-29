#!/usr/bin/env python
"""
This program writes a json file to record results of conformance reports. It
expects the followings paths as arguments:
- path of the conformance report
- path of the resulting JSON file (this doesn't need to exist; it will be created if it doesn't)
It will terminate with exit code:
- 0 if the current result is ** equal ** to the baseline (baseline = the previous recorded result).
- 1 if the current result ** surpasses ** the baseline.
- 2 if the current result is ** below ** the baseline.
"""

import json
from enum import Enum
from itertools import islice
from os import path
from sys import argv, exit
from typing import List, NamedTuple, Tuple, Union

from lxml import etree


class Cmp(str, Enum):
    EQUAL = 0
    BETTER = 1
    WORSE = 2

    @classmethod
    def tell(cls, x: Union[int, List], y: Union[int, List]) -> "Cmp":
        if isinstance(x, List) and isinstance(y, List):
            x, y = len(x), len(y)
        if x > y:
            return cls.BETTER
        if x == y:
            return cls.EQUAL
        return cls.WORSE


class Results(NamedTuple):
    passed: List[str]
    skipped: List[str]
    failed: List[str]

    @classmethod
    def get_latest(cls, path) -> "Results":
        with open(path, "r") as fh:
            results = json.load(fh)
        return cls(**results)

    @classmethod
    def parse(cls, path) -> "Results":
        ids = {"0", "1"}
        statuses = {"failed", "passed", "skipped"}
        xpaths_statuses = {
            (f'//tbody[@id="t{id}"]/tr[contains(@class, "{status}")]', status) for id in ids for status in statuses
        }
        results = {k: [] for k in statuses}

        parser = etree.HTMLParser()
        tree = etree.parse(path, parser)
        root = tree.getroot()
        has_dots = lambda x: x is not None and "." in x
        relevant_slice = lambda s: s.split(".", 5)[-1]

        for xp, status in xpaths_statuses:
            trs = root.xpath(xp)
            for tr in trs:
                children = tr.getchildren()
                found = [relevant_slice(e.text) for e in islice(children, 2) if has_dots(e.text)]
                results[status] += found
        return cls(**results)

    @staticmethod
    def write(current: "Results"):
        current = current._asdict()
        with open(baseline_path, "w") as fh:
            json.dump(current, fh, indent=2)
            fh.write("\n")
        print("Results written to disk.")

    @staticmethod
    def pass_verdict(current: "Results", previous: "Results"):
        diff = Diff.compare(current, previous)._asdict()
        worse = [f"{v}: {k}!" for k, v in diff.items() if Cmp.WORSE in v]
        not_better = all(Cmp.EQUAL in v for v in diff.values())

        if worse:
            print(
                f"{worse}\n\n^ Sorry, job results suggest that you didn't manage to clear the baseline. Scroll up for details. ^"
            )
            return Cmp.WORSE
        elif not_better:
            print(f"{current}\n\n^ Results are similar. ^")
            return Cmp.EQUAL
        else:
            Results.write(current)
            return Cmp.BETTER


class Diff(NamedTuple):
    passed: Tuple[int, Cmp]
    skipped: Tuple[int, Cmp]
    failed: Tuple[int, Cmp]

    @classmethod
    def compare(cls, last: Results, previous: Results) -> "Diff":
        passed = (len(last.passed), Cmp.tell(last.passed, previous.passed))
        skipped = (len(last.skipped), Cmp.tell(last.skipped, previous.skipped))
        failed = (len(last.failed), Cmp.tell(last.failed, previous.failed))
        return cls(passed, skipped, failed)


if __name__ == "__main__":
    report_path = path.relpath(argv[1])
    baseline_path = path.relpath(argv[2])

    assert path.exists(report_path)
    current = Results.parse(report_path)

    if not path.exists(baseline_path):
        Results.write(current)
        exit(Cmp.BETTER.value)

    previous = Results.get_latest(baseline_path)
    cmp = Results.pass_verdict(current, previous)
    exit(int(cmp.value))
