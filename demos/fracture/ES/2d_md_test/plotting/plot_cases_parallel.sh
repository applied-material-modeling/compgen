#!/usr/bin/env bash
# Run one plotting process per case. Each process is given one interpolation
# worker by default to avoid multiplying the number of processes.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLOT_SCRIPT="$SCRIPT_DIR/plot.py"
LOG_DIR="$SCRIPT_DIR/logs"
PYTHON="${PYTHON:-/home/bbrunsvik/.conda/envs/moose_genesis/bin/python}"
INNER_WORKERS="${INNER_WORKERS:-1}"

if [[ ! -x "$PYTHON" ]]; then
    echo "Python executable not found or not executable: $PYTHON" >&2
    echo "Set PYTHON=/path/to/python or activate moose_genesis and use PYTHON=python." >&2
    exit 1
fi

if ! [[ "$INNER_WORKERS" =~ ^[1-9][0-9]*$ ]]; then
    echo "INNER_WORKERS must be a positive integer (got: $INNER_WORKERS)" >&2
    exit 1
fi

if (( $# == 0 )); then
    cases=(case{0..10})
else
    cases=("$@")
fi

mkdir -p "$LOG_DIR"
declare -a pids
declare -a case_names

echo "Starting ${#cases[@]} plotting processes with $INNER_WORKERS inner worker(s) each."
for case_name in "${cases[@]}"; do
    if [[ ! "$case_name" =~ ^case([0-9]|10)$ ]]; then
        echo "Invalid case name: $case_name (expected case0 through case10)" >&2
        exit 1
    fi

    log_file="$LOG_DIR/${case_name}.log"
    echo "  $case_name -> $log_file"
    "$PYTHON" "$PLOT_SCRIPT" --case "$case_name" --workers "$INNER_WORKERS" \
        > >(tee "$log_file") 2>&1 &
    pids+=("$!")
    case_names+=("$case_name")
done

failed=0
for index in "${!pids[@]}"; do
    if wait "${pids[$index]}"; then
        echo "Finished ${case_names[$index]} successfully."
    else
        status=$?
        echo "${case_names[$index]} failed with exit status $status; see $LOG_DIR/${case_names[$index]}.log" >&2
        failed=1
    fi
done

if (( failed )); then
    exit 1
fi

echo "All requested plotting processes completed successfully."