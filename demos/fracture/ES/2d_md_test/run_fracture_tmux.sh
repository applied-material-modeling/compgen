#!/usr/bin/env bash

# tmux cheat sheet:
#   List sessions:                 tmux ls
#   Attach to a session:           tmux attach -t fracture-case1
#   Detach without stopping it:    Ctrl-b, then d
#   Kill without attaching:        tmux kill-session -t fracture-case1

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
shopt -s nullglob

config_files=("$SCRIPT_DIR"/config_case*.json)
if ((${#config_files[@]} == 0)); then
    echo "No config_case*.json files found in $SCRIPT_DIR" >&2
    exit 1
fi

for config_file in "${config_files[@]}"; do
    filename="$(basename "$config_file")"
    case_name="${filename#config_}"
    case_name="${case_name%.json}"
    session_name="fracture-${case_name}"

    if tmux has-session -t "$session_name" 2>/dev/null; then
        echo "Skipping $case_name: tmux session $session_name already exists."
        continue
    fi

    tmux new-session -d -s "$session_name" \
        "exec '$SCRIPT_DIR/run_fracture_predefined_local.sh' '$case_name'"
    echo "Started $case_name in tmux session $session_name"
done