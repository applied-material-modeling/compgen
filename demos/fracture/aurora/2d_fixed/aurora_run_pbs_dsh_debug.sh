#!/bin/bash

# Debug version of aurora_run_pbs_dsh.sh. The job is intentionally limited to
# one Aurora node and one hour; the simulation sweep may be truncated by the
# walltime limit.
#PBS -A TellusFM
#PBS -N compgen_raccoon_debug
#PBS -l select=1
#PBS -l walltime=01:00:00
#PBS -k doe
#PBS -l place=scatter
#PBS -q debug
#PBS -l filesystems=home_fs:flare
#PBS -M bbrunsvik@lanl.gov

echo "PBS debug script started running."

# Run the demo from the directory containing this launcher. This keeps all
# relative demo inputs local even when PBS_O_WORKDIR is set differently.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Initialize the conda environment for python scripts
module load frameworks
conda activate /home/bbrunsvik/environments/moose

echo "Starting pbsdsh from aurora_run_pbs_dsh_debug.sh"
pbsdsh /bin/bash "$SCRIPT_DIR/aurora_run_pbs_dsh_dummy.sh"