#!/usr/bin/env python3
"""Generate a wo_io.rpt.summary-style summary from a PrimeTime timing report.

Inputs:
  - Plain text PT report
  - Or gzipped report (.gz)

This script is tailored to reports that look like PT `report_timing -nosplit ...` output,
where each path block contains:
  Startpoint:
  Endpoint:
  Path Group:
  Point ... table
  data arrival time
  ...
  slack (VIOLATED) ... <slack>

It produces a summary in the same format as /Users/sunnyy/test/wo_io.rpt.summary.

Block mapping (optional):
  By default, the "startpoint block / endpoint block" table uses the first hierarchy token
  (e.g. m_misc/m_max_buf/... -> m_misc).

  You can override this by supplying one or more mapping files. Mapping uses longest-prefix
  match against the full instance path.

  Mapping file format (one per line):
    m_misc/m_max_buf/ -> m_max_buf
    m_misc/m_abuf/    -> m_abuf
  Lines starting with # are ignored.

Usage:
  # Basic
  ./pt_summary_from_rpt.py /Users/sunnyy/test/wo_io.rpt.gz -o /Users/sunnyy/test/out.summary

  # With mapping file (repeatable)
  ./pt_summary_from_rpt.py /Users/sunnyy/test/wo_io.rpt.gz \
    --block-map-file /Users/sunnyy/test/block_map.txt \
    -o /Users/sunnyy/test/out.summary
"""

from __future__ import annotations

import argparse
import gzip
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple


RE_STARTPOINT = re.compile(r"^\s*Startpoint:\s*(.+?)\s*\((.*clocked by\s+(\S+).*)\)")
RE_ENDPOINT = re.compile(r"^\s*Endpoint:\s*(.+?)\s*\((.*clocked by\s+(\S+).*)\)")
RE_PATH_GROUP = re.compile(r"^\s*Path Group:\s*(\S+)")
RE_POINT_TABLE = re.compile(r"^\s*Point\b")
RE_DATA_ARRIVAL = re.compile(r"^\s*data arrival time\b")
RE_CLK_NW_DELAY = re.compile(r"^\s*clock network delay \(propagated\)")
RE_SLACK = re.compile(r"^\s*slack\b")

# Point-row line with a pin and a cell type in parentheses.
RE_POINT_PIN = re.compile(r"^\s*(\S+?/[^\s]+)\s*\(")

# Capture the first float on the line (PT columns are aligned; the first float is what we want).
RE_FIRST_FLOAT = re.compile(r"([-+]?\d+(?:\.\d+)?)")

# Slack line: take the last float on the line.
RE_LAST_FLOAT = re.compile(r"([-+]?\d+(?:\.\d+)?)(?!.*[-+]?\d)")

# Heuristic: output pins that represent a timing stage in typical stdcell libs.
RE_OUTPUT_PIN = re.compile(
    r"/(?:Z|ZN|Y|Q\d*|QB\d*|QN|CO|COUT|S|SO|SUM)$"
)

# Endpoint data pin (D, D0..D9, D1.. etc)
RE_DATA_PIN = re.compile(r"/(?:D\d*|DIN\d*|DATA\d*)$")


@dataclass
class PathRec:
    start_inst: str
    end_inst: str
    start_clk: str
    end_clk: str
    path_group: str

    start_clk_delay: Optional[float] = None
    end_clk_delay: Optional[float] = None

    slack: Optional[float] = None

    stage_count: Optional[int] = None

    start_pin: Optional[str] = None  # instance/CP
    end_pin: Optional[str] = None    # instance/Dx

    def skew(self) -> Optional[float]:
        if self.start_clk_delay is None or self.end_clk_delay is None:
            return None
        return self.end_clk_delay - self.start_clk_delay


def open_text(path: Path) -> Iterator[str]:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8", errors="ignore") as f:
            yield from f
    else:
        with path.open("r", encoding="utf-8", errors="ignore") as f:
            yield from f


def parse_first_float(line: str) -> Optional[float]:
    m = RE_FIRST_FLOAT.search(line)
    return float(m.group(1)) if m else None


def parse_last_float_token(line: str) -> Optional[str]:
    m = RE_LAST_FLOAT.search(line)
    return m.group(1) if m else None


def _normalize_prefix(p: str) -> str:
    p = p.strip()
    if not p:
        return p
    # treat mapping prefixes as hierarchy prefixes
    return p if p.endswith("/") else (p + "/")


def top_block(inst: str, prefix_map: List[Tuple[str, str]]) -> str:
    """Return the block name used in the startpoint/endpoint block table.

    Default behavior (no mapping hit): use the first hierarchy token.

    With prefix_map: do a longest-prefix match against the full instance path.
    Example mapping:
      m_misc/m_max_buf/ -> m_max_buf
    """
    for prefix, name in prefix_map:
        if inst.startswith(prefix):
            return name
    # fallback: first level
    return inst.split("/", 1)[0] if "/" in inst else inst


def iter_paths(lines: Iterable[str]) -> Iterator[PathRec]:
    cur: Optional[PathRec] = None

    in_point_table = False
    seen_data_arrival = False
    output_stage_count = 0
    last_data_pin: Optional[str] = None

    for raw in lines:
        line = raw.rstrip("\n")

        msp = RE_STARTPOINT.match(line)
        if msp:
            # finalize previous path if it had slack
            if cur and cur.slack is not None:
                cur.stage_count = output_stage_count if output_stage_count else None
                cur.end_pin = last_data_pin or cur.end_pin
                yield cur

            start_inst = msp.group(1).strip()
            start_clk = msp.group(3).strip()
            cur = PathRec(
                start_inst=start_inst,
                end_inst="",
                start_clk=start_clk,
                end_clk="",
                path_group="*",
            )
            cur.start_pin = f"{start_inst}/CP"

            # reset per-path state
            in_point_table = False
            seen_data_arrival = False
            output_stage_count = 0
            last_data_pin = None
            continue

        if cur is None:
            continue

        mep = RE_ENDPOINT.match(line)
        if mep:
            cur.end_inst = mep.group(1).strip()
            cur.end_clk = mep.group(3).strip()
            continue

        mpg = RE_PATH_GROUP.match(line)
        if mpg:
            cur.path_group = mpg.group(1).strip()
            continue

        if RE_POINT_TABLE.match(line):
            in_point_table = True
            continue

        if in_point_table:
            if RE_DATA_ARRIVAL.match(line):
                in_point_table = False
                seen_data_arrival = True
                # best effort: if we didn't see end pin in the table, fall back to end_inst
                if cur.end_pin is None and cur.end_inst:
                    cur.end_pin = f"{cur.end_inst}/D"
                continue

            # within the point table, capture launch clock delay and stage count
            if RE_CLK_NW_DELAY.match(line) and cur.start_clk_delay is None:
                cur.start_clk_delay = parse_first_float(line)
                continue

            mpin = RE_POINT_PIN.match(line)
            if not mpin:
                continue

            pin = mpin.group(1)
            if "(net)" in line:
                continue

            # count output pins as stages (only when the line is a sensitized stage, marked with '&')
            if RE_OUTPUT_PIN.search(pin) and "&" in line:
                output_stage_count += 1

            # detect endpoint data pin from the last row before data arrival time
            if RE_DATA_PIN.search(pin):
                last_data_pin = pin

        # after data arrival time, capture capture-clock delay (the next clk network delay)
        if seen_data_arrival and cur.end_clk_delay is None and RE_CLK_NW_DELAY.match(line):
            cur.end_clk_delay = parse_first_float(line)
            continue

        if RE_SLACK.match(line):
            cur.slack = parse_slack_value(line)
            continue

    # finalize last
    if cur and cur.slack is not None:
        cur.stage_count = output_stage_count if output_stage_count else None
        cur.end_pin = last_data_pin or cur.end_pin
        yield cur


def make_slack_bins() -> List[Tuple[Optional[float], Optional[float], str]]:
    # (lo, hi, label) where bin is (hi, lo] in the printed style:
    # "-0.002ns < -0.004ns" means -0.004 <= slack < -0.002.
    edges = [
        -0.000,
        -0.002,
        -0.004,
        -0.006,
        -0.008,
        -0.010,
        -0.015,
        -0.020,
        -0.030,
        -0.040,
        -0.050,
        -0.060,
        -0.070,
        -0.080,
        -0.090,
        -0.100,
        -0.110,
        -0.120,
        -0.130,
        -0.140,
        -0.150,
        -0.160,
        -0.170,
        -0.180,
        -0.190,
        -0.200,
        -0.300,
        -0.400,
        -0.500,
        -1.000,
        -2.000,
        -5.000,
    ]
    bins: List[Tuple[Optional[float], Optional[float], str]] = []
    for a, b in zip(edges[:-1], edges[1:]):
        bins.append((a, b, f" {a:+.3f}ns < {b:+.3f}ns".replace("+", "")))
    # final open-ended: slack < -5.0
    bins.append((-5.000, None, " -5.000ns <"))
    return bins


def make_skew_bins() -> List[Tuple[Optional[float], Optional[float], str]]:
    # Match the reference summary formatting exactly.
    return [
        (None, -5.0, "        < -5.0ns"),
        (-5.0, -2.0, " -5.0ns < -2.0ns"),
        (-2.0, -1.0, " -2.0ns < -1.0ns"),
        (-1.0, -0.5, " -1.0ns < -0.5ns"),
        (-0.5, -0.2, " -0.5ns < -0.2ns"),
        (-0.2, -0.1, " -0.2ns < -0.1ns"),
        (-0.1, 0.0, " -0.1ns <  0.0ns"),
        (0.0, 0.1, "  0.0ns < +0.1ns"),
        (0.1, 0.2, " +0.1ns < +0.2ns"),
        (0.2, 0.5, " +0.2ns < +0.5ns"),
        (0.5, 1.0, " +0.5ns < +1.0ns"),
        (1.0, 2.0, " +1.0ns < +2.0ns"),
        (2.0, 5.0, " +2.0ns < +5.0ns"),
        (5.0, None, " +5.0ns <"),
    ]


def bin_value_desc(v: float, bins: List[Tuple[Optional[float], Optional[float], str]]) -> str:
    """Bin for descending ranges like slack bins near 0 going more negative.

    Match the example file's boundary behavior:
      "-0.000ns < -0.002ns" counts values where  -0.002 < v <= -0.000
      "-0.002ns < -0.004ns" counts values where  -0.004 < v <= -0.002

    i.e. (lower, upper] for each bin.
    """
    for upper, lower, label in bins:
        if upper is None and lower is not None:
            # "< lower" (more negative than the last edge)
            if v <= lower:
                return label
        elif lower is None and upper is not None:
            # not used for our slack bins, but keep for completeness
            if v > upper:
                return label
        elif upper is not None and lower is not None:
            if v <= upper and v > lower:
                return label
    return "(unbinned)"


def bin_value_linear(v: float, bins: List[Tuple[Optional[float], Optional[float], str]]) -> str:
    """Bin for standard increasing ranges."""
    for lo, hi, label in bins:
        if lo is None and hi is not None:
            if v < hi:
                return label
        elif hi is None and lo is not None:
            if v >= lo:
                return label
        elif lo is not None and hi is not None:
            if v >= lo and v < hi:
                return label
    return "(unbinned)"


def fmt3(x: float) -> str:
    return f"{x:.3f}"


def emit_summary(paths: List[PathRec], prefix_map: List[Tuple[str, str]]) -> str:
    neg = [p for p in paths if p.slack is not None and p.slack < 0]

    slack_bins = make_slack_bins()
    skew_bins = make_skew_bins()

    slack_hist = Counter(bin_value_desc(p.slack, slack_bins) for p in neg if p.slack is not None)
    skew_hist = Counter(
        bin_value_linear(p.skew(), skew_bins) for p in neg if p.skew() is not None
    )

    total = len(neg)
    wns = min((p.slack for p in neg if p.slack is not None), default=0.0)
    tns = sum((p.slack for p in neg if p.slack is not None), 0.0)

    # path group table
    pg_count: Dict[str, int] = Counter(p.path_group for p in neg)
    pg_wns: Dict[str, float] = {}
    pg_tns: Dict[str, float] = Counter()
    for p in neg:
        if p.slack is None:
            continue
        pg_tns[p.path_group] += p.slack
        if p.path_group in pg_wns:
            pg_wns[p.path_group] = min(pg_wns[p.path_group], p.slack)
        else:
            pg_wns[p.path_group] = p.slack

    # start/end clock table
    clk_key = lambda p: (p.start_clk, p.end_clk)
    clk_count: Dict[Tuple[str, str], int] = Counter(clk_key(p) for p in neg)
    clk_wns: Dict[Tuple[str, str], float] = {}
    clk_tns: Dict[Tuple[str, str], float] = Counter()
    for p in neg:
        if p.slack is None:
            continue
        k = clk_key(p)
        clk_tns[k] += p.slack
        clk_wns[k] = min(clk_wns.get(k, p.slack), p.slack)

    # start/end block table
    blk_key = lambda p: (top_block(p.start_inst, prefix_map), top_block(p.end_inst, prefix_map))
    blk_count: Dict[Tuple[str, str], int] = Counter(blk_key(p) for p in neg)
    blk_wns: Dict[Tuple[str, str], float] = {}
    blk_tns: Dict[Tuple[str, str], float] = Counter()
    for p in neg:
        if p.slack is None:
            continue
        k = blk_key(p)
        blk_tns[k] += p.slack
        blk_wns[k] = min(blk_wns.get(k, p.slack), p.slack)

    # stage count histogram
    stage_hist = Counter(p.stage_count for p in neg if p.stage_count is not None)

    # bottom listing grouped by startpoint pin
    by_start: Dict[str, List[PathRec]] = defaultdict(list)
    for p in neg:
        by_start[p.start_pin or (p.start_inst + "/CP")].append(p)

    # Determine per-start summary slack (worst) and stage count (max)
    start_summary: List[Tuple[int, str, float, int, float, List[PathRec]]] = []
    for sp, plist in by_start.items():
        worst = min((p.slack for p in plist if p.slack is not None), default=0.0)
        # stage count shown next to startpoint: match example by using max stage_count
        max_stage = max((p.stage_count or 0) for p in plist)
        # start clk delay is constant-ish; use first non-None
        scd = next((p.start_clk_delay for p in plist if p.start_clk_delay is not None), 0.0)
        start_summary.append((len(plist), sp, worst, max_stage, scd, plist))

    start_summary.sort(key=lambda t: (-t[0], t[2]))  # most violations first, then worst slack

    out: List[str] = []

    out.append("")
    out.append(" violation range                      # of violations")
    out.append(" ------------------------------  --------------------")
    for lo, hi, label in slack_bins:
        out.append(f"{label:<30}  {slack_hist.get(label,0):>21}")
    out.append(" ------------------------------  --------------------")
    out.append(f" total{total:>47}")
    out.append(" ------------------------------  --------------------")
    out.append(f" WNS:{wns:>48.3f}")
    out.append(f" TNS:{tns:>48.3f}")
    out.append("")

    out.append(" original skew range                  # of violations")
    out.append(" ------------------------------  --------------------")
    for lo, hi, label in skew_bins:
        out.append(f"{label:<30}  {skew_hist.get(label,0):>21}")
    out.append(" ------------------------------  --------------------")
    out.append(f" total{total:>47}")
    out.append("")

    out.append(" path group                           # of violations           worst slack           total slack")
    out.append(" ------------------------------  --------------------  --------------------  --------------------")
    for pg in sorted(pg_count.keys()):
        out.append(
            f" {pg:<30}  {pg_count[pg]:>20}  {pg_wns.get(pg,0.0):>20.3f}  {pg_tns.get(pg,0.0):>20.3f}"
        )
    out.append(" ------------------------------  --------------------  --------------------  --------------------")
    out.append(f" *{'':<30}  {total:>20}  {wns:>20.3f}  {tns:>20.3f}")
    out.append("")

    out.append(
        " startpoint clock      endpoint clock             # of violations           worst slack           total slack"
    )
    out.append(
        " --------------------  --------------------  --------------------  --------------------  --------------------"
    )
    for (sc, ec) in sorted(clk_count.keys()):
        out.append(
            f" {sc:<20}{ec:<20}{clk_count[(sc,ec)]:>20}{clk_wns[(sc,ec)]:>20.3f}{clk_tns[(sc,ec)]:>20.3f}"
        )
    out.append(
        " --------------------  --------------------  --------------------  --------------------  --------------------"
    )
    out.append(f" {'*':<21}{'*':<20}{total:>20}{wns:>20.3f}{tns:>20.3f}")
    out.append("")

    out.append(
        " startpoint block                endpoint block                       # of violations           worst slack           total slack"
    )
    out.append(
        " ------------------------------  ------------------------------  --------------------  --------------------  --------------------"
    )
    for (sb, eb) in sorted(blk_count.keys()):
        out.append(
            f" {sb:<30}{eb:<30}{blk_count[(sb,eb)]:>20}{blk_wns[(sb,eb)]:>20.3f}{blk_tns[(sb,eb)]:>20.3f}"
        )
    out.append(
        " ------------------------------  ------------------------------  --------------------  --------------------  --------------------"
    )
    out.append(f" {'*':<31}{'*':<31}{total:>20}{wns:>20.3f}{tns:>20.3f}")
    out.append("")

    out.append(" stage count                          # of violations")
    out.append(" ------------------------------  --------------------")
    for sc in sorted(stage_hist.keys()):
        out.append(f"{sc:>31}{stage_hist[sc]:>22}")
    out.append(" ------------------------------  --------------------")
    out.append(f" total{total:>47}")
    out.append("")

    out.append("<# of violations>\t<startpoint> <slack> (<stage_count>) (<clock>:<clock_network_delay>)")
    out.append("\t\t\t<endpoint>   <slack> (<stage_count>) (<clock>:<clock_network_delay>) (<skew>)")
    out.append("")

    for cnt, sp, worst, max_stage, scd, plist in start_summary:
        # print the startpoint line
        sc_name = plist[0].start_clk
        out.append(f"{cnt}\t{sp} {worst:.3f} ({max_stage}) ({sc_name}:{scd:.3f})")

        # endpoints sorted by slack (worst first)
        plist_sorted = sorted(plist, key=lambda p: (p.slack if p.slack is not None else 0.0))
        for p in plist_sorted:
            ep = p.end_pin or (p.end_inst + "/D")
            slack = p.slack if p.slack is not None else 0.0
            stc = p.stage_count or 0
            ecd = p.end_clk_delay or 0.0
            sk = p.skew() or 0.0
            out.append(
                f"\t{ep} {slack:.3f} ({stc}) ({p.end_clk}:{ecd:.3f}) ({sk:.3f})"
            )

    return "\n".join(out) + "\n"


def parse_slack_value(line: str) -> Optional[float]:
    """Parse slack from a PT 'slack ...' line.

    Important: PT often prints tiny negative slacks as '-0.000'.
    float('-0.000') becomes -0.0, and (-0.0 < 0) is False in Python.
    We preserve the sign by nudging negative zeros slightly below 0.
    """
    tok = parse_last_float_token(line)
    if tok is None:
        return None
    val = float(tok)
    if val == 0.0 and tok.lstrip().startswith("-"):
        return -1e-12
    return val


def _load_block_map_file(path: Path) -> List[Tuple[str, str]]:
    """Read mapping file.

    Supported line formats (whitespace-insensitive):
      m_misc/m_max_buf/ -> m_max_buf
      m_misc/m_max_buf/  m_max_buf
    Lines starting with # are ignored.
    """
    out: List[Tuple[str, str]] = []
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


def _parse_block_map_args(entries: List[str], files: List[Path]) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for e in entries:
        if "=" not in e:
            raise ValueError(f"--block-map expects prefix=name, got: {e!r}")
        prefix, name = e.split("=", 1)
        out.append((_normalize_prefix(prefix), name.strip()))
    for f in files:
        out.extend(_load_block_map_file(f))
    # longest prefix wins
    out.sort(key=lambda t: len(t[0]), reverse=True)
    return out


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser()
    ap.add_argument("report", type=Path)
    ap.add_argument("-o", "--output", type=Path, required=False)
    ap.add_argument(
        "--block-map",
        action="append",
        default=[],
        help=(
            "Block mapping entry prefix=name (repeatable). Longest prefix match wins. "
            "Example: --block-map 'm_misc/m_max_buf/=m_max_buf'"
        ),
    )
    ap.add_argument(
        "--block-map-file",
        action="append",
        type=Path,
        default=[],
        help=(
            "Path to a mapping file (repeatable). Lines: 'prefix -> name'. "
            "Example line: m_misc/m_max_buf/ -> m_max_buf"
        ),
    )
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    prefix_map = _parse_block_map_args(args.block_map, args.block_map_file)

    paths = list(iter_paths(open_text(args.report)))
    summary = emit_summary(paths, prefix_map)

    if args.output:
        args.output.write_text(summary, encoding="utf-8")
    else:
        print(summary, end="")


if __name__ == "__main__":
    main()
