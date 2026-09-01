#!/bin/bash

# Trying this, following Mark's example. module was not available. 
source /etc/bash.bashrc

### Handle logging. Make sure each node gets its own log. 
logdir=/lus/flare/projects/ai4ns-composites/brennan/fracture_simulations/logs
mkdir -p "$logdir"
exec > "$logdir/$(hostname).out" 2> "$logdir/$(hostname).err"

echo "Dummy script started running. Using version from 2026/09/01. "

# Change to the directory from which the job was submitted
cd $PBS_O_WORKDIR

# Initialize the conda environment for python scripts
module load frameworks
conda activate /home/bbrunsvik/environments/moose

# The python script will use multiprocess internally to map jobs over the PBS environment 
echo "Executing aurora_run_fracture_predefined.py from dummy script"
python aurora_run_fracture_predefined.py

### Run Compgen end