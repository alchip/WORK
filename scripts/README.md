# WORK/scripts

Small utility scripts used in the `alchip/WORK` repo.

## Requirements

- Python 3.9+ (both scripts are `python3`)

## Scripts

### 1) `pt_summary_from_rpt.py`

Generate a `wo_io.rpt.summary`-style summary from a PrimeTime timing report.

**Input**
- Plain text PT report
- Or gzipped report (`.gz`)

It is tailored to reports similar to `PrimeTime report_timing -nosplit ...` output, where each path block contains:
- `Startpoint:`
- `Endpoint:`
- `Path Group:`
- `Point` table
- `data arrival time`
- `slack ... <value>`

**Basic usage**

```bash
./pt_summary_from_rpt.py /path/to/wo_io.rpt.gz -o /path/to/out.summary
```

**Block mapping (optional)**

By default, the script uses the first hierarchy token as the “block” name.
You can override this with longest-prefix mapping.

Mapping file format (one per line):

```text
# prefix -> block_name
m_misc/m_max_buf/ -> m_max_buf
m_misc/m_abuf/    -> m_abuf
```

Run with mapping file(s):

```bash
./pt_summary_from_rpt.py /path/to/wo_io.rpt.gz \
  --block-map-file /path/to/block_map.txt \
  -o /path/to/out.summary
```

Other options:
- `--block-map prefix=name` (repeatable)
- `--range-groups reg2reg,reg2cgate` (comma-separated)

---

### 2) `tcl_to_cfg.py`

Convert simple Tcl list-style variable definitions into `.cfg` format.

**Supported input pattern**

```tcl
set liblist(LEF_STD) [list \
    /path/a \
    /path/b] ;
```

**Output pattern**

```cfg
[liblist]
# Author: sunnyy@alchip.com
# Created: YYYY-MM-DD

LEF_STD       = /path/a
                /path/b
```

**Usage**

```bash
# Print to stdout
./tcl_to_cfg.py input.tcl

# Write to file
./tcl_to_cfg.py input.tcl -o output.cfg
```

Common options:
- `--section liblist` (section header name)
- `--author sunnyy@alchip.com`
- `--created 2026-02-12`
- `--name-width 12`
- `--indent-width 16`

## Notes

- If you want to run without `chmod +x`, use `python3 script.py ...`.
- Keep repo-specific / proprietary examples out of the README; use paths/placeholders.
