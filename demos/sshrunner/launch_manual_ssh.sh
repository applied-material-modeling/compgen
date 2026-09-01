#!/usr/bin/env bash
set -u

# Directory containing this launch script: .../demos/sshrunner
SSHRUNNER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parent demos directory: .../demos
DEMOS_DIR="$(cd "$SSHRUNNER_DIR/.." && pwd)"

# Default nodefile lives inside sshrunner
NODEFILE="${1:-$SSHRUNNER_DIR/nodes_manual_1node.txt}"

# If user passes just "nodes_manual_1node.txt", look for it in sshrunner
if [[ ! -f "$NODEFILE" && -f "$SSHRUNNER_DIR/$NODEFILE" ]]; then
    NODEFILE="$SSHRUNNER_DIR/$NODEFILE"
fi

PARALLEL="${PARALLEL:-1}"

# Script that actually runs on each compute node
RUN_SCRIPT="$SSHRUNNER_DIR/aurora_run_pbs_dsh_dummy_manual.sh"

LOGDIR="/home/bbrunsvik/manual_ssh_logs"

mkdir -p "$LOGDIR"

echo "Node file:$NODEFILE"
echo "Parallel:  $PARALLEL"
echo "Demos dir:$DEMOS_DIR"
echo "Runner:    $RUN_SCRIPT"
echo "Logs:$LOGDIR"

if [[ ! -f "$NODEFILE" ]]; then
    echo "ERROR: node file not found:$NODEFILE" >&2
    exit 1
fi

if [[ ! -f "$RUN_SCRIPT" ]]; then
    echo "ERROR: run script not found:$RUN_SCRIPT" >&2
    exit 1
fi

grep -v '^[[:space:]]*$' "$NODEFILE" | xargs -r -P "$PARALLEL" -I {} bash -c '
h="$1"
DEMOS_DIR="$2"
RUN_SCRIPT="$3"
LOGDIR="$4"

echo "Launching on$h"

ssh -o BatchMode=yes -o ConnectTimeout=10 "$h" "
    set -e

    mkdir -p \"$LOGDIR\"

    cd \"$DEMOS_DIR\"

    if [ ! -f \"$RUN_SCRIPT\" ]; then
        echo \"ERROR: run script not found on remote node: $RUN_SCRIPT\" >&2
        exit 2
    fi

    nohup bash \"$RUN_SCRIPT\" > \"$LOGDIR/${h}.out\" 2> \"$LOGDIR/${h}.err\" < /dev/null &

    pid=\$!
    echo \$pid > /tmp/bbrunsvik_aurora_manual.pid

    sleep 1

    if ps -p \$pid > /dev/null 2>&1; then
        echo \"started pid=\$pid on \$(hostname)\"
        exit 0
    else
        echo \"FAILED: process exited immediately on \$(hostname)\" >&2
        echo \"--- stderr: $LOGDIR/${h}.err ---\" >&2
        tail -n 80 \"$LOGDIR/${h}.err\" >&2 || true
        exit 1
    fi
"

rc=$?

if [ "$rc" -eq 0 ]; then
    echo "SUCCESS $h"
else
    echo "FAILED$h rc=$rc"
fi
' _ {} "$DEMOS_DIR" "$RUN_SCRIPT" "$LOGDIR"

echo "Done launching."