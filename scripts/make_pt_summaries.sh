#!/usr/bin/env bash
set -euo pipefail

# Batch-generate PT summary files from *.tarpt.gz reports.
#
# Default behavior:
#   input : <dir>/*.tarpt.gz
#   output: <dir>/<same basename>.sum
#
# Usage:
#   ./scripts/make_pt_summaries.sh [dir]
#   ./scripts/make_pt_summaries.sh tmp
#   ./scripts/make_pt_summaries.sh tmp --overwrite
#   ./scripts/make_pt_summaries.sh tmp --block-map-file /path/block_map.txt

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PT_SUMMARY_PY="$ROOT_DIR/scripts/pt_summary_from_rpt.py"

usage() {
  cat <<'EOF'
Usage:
  ./scripts/make_pt_summaries.sh [dir] [options]

Arguments:
  dir                         Directory containing *.tarpt.gz files (default: .)

Options:
  --overwrite                 Overwrite existing .sum files
  --block-map-file <file>     Pass-through to pt_summary_from_rpt.py (repeatable)
  --block-map <prefix=name>   Pass-through to pt_summary_from_rpt.py (repeatable)
  --range-groups <csv>        Pass-through, e.g. reg2reg,reg2cgate
  -h, --help                  Show this help
EOF
}

DIR="."
OVERWRITE=0
EXTRA_ARGS=()

if [[ $# -gt 0 && "${1:-}" != --* ]]; then
  DIR="$1"
  shift
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    --overwrite)
      OVERWRITE=1
      shift
      ;;
    --block-map-file|--block-map|--range-groups)
      if [[ $# -lt 2 ]]; then
        echo "[ERROR] Missing value for $1" >&2
        exit 1
      fi
      EXTRA_ARGS+=("$1" "$2")
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] Unknown option: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ ! -d "$DIR" ]]; then
  echo "[ERROR] Directory not found: $DIR" >&2
  exit 1
fi

shopt -s nullglob
files=("$DIR"/*.tarpt.gz)
shopt -u nullglob

if [[ ${#files[@]} -eq 0 ]]; then
  echo "[INFO] No *.tarpt.gz files found under: $DIR"
  exit 0
fi

count=0
for rpt in "${files[@]}"; do
  out="${rpt%.tarpt.gz}.sum"

  if [[ -f "$out" && $OVERWRITE -ne 1 ]]; then
    echo "[SKIP] Exists: $out (use --overwrite to regenerate)"
    continue
  fi

  echo "[RUN ] $rpt -> $out"
  if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    python3 "$PT_SUMMARY_PY" "$rpt" -o "$out" "${EXTRA_ARGS[@]}"
  else
    python3 "$PT_SUMMARY_PY" "$rpt" -o "$out"
  fi
  count=$((count + 1))
done

echo "[DONE] Generated $count summary file(s)."
