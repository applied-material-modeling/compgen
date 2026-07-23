#!/bin/bash

# Submit from the demos directory with: sbatch run_slurm_array_36.sh

#SBATCH --time=08:00:00
# Two array elements reserve one whole node each. Each element processes 18
# simulations with at most 8 running concurrently, for 36 simulations total.
#SBATCH --array=0-1%2
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --ntasks-per-node=48
#SBATCH --cpus-per-task=1
#SBATCH --hint=nomultithread
#SBATCH --exclusive
#SBATCH --mem=0
#SBATCH --job-name=compgen_array
#SBATCH --output=JOB_%A_%a.out
#SBATCH --error=JOB_%A_%a.err

set -e
set -o pipefail

source ~/miniconda3/etc/profile.d/conda.sh
conda activate racoon

# Prevent threaded numerical libraries from creating extra threads in each
# Python worker or MPI rank.
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

export COMPGEN_RUNS_PER_TASK=18
export COMPGEN_THREADS_PER_TASK=8

export PATH="$HOME/.local/compiler-wrappers:$PATH"
export LIBMESH_CXX="${CONDA_PREFIX}/bin/g++"

GCC_VERSION=$("${CONDA_PREFIX}/bin/g++" -dumpversion)
CXX_INCLUDE_DIR="${CONDA_PREFIX}/lib/gcc/x86_64-conda-linux-gnu/${GCC_VERSION}/include/c++"

export LIBMESH_CXXFLAGS="-I${CXX_INCLUDE_DIR} -I${CONDA_PREFIX}/x86_64-conda-linux-gnu/sysroot/usr/include -L${CONDA_PREFIX}/lib -Wl,-rpath,${CONDA_PREFIX}/lib"

cd "${SLURM_SUBMIT_DIR}"

echo "Array job ${SLURM_ARRAY_JOB_ID}, task ${SLURM_ARRAY_TASK_ID}"
echo "Allocated node: ${SLURMD_NODENAME}"

python -u run_fracture_predefined_slurm_array.py
