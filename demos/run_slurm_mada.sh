#!/bin/bash

# Submit this script with: sbatch run_slurm.sh

#SBATCH --time=00:30:00
#SBATCH -N 4
#SBATCH --job-name=compgen_parallel_brb
#SBATCH --output=JOB_%j.out
#SBATCH --error=JOB_%j.err
#SBATCH --mail-user=bbrunsvik@lanl.gov
#SBATCH --reservation=hbm_debug
#SBATCH --qos=hbm_debug 


# Initialize the conda environment for python scripts
module load PrgEnv-gnu # MADA can't run the job without this line. 
module load cray-mpich # MADA can't run the job without this line. 
source /usr/projects/hpcsoft/pe/installs/cos3-x86_64/anaconda/2024.10/etc/profile.d/conda.sh
conda activate /users/bbrunsvik/miniconda3/envs/racoon
# Set environment for CompGen
export COMPGEN_PATH="/lustre/roscratch1/bbrunsvik/compgen_20260619/compgen"
export PYTHONPATH="${COMPGEN_PATH}:${PYTHONPATH}"

# The python script will use multiprocess internally to map jobs over srun --exclusive --exact
python run_fracture_predefined_slurm.py