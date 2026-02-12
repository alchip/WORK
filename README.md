# WORK

Personal/work utilities and notes.

## Contents

- `scripts/` – small helper scripts
  - Detailed docs: [`scripts/README.md`](scripts/README.md)
- `issues` – local notes / scratchpad (format is ad-hoc)

## Scripts quickstart

### `scripts/pt_summary_from_rpt.py`
Generate a `wo_io.rpt.summary`-style summary from a PrimeTime timing report (plain text or `.gz`).

```bash
# Basic
./scripts/pt_summary_from_rpt.py /path/to/report.rpt.gz -o out.summary

# With block mapping
./scripts/pt_summary_from_rpt.py /path/to/report.rpt.gz \
  --block-map-file /path/to/block_map.txt \
  -o out.summary
```

### `scripts/tcl_to_cfg.py`
Convert Tcl `[list]` variable definitions into `.cfg` format.

```bash
# Print to stdout
./scripts/tcl_to_cfg.py input.tcl

# Write to file
./scripts/tcl_to_cfg.py input.tcl -o output.cfg
```

## Clone

```bash
git clone git@github.com:alchip/WORK.git
```

## Contributing / workflow

Typical update cycle:

```bash
git add -A
git commit -m "<message>"
git push
```
