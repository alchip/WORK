# gen_sum.tcl
# Innovus Tcl wrapper for batch summary generation.
#
# Usage inside Innovus:
#   source /Users/sunny/WORK/scripts/gen_sum.tcl
#   gen_sum -path /Users/sunny/WORK/tmp
#
# Options:
#   -path <dir>                 (required) directory containing *.tarpt.gz
#   -suffix <ext>               optional, default .sum
#   -block_map_file <file>      optional, repeatable
#   -block_map <prefix=name>    optional, repeatable
#   -runner <tcsh|bash|auto>    optional, default auto
#
# Examples:
#   gen_sum -path /Users/sunny/WORK/tmp
#   gen_sum -path /Users/sunny/WORK/tmp -suffix .clock.new.sum
#   gen_sum -path /Users/sunny/WORK/tmp -block_map_file /Users/sunny/WORK/scripts/block_map.example.txt

proc gen_sum {args} {
    set script_dir [file dirname [info script]]
    set csh_script [file join $script_dir gen_summaries.csh]
    set sh_script  [file join $script_dir gen_summaries.sh]

    # defaults
    set path ""
    set suffix ""
    set runner "auto"
    set block_map_files {}
    set block_maps {}

    # parse args
    set i 0
    set n [llength $args]
    while {$i < $n} {
        set a [lindex $args $i]
        switch -- $a {
            -path {
                incr i
                if {$i >= $n} { error "-path requires a value" }
                set path [lindex $args $i]
            }
            -suffix {
                incr i
                if {$i >= $n} { error "-suffix requires a value" }
                set suffix [lindex $args $i]
            }
            -block_map_file {
                incr i
                if {$i >= $n} { error "-block_map_file requires a value" }
                lappend block_map_files [lindex $args $i]
            }
            -block_map {
                incr i
                if {$i >= $n} { error "-block_map requires a value" }
                lappend block_maps [lindex $args $i]
            }
            -runner {
                incr i
                if {$i >= $n} { error "-runner requires a value" }
                set runner [lindex $args $i]
            }
            -h -
            --help {
                puts "Usage: gen_sum -path <dir> ?-suffix <ext>? ?-block_map_file <file>? ?-block_map <prefix=name>? ?-runner <tcsh|bash|auto>?"
                return
            }
            default {
                error "Unknown option: $a"
            }
        }
        incr i
    }

    if {$path eq ""} {
        error "Missing required -path"
    }

    if {![file isdirectory $path]} {
        error "Not a directory: $path"
    }

    # choose runner/script
    set cmd {}
    if {$runner eq "tcsh"} {
        if {![file exists $csh_script]} { error "Missing script: $csh_script" }
        set cmd [list tcsh $csh_script -path $path]
    } elseif {$runner eq "bash"} {
        if {![file exists $sh_script]} { error "Missing script: $sh_script" }
        set cmd [list bash $sh_script -path $path]
    } else {
        # auto prefer tcsh script, fallback to bash script
        if {[file exists $csh_script]} {
            set cmd [list tcsh $csh_script -path $path]
        } elseif {[file exists $sh_script]} {
            set cmd [list bash $sh_script -path $path]
        } else {
            error "Neither gen_summaries.csh nor gen_summaries.sh found under $script_dir"
        }
    }

    if {$suffix ne ""} {
        lappend cmd -suffix $suffix
    }

    foreach f $block_map_files {
        lappend cmd -block_map_file $f
    }
    foreach m $block_maps {
        lappend cmd -block_map $m
    }

    puts "gen_sum Running: [join $cmd { }]"

    # Use exec directly (no shell quoting issues)
    set rc [catch {eval exec $cmd} out]
    if {$rc != 0} {
        puts stderr "gen_sum ERROR"
        puts stderr $out
        error "gen_sum failed"
    }

    puts $out
    puts "gen_sum done"
}
