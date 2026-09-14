#!/bin/bash

#PBS -A TellusFM
#PBS -N compgen_raccoon_random
#PBS -l select=2
#PBS -l walltime=01:00:00
#PBS -k doe
#PBS -l place=scatter
#PBS -q debug
# #PBS -q prod
# #PBS -q debug-scaling
# #PBS -q capacity
#PBS -l filesystems=home_fs:flare
#PBS -M bbrunsvik@lanl.gov

echo "PBS script (random sweep) started running. "

# Change to the directory from which the job was submitted
cd $PBS_O_WORKDIR

# Initialize the conda environment for python scripts
module load frameworks
conda activate /home/bbrunsvik/environments/moose

# pbsdsh launches the dummy script on every allocated node. Each node runs the
# full python script independently, drawing its own random samples, so the total
# number of samples = (select nodes) x (number in fracture_random_slurm.json).
echo "Starting pbsdsh from aurora_run_pbs_dsh_random.sh"
pbsdsh /bin/bash "$PBS_O_WORKDIR/aurora_run_pbs_dsh_dummy_random.sh"
