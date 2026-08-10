# Change to the directory from which the job was submitted
# cd $PBS_O_WORKDIR

# Initialize the conda environment for python scripts
# module load miniforge3 
# conda activate /home/bbrunsvik/environments/moose
module load frameworks
source /lus/flare/projects/ai4ns-composites/packages/moose-env/bin/activate

# The python script will use multiprocess internally to map jobs over the PBS environment
python aurora_run_fracture_predefined.py