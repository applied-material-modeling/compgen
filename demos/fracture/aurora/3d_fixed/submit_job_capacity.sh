#!/bin/bash

# Debug version of submit_job.sh. The job is intentionally limited to
# one Aurora node and one hour; the 3D setup check may be truncated by the
# walltime limit.
#PBS -A TellusFM
#PBS -N compgen_raccoon_3d_fixed_debug
#PBS -l select=2
#PBS -l walltime=48:00:00
#PBS -k doe
#PBS -l place=scatter
#PBS -q capacity
#PBS -l filesystems=home_fs:flare
#PBS -M bbrunsvik@lanl.gov

echo "Aurora 3D fixed PBS debug script started running."

# Change to the directory from which the job was submitted.
cd "$PBS_O_WORKDIR"

# Initialize the conda environment for python scripts
module load frameworks
conda activate /home/bbrunsvik/environments/moose

echo "Starting pbsdsh from submit_job_debug.sh"
pbsdsh /bin/bash "$PBS_O_WORKDIR/dummy_dsh.sh"