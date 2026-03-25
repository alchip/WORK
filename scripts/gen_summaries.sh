#!/usr/bin/env bash
set -euo pipefail

# One-click batch summary generation:
#   scan a directory for *.tarpt.gz
#   generate same-name .sum next to each input
#
# Usage:
#   ./scripts/gen_summaries.sh -path /Users/sunny/WORK/tmp
#   ./scripts/gen_summaries.sh -path ./tmp --suffix .clock.new.sum
#   ./scripts/gen_summaries.sh -path ./tmp --block-map-file ./scripts/block_map.example.txt

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$SCRIPT_DIR/innovus_tarpt_to_sum.py"

TARGET_PATH=""
SUFFIX=".sum"
EXTRA_ARGS=()

usage() {
  cat <<'EOF'
Usage:
  gen_summaries.sh -path <dir> [options]

Required:
  -path <dir>                    Directory containing *.tarpt.gz

Options:
  --suffix <ext>                 Output suffix (default: .sum)
                                 Example: --suffix .clock.new.sum
  --block-map-file <file>        Pass-through (repeatable)
  --block-map <prefix=name>      Pass-through (repeatable)
  -h, --help                     Show help

Behavior:
  For each <name>.tarpt.gz under -path:
    output => <name><suffix>

Examples:
  ./scripts/gen_summaries.sh -path /Users/sunny/WORK/tmp
  ./scripts/gen_summaries.sh -path /Users/sunny/WORK/tmp --suffix .clock.new.sum
  ./scripts/gen_summaries.sh -path /Users/sunny/WORK/tmp --block-map-file ./scripts/block_map.example.txt
EOF
}

if [[ $# -eq 0 ]]; then
  usage
  exit 1
fi

while [[ $# -gt 0 ]]; do
  case "$1" in
    -path)
      if [[ $# -lt 2 ]]; then
        echo "[ERROR] -path requires a value" >&2
        exit 1
      fi
      TARGET_PATH="$2"
      shift 2
      ;;
    --suffix)
      if [[ $# -lt 2 ]]; then
        echo "[ERROR] --suffix requires a value" >&2
        exit 1
      fi
      SUFFIX="$2"
      shift 2
      ;;
    --block-map-file|--block-map)
      if [[ $# -lt 2 ]]; then
        echo "[ERROR] $1 requires a value" >&2
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

if [[ -z "$TARGET_PATH" ]]; then
  echo "[ERROR] Missing required -path" >&2
  usage
  exit 1
fi

if [[ ! -d "$TARGET_PATH" ]]; then
  echo "[ERROR] Not a directory: $TARGET_PATH" >&2
  exit 1
fi

if [[ ! -f "$PY" ]]; then
  echo "[ERROR] Missing parser script: $PY" >&2
  exit 1
fi

shopt -s nullglob
files=("$TARGET_PATH"/*.tarpt.gz)
shopt -u nullglob

if [[ ${#files[@]} -eq 0 ]]; then
  echo "[INFO] No .tarpt.gz files found in: $TARGET_PATH"
  exit 0
fi

count=0
for rpt in "${files[@]}"; do
  base="${rpt%.tarpt.gz}"
  out="${base}${SUFFIX}"
  echo "[RUN ] $(basename "$rpt") -> $(basename "$out")"
  if [[ ${#EXTRA_ARGS[@]} -gt 0 ]]; then
    python3 "$PY" "$rpt" -o "$out" "${EXTRA_ARGS[@]}"
  else
    python3 "$PY" "$rpt" -o "$out"
  fi
  count=$((count+1))
done

echo "[DONE] Generated $count summary file(s) in: $TARGET_PATH"
