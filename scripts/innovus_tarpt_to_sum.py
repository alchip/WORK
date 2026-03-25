#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator

PATH_RE = re.compile(r"^Path\s+\d+:")
BEGIN_RE = re.compile(r"^Beginpoint:\s+(\S+).+edge of '([^']+)'")
END_RE = re.compile(r"^Endpoint:\s+(\S+).+edge of '([^']+)'")
GROUP_RE = re.compile(r"Path Groups:\s*\{([^}]+)\}")
SLACK_RE = re.compile(r"=\s*Slack Time\s*([+-]?\d+(?:\.\d+)?)")


@dataclass
class Rec:
    sp: str = ""
    ep: str = ""
    pg: str = "unknown"
    sc: str = "unknown"
    ec: str = "unknown"
    slack: float = 0.0
    stage: int = 0


@dataclass
class ParseOut:
    recs: list[Rec] = field(default_factory=list)
    scenario: str = "NA"


def open_lines(path: Path) -> Iterator[str]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="ignore") as f:
            yield from f
    else:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            yield from f


def is_non_positive(val: float) -> bool:
    return val <= 0.0


def _normalize_prefix(p: str) -> str:
    p = p.strip()
    if not p:
        return p
    return p if p.endswith("/") else (p + "/")


def _load_block_map_file(path: Path) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "->" in line:
            left, right = [x.strip() for x in line.split("->", 1)]
        else:
            parts = line.split()
            if len(parts) < 2:
                raise ValueError(f"Bad mapping line: {raw!r}")
            left, right = parts[0].strip(), parts[1].strip()
        out.append((_normalize_prefix(left), right))
    return out


def _parse_block_map_args(entries: list[str], files: list[Path]) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for e in entries:
        if "=" not in e:
            raise ValueError(f"--block-map expects prefix=name, got: {e!r}")
        prefix, name = e.split("=", 1)
        out.append((_normalize_prefix(prefix), name.strip()))
    for f in files:
        out.extend(_load_block_map_file(f))
    out.sort(key=lambda t: len(t[0]), reverse=True)  # longest-prefix wins
    return out


def map_block(pin: str, *, is_start: bool, block_map: list[tuple[str, str]]) -> str:
    if "/" not in pin:
        return "INPUT" if is_start else "OUTPUT"
    for prefix, name in block_map:
        if pin.startswith(prefix):
            return name
    return pin.split("/", 1)[0]


def parse(path: Path) -> ParseOut:
    out: list[Rec] = []
    cur = Rec()
    scenario = "NA"

    for line in open_lines(path):
        if PATH_RE.match(line):
            cur = Rec()
            continue

        if scenario == "NA" and line.startswith("Analysis View:"):
            scenario = line.split(":", 1)[1].strip() or "NA"

        m = BEGIN_RE.search(line)
        if m:
            cur.sp = m.group(1)
            cur.sc = m.group(2)
            continue

        m = END_RE.search(line)
        if m:
            cur.ep = m.group(1)
            cur.ec = m.group(2)
            continue

        m = GROUP_RE.search(line)
        if m:
            cur.pg = m.group(1).strip()
            continue

        if "->" in line:
            cur.stage += 1

        m = SLACK_RE.search(line)
        if m:
            val = float(m.group(1))
            cur.slack = val
            if cur.sp and cur.ep and is_non_positive(val):
                out.append(cur)
            cur = Rec()

    return ParseOut(recs=out, scenario=scenario)


def slack_bins() -> list[tuple[float | None, float | None, str]]:
    edges = [
        -0.000, -0.010, -0.020, -0.030, -0.040, -0.050, -0.060, -0.070, -0.080,
        -0.090, -0.100, -0.110, -0.120, -0.130, -0.140, -0.150, -0.160, -0.170,
        -0.180, -0.190, -0.200, -0.300, -0.400, -0.500,
    ]
    bins = []
    for a, b in zip(edges[:-1], edges[1:]):
        bins.append((a, b, f"{a:.3f} < {b:.3f}"))
    bins.append((-0.500, None, "-0.500 <"))
    return bins


def bin_label(v: float, bins: Iterable[tuple[float | None, float | None, str]]) -> str:
    for hi, lo, label in bins:
        if hi is not None and lo is not None and v <= hi and v > lo:
            return label
        if hi is not None and lo is None and v <= hi:
            return label
        if hi is None and lo is not None and v > lo:
            return label
    return "-0.500 <"


def emit(recs: list[Rec], path_group_name: str, scenario: str, block_map: list[tuple[str, str]]) -> str:
    bins = slack_bins()
    bcnt = Counter(bin_label(r.slack, bins) for r in recs)

    stage_map: dict[int, list[float]] = defaultdict(list)
    for r in recs:
        stage_map[r.stage].append(r.slack)

    pg_map: dict[str, list[float]] = defaultdict(list)
    for r in recs:
        pg_map[r.pg].append(r.slack)

    blk_map: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in recs:
        blk_map[(map_block(r.sp, is_start=True, block_map=block_map), map_block(r.ep, is_start=False, block_map=block_map))].append(r.slack)

    clk_map: dict[tuple[str, str], list[float]] = defaultdict(list)
    for r in recs:
        clk_map[(r.sc, r.ec)].append(r.slack)

    sp_map: dict[str, list[Rec]] = defaultdict(list)
    for r in recs:
        sp_map[r.sp].append(r)

    total = len(recs)
    tns = sum(r.slack for r in recs)
    wns = min((r.slack for r in recs), default=0.0)

    lines: list[str] = []
    lines.append(f"scenario: {scenario}")
    lines.append("")

    # timing slack
    lines.append("#start timing slack")
    lines.append(f"{'violation range':<21}{'total':<22}{path_group_name:<22}")
    lines.append("-" * 66)
    for _, _, label in bins:
        c = bcnt.get(label, 0)
        lines.append(f"{label:<21}{c:<22}{c:<22}")
    lines.append("-" * 66)
    lines.append(f"{'total':<21}{total:<22}{total:<22}")
    lines.append("#end timing slack")
    lines.append("")

    # stage count
    lines.append("#start stage count")
    lines.append(f"{'stage count':<21}{'# of violations':<22}{'worst slack':<21}")
    lines.append("-" * 66)
    for st in sorted(stage_map.keys(), reverse=True):
        arr = stage_map[st]
        lines.append(f"{st:<21}{len(arr):<22}{min(arr):<21.3f}")
    lines.append("-" * 66)
    lines.append(f"{'total':<21}{total:<22}{wns:<21.3f}")
    lines.append("#end stage count")
    lines.append("")

    # path group
    lines.append("#start path group")
    lines.append(f"{'path group':<22}{'#of violations':<22}{'worst slack':<21}{'TNS':<22}")
    lines.append("-" * 88)
    for k in sorted(pg_map):
        arr = pg_map[k]
        lines.append(f"{k:<22}{len(arr):<22}{min(arr):<21.3f}{sum(arr):<22.3f}")
    lines.append("-" * 88)
    lines.append(f"{'total':<22}{total:<22}{wns:<21.3f}{tns:<22.3f}")
    lines.append("#end path group")
    lines.append("")

    # ends block
    lines.append("#start ends block")
    lines.append(f"{'start_point_block':<22}{'end_point_block':<22}{'#of violations':<22}{'worst slack':<21}{'TNS':<22}")
    lines.append("-" * 110)
    for (sb, eb), arr in sorted(blk_map.items(), key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1])):
        lines.append(f"{sb:<22}{eb:<22}{len(arr):<22}{min(arr):<21.3f}{sum(arr):<22.3f}")
    lines.append("-" * 110)
    lines.append(f"{'total':<22}{'total':<22}{total:<22}{wns:<21.3f}{tns:<22.3f}")
    lines.append("#end ends block")
    lines.append("")

    # new: clock group
    lines.append("#start clock group")
    lines.append(f"{'start_point_clock':<22}{'end_point_clock':<22}{'#of violations':<22}{'worst slack':<21}{'TNS':<22}")
    lines.append("-" * 110)
    for (sc, ec), arr in sorted(clk_map.items(), key=lambda kv: (-len(kv[1]), kv[0][0], kv[0][1])):
        lines.append(f"{sc:<22}{ec:<22}{len(arr):<22}{min(arr):<21.3f}{sum(arr):<22.3f}")
    lines.append("-" * 110)
    lines.append(f"{'total':<22}{'total':<22}{total:<22}{wns:<21.3f}{tns:<22.3f}")
    lines.append("#end clock group")
    lines.append("")

    # detail
    lines.append("#start detail timing path")
    lines.append("<# of violations>   <startpoint> <slack> (<stage_count>) (<clock>)        <endpoint>   <slack> (<stage_count>) (<clock>)")
    items = sorted(
        ((len(v), sp, min(x.slack for x in v), max(x.stage for x in v), v) for sp, v in sp_map.items()),
        key=lambda t: (-t[0], t[2])
    )
    for cnt, sp, worst, stg, plist in items:
        sc = plist[0].sc
        lines.append(f"< {cnt:<5} {sp} {worst:.3f} ({stg}) ({sc})")
        for r in sorted(plist, key=lambda x: x.slack):
            lines.append(f"        {r.ep} {r.slack:.3f} ({r.stage}) ({r.ec}) ")
    lines.append("#end detail timing path")

    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser(description="Innovus tarpt.gz to .sum")
    ap.add_argument("report", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=False)
    ap.add_argument(
        "--block-map",
        action="append",
        default=[],
        help="Block mapping entry prefix=name (repeatable). Longest prefix match wins.",
    )
    ap.add_argument(
        "--block-map-file",
        action="append",
        type=Path,
        default=[],
        help="Path to mapping file (repeatable). Lines: 'prefix -> name'",
    )
    args = ap.parse_args()

    block_map = _parse_block_map_args(args.block_map, args.block_map_file)

    parsed = parse(args.report)
    recs = parsed.recs
    # use dominant path group name for header
    pg = Counter(r.pg for r in recs)
    pg_name = pg.most_common(1)[0][0] if pg else "group"
    text = emit(recs, pg_name, parsed.scenario, block_map)

    out = args.output if args.output else args.report.with_suffix("").with_suffix(".sum")
    out.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
