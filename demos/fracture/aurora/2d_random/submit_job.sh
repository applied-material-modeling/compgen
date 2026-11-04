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

# Run the demo from the directory containing this launcher. This keeps all
# relative demo inputs local even when PBS_O_WORKDIR is set differently.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Initialize the conda environment for python scripts
module load frameworks
conda activate /home/bbrunsvik/environments/moose

# pbsdsh launches the dummy script on every allocated node. Each node runs the
# full python script independently, drawing its own random samples, so the total
# number of samples = (select nodes) x (number in config_fracture.json).
echo "Starting pbsdsh from submit_job.sh"
pbsdsh /bin/bash "$SCRIPT_DIR/dummy_dsh.sh"
