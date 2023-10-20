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
from typing import List, NamedTuple

from lxml import etree


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
        else:
            return "☠️"


class Result(NamedTuple):
    passed: List[str]
    skipped: List[str]
    failed: List[str]

    @classmethod
    def load(cls, _path) -> "Result":
        with open(_path, "r") as fh:
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

    def compare(self, other: "Result") -> Cmp:
        """
        Compares the result with another one and returns if it is better, equal or worse than the other one
        """
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
    report_path = path.relpath(argv[1])
    baseline_path = path.relpath(argv[2])

    _current = Result.load(baseline_path)

    assert path.exists(report_path)
    _new = Result.parse(report_path)
    _new.write()

    _cmp = _new.compare(_current)
    print(f"{Cmp.emoji(_cmp)} Conformance is {_cmp.name}")
    exit(int(_cmp.value))
