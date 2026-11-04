#!/bin/bash

#PBS -A TellusFM 
#PBS -N compgen_raccoon
#PBS -l select=256
#PBS -l walltime=12:00:00
#PBS -k doe
#PBS -l place=scatter
#PBS -q prod
# #PBS -q debug
# #PBS -q debug-scaling
# #PBS -q capacity
#PBS -l filesystems=home_fs:flare
#PBS -M bbrunsvik@lanl.gov

echo "PBS script started running. "

# Change to the directory from which the job was submitted.
cd "$PBS_O_WORKDIR"

# Initialize the conda environment for python scripts
module load frameworks
conda activate /home/bbrunsvik/environments/moose

echo "Starting pbsdsh from submit_job_large.sh"
pbsdsh /bin/bash "$PBS_O_WORKDIR/dummy_dsh.sh"


