#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

export TMPDIR="$SCRIPT_DIR/simulations/tmp"
mkdir -p "$TMPDIR"

if [[ -z "${CONDA_PREFIX:-}" || "${CONDA_DEFAULT_ENV:-}" != "moose_genesis" ]]; then
    if ! command -v conda >/dev/null 2>&1; then
        echo "conda is not available. Activate moose_genesis before running this script." >&2
        exit 1
    fi
    # Some conda activation hooks reference optional variables such as
    # CONDA_BUILD without defining them. Keep the wrapper strict outside of
    # activation, but allow those hooks to run.
    set +u
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate moose_genesis
    set -u
fi

cd "$SCRIPT_DIR"

# Use the conventional local RACCOON checkout when present. These defaults
# can be overridden for another machine with RACCOON_DIR and
# MOOSE_ADFPARSER_JIT_INCLUDE.
RACCOON_DIR="${RACCOON_DIR:-$HOME/code/raccoon}"
if [[ -x "$RACCOON_DIR/raccoon-opt" ]]; then
    export PATH="$RACCOON_DIR:$PATH"
fi
if [[ -z "${MOOSE_ADFPARSER_JIT_INCLUDE:-}" && -f "$RACCOON_DIR/ADRealMonolithic.h" ]]; then
    export MOOSE_ADFPARSER_JIT_INCLUDE="$RACCOON_DIR/ADRealMonolithic.h"
fi

# The launcher is stored four levels below the repository root.  Make the
# repository package importable even when this script is started elsewhere.
export PYTHONPATH="$(cd "$SCRIPT_DIR/../../../.." && pwd)${PYTHONPATH:+:$PYTHONPATH}"

if ! python -c 'import exodusii' >/dev/null 2>&1; then
    echo "Missing Python dependency: exodusii" >&2
    echo "Install it in moose_genesis with:" >&2
    echo "  python -m pip install 'exodusii @ git+https://github.com/sandialabs/exodusii.git@main'" >&2
    exit 1
fi

if ! command -v raccoon-opt >/dev/null 2>&1; then
    echo "RACCOON executable was not found on PATH: raccoon-opt" >&2
    exit 1
fi

if [[ -z "${MOOSE_ADFPARSER_JIT_INCLUDE:-}" || ! -f "$MOOSE_ADFPARSER_JIT_INCLUDE" ]]; then
    echo "RACCOON JIT support is not configured." >&2
    echo "The RACCOON executable requires MOOSE's generated ADRealMonolithic.h header." >&2
    echo "Set MOOSE_ADFPARSER_JIT_INCLUDE to the matching ADRealMonolithic.h path." >&2
    exit 1
fi

exec python "$SCRIPT_DIR/run_fracture_predefined_local.py"