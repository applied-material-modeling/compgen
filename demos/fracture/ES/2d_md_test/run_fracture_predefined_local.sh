#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# The selected case determines separate outputs, logs, and temporary files below
# simulations/. The default preserves the original direct-run behavior.
which_case="${1:-case2}"

if [[ "$which_case" != "case0" && "$which_case" != "case1" && "$which_case" != "case2" ]]; then
    echo "Invalid which_case='$which_case'; choose case0, case1, or case2." >&2
    exit 1
fi

RACCOON_ENV_PREFIX="${RACCOON_ENV_PREFIX:-/home/bbrunsvik/.conda/envs/moose_genesis}"
RACCOON_DIR="${RACCOON_DIR:-/home/bbrunsvik/code/raccoon}"

export TMPDIR="$SCRIPT_DIR/simulations/$which_case/tmp"
mkdir -p "$TMPDIR"

if [[ "${CONDA_PREFIX:-}" != "$RACCOON_ENV_PREFIX" ]]; then
    if ! command -v conda >/dev/null 2>&1; then
        echo "conda is not available. Activate $RACCOON_ENV_PREFIX before running this script." >&2
        exit 1
    fi
    # Some conda activation hooks reference optional variables such as
    # CONDA_BUILD without defining them. Keep the wrapper strict outside of
    # activation, but allow those hooks to run.
    set +u
    source "$(conda info --base)/etc/profile.d/conda.sh"
    conda activate "$RACCOON_ENV_PREFIX"
    set -u
fi

cd "$SCRIPT_DIR"

# Use the compiled RACCOON checkout associated with the environment. The
# default can be overridden for another machine with RACCOON_DIR.
if [[ -x "$RACCOON_DIR/raccoon-opt" ]]; then
    export PATH="$RACCOON_DIR:$PATH"
fi

# The launcher is stored four levels below the repository root.  Make the
# repository package importable even when this script is started elsewhere.
export PYTHONPATH="$(cd "$SCRIPT_DIR/../../../.." && pwd)${PYTHONPATH:+:$PYTHONPATH}"

if ! python -c 'import exodusii' >/dev/null 2>&1; then
    echo "Missing Python dependency: exodusii" >&2
    echo "Install it in the raccoon environment with:" >&2
    echo "  python -m pip install 'exodusii @ git+https://github.com/sandialabs/exodusii.git@main'" >&2
    exit 1
fi

if ! command -v raccoon-opt >/dev/null 2>&1; then
    echo "RACCOON executable was not found on PATH: raccoon-opt" >&2
    exit 1
fi

export COMPGEN_FRACTURE_CASE="$which_case"
exec python "$SCRIPT_DIR/run_fracture_predefined_local.py"