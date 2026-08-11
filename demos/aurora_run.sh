# brb2026/08/11 This old file is probably not working anymore. 

# Change to the directory from which the job was submitted
cd $PBS_O_WORKDIR

# Initialize the conda environment for python scripts
# module load miniforge3 
# conda activate /home/bbrunsvik/environments/moose
module load frameworks
# source /lus/flare/projects/ai4ns-composites/packages/moose-env/bin/activate
# source /home/bbrunsvik/environments/moose/bin
conda activate /home/bbrunsvik/environments/moose

# The python script will use multiprocess internally to map jobs over the PBS environment
python aurora_run_fracture_predefined.py