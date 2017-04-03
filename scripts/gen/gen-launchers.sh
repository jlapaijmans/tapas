#!/bin/sh
set -ue

## This script generates launchers for every script in the scripts
## directory. The purpose of the launchers is to set the appropriate
## library paths before R or Python are started which run the actual 
## script.   

# Directory this script lives in 
thisdir="$(dirname "$(readlink -f "$0")")"
# Directory the launchers are written to
launcher_dir="${thisdir}/.."
# Directory there the scripts for which the launchers are written
# live in. Given relative to $launcher_dir
scriptsdir="src"

# Usage:   generate_launcher SCRIPT LAUNCHER_FUNCTION
# Purpose: Output a launcher script. 
# Parameters:
#   SCRIPTNAME:        Script path relative to launcher
#   LAUNCHER_FUNCTION: File in $thisdir containing a function
#                      of the same name which starts SCRIPTNAME with 
#                      the appropriate interpreter. 
function generate_launcher(){
    scriptname="$1"
    launcher_function="$2"

    echo "#!/bin/sh"
    echo "## Launch the script ${scriptname}."
    echo "## Set appropriate environment variables in advance."
    echo "## See the help of the launched scripts by invoking"
    echo "## this script with the --help option."
    echo 
    echo "# This launcher was automatically generated by"
    echo "# gen/gen-launchers.sh"
    echo 
    echo "## ----- Launcher follows -----------------------------"
    echo 
    cat "${thisdir}/${launcher_function}"
    echo 
    echo "# Directory this script lives in"
    echo 'thisdir="$(dirname "$(readlink -f "$0")")"'
    echo "# Launch the script and forward all command line arguments"
    # "${thisdir}" and $@ must be written in the launcher literally!
    echo $launcher_function "${scriptname}" '"${thisdir}"' '"$@"'

}

function generate_deprecated_launcher(){
    deprecated_scriptname="$1"
    new_scriptname="$2"
    launcher_function="$3"

    echo "#!/bin/sh"
    echo "## Launch the script ${deprecated_scriptname}."
    echo "## This is DEPRECATED. You should rather use ${new_scriptname}"
    echo 
    echo "# This launcher was automatically generated by"
    echo "# gen/gen-launchers.sh"
    echo 
    echo "## ----- Launcher follows -----------------------------"
    echo 
    cat "${thisdir}/${launcher_function}"
    echo 
    echo "# Directory this script lives in"
    echo 'thisdir="$(dirname "$(readlink -f "$0")")"'
    echo "# Launch the script and forward all command line arguments"
    # "${thisdir}" and $@ must be written in the launcher literally!
    echo "echo 'Using the function ${deprecated_scriptname} is DEPRECATED.'\\"
    echo "     'Use "${new_scriptname}" instead.' >&2 "
    echo $launcher_function "${new_scriptname}" '"${thisdir}"' '"$@"'

}

# This enables outputting relative paths in the subseqent `ls`
# commmands
cd "$launcher_dir"

# Generate python launchers for every python script
for py in $(ls "$scriptsdir"/*.py); do
    # Write a launcher which has the same name as the script,
    # but without the extension and in the launcher directory,
    # not in `src/`.
    launcher_name="${launcher_dir}/$(basename "${py%.py}")"
    generate_launcher "${py}" python_launch \
        > "${launcher_name}"

    chmod u+x "${launcher_name}"
done

# Generate R launchers for every python script
for r in $(ls "$scriptsdir"/*.R); do
    # Write a launcher which has the same name as the script,
    # but without the extension and in the launcher directory,
    # not in `src/`.
    launcher_name="${launcher_dir}/$(basename "${r%.R}")"
    generate_launcher "${r}" r_launch \
        > "${launcher_name}"

    chmod u+x "${launcher_name}"
done

for sh in $(ls "$scriptsdir"/*.sh); do
    # Write a launcher which has the same name as the script,
    # but without the extension and in the launcher directory,
    # not in `src/`.
    launcher_name="${launcher_dir}/$(basename "${sh%.sh}")"
    generate_launcher "${sh}" sh_launch \
        > "${launcher_name}"

    chmod u+x "${launcher_name}"
done

declare -A deprecated
deprecated[filter-fastq]=filter_fastq
deprecated[index-column]=index_column
deprecated[plot-read-fate]=plot_read_fate
deprecated[preview]=plot_mutation_probabilities
deprecated[sam-extract]=sam_extract
deprecated[synth-fastq]=synth_fastq
for d in "${!deprecated[@]}"; do 
    n="${deprecated[$d]}"
    generate_deprecated_launcher "${d}" "${n}" sh_launch \
        > "${d}"
    chmod u+x "${d}"
done

# vim:ft=sh

