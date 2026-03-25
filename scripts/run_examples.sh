#!/usr/bin/env bash
set -euo pipefail

# Quick examples for WORK/scripts tools.
# Usage:
#   ./scripts/run_examples.sh                 # show this help
#   ./scripts/run_examples.sh pt <rpt> [out] # run pt_summary_from_rpt.py
#   ./scripts/run_examples.sh tcl <in.tcl> [out.cfg] # run tcl_to_cfg.py

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/run_examples.sh pt <report.rpt|report.rpt.gz> [out.summary]
  ./scripts/run_examples.sh tcl <input.tcl> [output.cfg]

Examples:
  ./scripts/run_examples.sh pt /path/to/wo_io.rpt.gz
  ./scripts/run_examples.sh pt /path/to/wo_io.rpt.gz /tmp/out.summary

  ./scripts/run_examples.sh tcl /path/to/input.tcl
  ./scripts/run_examples.sh tcl /path/to/input.tcl /tmp/output.cfg
EOF
}

if [[ $# -lt 1 ]]; then
  usage
  exit 0
fi

cmd="$1"
shift || true

case "$cmd" in
  pt)
    if [[ $# -lt 1 ]]; then
      echo "[ERROR] Missing PT report path."
      usage
      exit 1
    fi
    rpt="$1"
    out="${2:-${rpt}.summary}"
    python3 "$ROOT_DIR/scripts/pt_summary_from_rpt.py" "$rpt" -o "$out"
    echo "[OK] Wrote summary: $out"
    ;;

  tcl)
    if [[ $# -lt 1 ]]; then
      echo "[ERROR] Missing Tcl input path."
      usage
      exit 1
    fi
    in_tcl="$1"
    out="${2:-${in_tcl}.cfg}"
    python3 "$ROOT_DIR/scripts/tcl_to_cfg.py" "$in_tcl" -o "$out"
    echo "[OK] Wrote cfg: $out"
    ;;

  -h|--help|help)
    usage
    ;;

  *)
    echo "[ERROR] Unknown command: $cmd"
    usage
    exit 1
    ;;
esac
