#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

export TMPDIR="/tmp/brb"
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

# The launcher is stored two levels below the repository root.  Make the
# repository package importable even when this script is started elsewhere.
export PYTHONPATH="$(cd "$SCRIPT_DIR/../.." && pwd)${PYTHONPATH:+:$PYTHONPATH}"

if ! python -c 'import exodusii' >/dev/null 2>&1; then
    echo "Missing Python dependency: exodusii" >&2
    echo "Install it in moose_genesis with:" >&2
    echo "  python -m pip install 'exodusii @ git+https://github.com/sandialabs/exodusii.git@main'" >&2
    exit 1
fi

if [[ ! -x /home/bbrunsvik/code/raccoon/raccoon-opt ]]; then
    echo "RACCOON executable is missing or not executable:" >&2
    echo "  /home/bbrunsvik/code/raccoon/raccoon-opt" >&2
    exit 1
fi

RACCOON_JIT_HEADER="/home/bbrunsvik/code/raccoon/ADRealMonolithic.h"
if [[ -n "${MOOSE_ADFPARSER_JIT_INCLUDE:-}" ]]; then
    RACCOON_JIT_HEADER="$MOOSE_ADFPARSER_JIT_INCLUDE"
fi

if [[ ! -f "$RACCOON_JIT_HEADER" ]]; then
    echo "RACCOON JIT support is not configured." >&2
    echo "The RACCOON executable requires MOOSE's generated ADRealMonolithic.h header." >&2
    echo "Expected matching header: $RACCOON_JIT_HEADER" >&2
    echo "Generate it from the embedded MOOSE checkout with:" >&2
    echo "  cd /home/bbrunsvik/code/raccoon && make ADRealMonolithic.h" >&2
    exit 1
fi

export MOOSE_ADFPARSER_JIT_INCLUDE="$RACCOON_JIT_HEADER"

exec python "$SCRIPT_DIR/run_fracture_predefined_local.py"