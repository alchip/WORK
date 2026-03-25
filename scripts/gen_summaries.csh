#!/bin/tcsh -f

# One-click batch summary generation (tcsh):
#   scan a directory for *.tarpt.gz
#   generate same-name .sum next to each input
#
# Usage:
#   ./scripts/gen_summaries.csh -path /Users/sunny/WORK/tmp
#   ./scripts/gen_summaries.csh -path /Users/sunny/WORK/tmp -suffix .clock.new.sum
#   ./scripts/gen_summaries.csh -path /Users/sunny/WORK/tmp -block_map_file ./scripts/block_map.example.txt

set script_path="$0"
if ( "$script_path" !~ /* ) then
  set script_path="$cwd/$script_path"
endif
set script_dir=`dirname "$script_path"`
set py="$script_dir/innovus_tarpt_to_sum.py"

set target_path=""
set suffix=".sum"
set extra_args=()

if ( $#argv == 0 ) then
  echo "Usage: gen_summaries.csh -path <dir> [-suffix <ext>] [-block_map_file <file>] [-block_map <prefix=name>]"
  exit 1
endif

set i=1
while ( $i <= $#argv )
  set a="$argv[$i]"

  if ( "$a" == "-path" ) then
    @ i++
    if ( $i > $#argv ) then
      echo "[ERROR] -path requires value"
      exit 1
    endif
    set target_path="$argv[$i]"

  else if ( "$a" == "-suffix" ) then
    @ i++
    if ( $i > $#argv ) then
      echo "[ERROR] -suffix requires value"
      exit 1
    endif
    set suffix="$argv[$i]"

  else if ( "$a" == "-block_map_file" ) then
    @ i++
    if ( $i > $#argv ) then
      echo "[ERROR] -block_map_file requires value"
      exit 1
    endif
    set extra_args=( $extra_args --block-map-file "$argv[$i]" )

  else if ( "$a" == "-block_map" ) then
    @ i++
    if ( $i > $#argv ) then
      echo "[ERROR] -block_map requires value"
      exit 1
    endif
    set extra_args=( $extra_args --block-map "$argv[$i]" )

  else if ( "$a" == "-h" || "$a" == "--help" ) then
    echo "Usage: gen_summaries.csh -path <dir> [-suffix <ext>] [-block_map_file <file>] [-block_map <prefix=name>]"
    exit 0

  else
    echo "[ERROR] Unknown option: $a"
    exit 1
  endif

  @ i++
end

if ( "$target_path" == "" ) then
  echo "[ERROR] Missing -path"
  exit 1
endif

if ( ! -d "$target_path" ) then
  echo "[ERROR] Not a directory: $target_path"
  exit 1
endif

if ( ! -f "$py" ) then
  echo "[ERROR] Missing parser script: $py"
  exit 1
endif

set files=( "$target_path"/*.tarpt.gz )
if ( "$files[1]" == "$target_path/*.tarpt.gz" ) then
  echo "[INFO] No .tarpt.gz files found in: $target_path"
  exit 0
endif

set count=0
foreach rpt ( $files )
  set base="$rpt"
  set base=`echo "$base" | sed 's/\.tarpt\.gz$//'`
  set out="${base}${suffix}"
  set rpt_name=`basename "$rpt"`
  set out_name=`basename "$out"`

  echo "[RUN ] $rpt_name -> $out_name"
  if ( $#extra_args > 0 ) then
    python3 "$py" "$rpt" -o "$out" $extra_args
  else
    python3 "$py" "$rpt" -o "$out"
  endif

  @ count++
end

echo "[DONE] Generated $count summary file(s) in: $target_path"
