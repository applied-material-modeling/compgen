#!/bin/bash

# Random-material sweep variant of dummy_dsh.sh.
# Trying this, following Mark's example. module was not available.
source /etc/bash.bashrc

### Handle logging. Make sure each node gets its own log.
logdir=/lus/flare/projects/ai4ns-composites/brennan/fracture_simulations/2d_random
mkdir -p "$logdir"
exec > "$logdir/$(hostname).out" 2> "$logdir/$(hostname).err"

echo "Dummy script (random sweep) started running. Using version from 2026/09/14. "

# Run the demo from the directory containing this launcher.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Initialize the conda environment for python scripts
module load frameworks
conda activate /home/bbrunsvik/environments/moose

# The python script will use multiprocess internally to map jobs over the PBS environment
echo "Executing dummy_start_compgen.py from dummy script"
python "$SCRIPT_DIR/dummy_start_compgen.py"

### Run Compgen end
