#!/bin/bash

# Submit this script with: sbatch run_benchmark_slurm.sh

#SBATCH --time=02:00:00
#SBATCH -N 1
#SBATCH --ntasks=32
#SBATCH --job-name=compgen_benchmark_mpi
#SBATCH --output=benchmark_JOB_%j.out
#SBATCH --error=benchmark_JOB_%j.err
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

# Run the benchmark script
# This will test MPI scaling with 1, 2, 8, and 32 ranks
python benchmark_parallel.py