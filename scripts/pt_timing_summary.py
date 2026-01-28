#!/usr/bin/env python3
"""Generate a summary from a PrimeTime timing report."""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional


SLACK_RE = re.compile(r"\bslack\b[^-+\d]*([-+]?\d+(?:\.\d+)?)")
STARTPOINT_RE = re.compile(r"^Startpoint:")
PATH_GROUP_RE = re.compile(r"^Path Group:\s*(.+)")
PATH_TYPE_RE = re.compile(r"^Path Type:\s*(.+)")


@dataclass
class TimingStats:
    path_count: int = 0
    slack_values: List[float] = field(default_factory=list)
    path_types: Dict[str, int] = field(default_factory=dict)

    def record_path(self) -> None:
        self.path_count += 1

    def record_slack(self, value: float) -> None:
        self.slack_values.append(value)

    def record_path_type(self, path_type: str) -> None:
        self.path_types[path_type] = self.path_types.get(path_type, 0) + 1

    @property
    def has_slack(self) -> bool:
        return bool(self.slack_values)

    @property
    def wns(self) -> Optional[float]:
        return min(self.slack_values) if self.slack_values else None

    @property
    def best_slack(self) -> Optional[float]:
        return max(self.slack_values) if self.slack_values else None

    @property
    def violations(self) -> int:
        return sum(1 for value in self.slack_values if value < 0)

    @property
    def tns(self) -> float:
        return sum(value for value in self.slack_values if value < 0)

    def resolved_path_count(self) -> int:
        if self.path_count:
            return self.path_count
        return len(self.slack_values)


def parse_report(lines: Iterable[str]) -> Dict[str, TimingStats]:
    stats: Dict[str, TimingStats] = {"ALL": TimingStats()}
    current_group = "UNSPECIFIED"

    for line in lines:
        line = line.rstrip("\n")

        group_match = PATH_GROUP_RE.match(line)
        if group_match:
            current_group = group_match.group(1).strip() or "UNSPECIFIED"
            stats.setdefault(current_group, TimingStats())
            continue

        path_type_match = PATH_TYPE_RE.match(line)
        if path_type_match:
            path_type = path_type_match.group(1).strip()
            stats["ALL"].record_path_type(path_type)
            stats.setdefault(current_group, TimingStats()).record_path_type(path_type)
            continue

        if STARTPOINT_RE.match(line):
            stats["ALL"].record_path()
            stats.setdefault(current_group, TimingStats()).record_path()
            continue

        slack_match = SLACK_RE.search(line)
        if slack_match:
            value = float(slack_match.group(1))
            stats["ALL"].record_slack(value)
            stats.setdefault(current_group, TimingStats()).record_slack(value)

    return stats


def format_float(value: Optional[float]) -> str:
    if value is None:
        return "n/a"
    return f"{value:.3f}"


def emit_summary(stats: Dict[str, TimingStats]) -> str:
    overall = stats["ALL"]
    lines: List[str] = []

    lines.append("Summary")
    lines.append("=" * 7)
    lines.append(f"Total paths: {overall.resolved_path_count()}")
    lines.append(f"Worst slack (WNS): {format_float(overall.wns)}")
    lines.append(f"Total negative slack (TNS): {format_float(overall.tns)}")
    lines.append(f"Violations: {overall.violations}")
    lines.append(f"Best slack: {format_float(overall.best_slack)}")

    if overall.path_types:
        lines.append("Path types:")
        for path_type, count in sorted(overall.path_types.items()):
            lines.append(f"  - {path_type}: {count}")

    lines.append("")
    lines.append("Per Path Group")
    lines.append("--------------")
    lines.append(
        "{:<24} {:>8} {:>10} {:>12} {:>11} {:>11}".format(
            "Group", "Paths", "WNS", "TNS", "Violations", "Best"
        )
    )
    lines.append("-" * 80)

    for group, group_stats in sorted(stats.items()):
        if group == "ALL":
            continue
        lines.append(
            "{:<24} {:>8} {:>10} {:>12} {:>11} {:>11}".format(
                group[:24],
                group_stats.resolved_path_count(),
                format_float(group_stats.wns),
                format_float(group_stats.tns),
                group_stats.violations,
                format_float(group_stats.best_slack),
            )
        )

    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a summary from a PrimeTime timing report."
    )
    parser.add_argument("report", type=Path, help="Path to the PT report.")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Optional output file to write the summary.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    content = args.report.read_text(encoding="utf-8", errors="ignore").splitlines()
    stats = parse_report(content)
    summary = emit_summary(stats)

    if args.output:
        args.output.write_text(summary + "\n", encoding="utf-8")
    else:
        print(summary)


if __name__ == "__main__":
    main()
