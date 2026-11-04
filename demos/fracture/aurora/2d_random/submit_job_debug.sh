#!/bin/bash

# Debug version of submit_job_large.sh. The job is intentionally
# limited to one Aurora node and one hour; the simulation sweep may be
# truncated by the walltime limit.
#PBS -A TellusFM
#PBS -N compgen_raccoon_random_debug
#PBS -l select=1
#PBS -l walltime=01:00:00
#PBS -k doe
#PBS -l place=scatter
#PBS -q debug
#PBS -l filesystems=home_fs:flare
#PBS -M bbrunsvik@lanl.gov

echo "PBS debug script (random sweep) started running."

# Change to the directory from which the job was submitted.
cd "$PBS_O_WORKDIR"

# Initialize the conda environment for python scripts
module load frameworks
conda activate /home/bbrunsvik/environments/moose

# The one allocated node runs the full random sweep independently.
echo "Starting pbsdsh from submit_job_debug.sh"
pbsdsh /bin/bash "$PBS_O_WORKDIR/dummy_dsh.sh"