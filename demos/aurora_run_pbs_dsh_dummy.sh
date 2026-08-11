#!/bin/bash

# Trying this, following Mark's example. module was not available. 
source /etc/bash.bashrc

echo "Dummy script started running. "

# Change to the directory from which the job was submitted
cd $PBS_O_WORKDIR

# Initialize the conda environment for python scripts
module load frameworks
conda activate /home/bbrunsvik/environments/moose

# The python script will use multiprocess internally to map jobs over the PBS environment 
echo "Executing aurora_run_fracture_predefined.py from dummy script"
python aurora_run_fracture_predefined.py

### Run Compgen end