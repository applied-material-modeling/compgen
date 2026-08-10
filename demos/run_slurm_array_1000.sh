#!/bin/bash

# Submit from the demos directory with:
#   sbatch run_slurm_array_1000.sh
#
# Fifty array elements process twenty simulations each, for exactly 1000
# simulations total. Each array element reserves one whole node and runs at
# most eight simulations concurrently. Each simulation uses six MPI ranks.

#SBATCH --time=10:00:00
# Allow two one-node array elements to run concurrently. Increase the value
# after % only if the HPC system can support more simultaneous nodes.
#SBATCH --array=0-49%10
#SBATCH --nodes=1
#SBATCH --ntasks=48
#SBATCH --ntasks-per-node=48
#SBATCH --cpus-per-task=1
#SBATCH --hint=nomultithread
#SBATCH --exclusive
#SBATCH --mem=0
#SBATCH --job-name=compgen_array_1000
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

export COMPGEN_RUNS_PER_TASK=20
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
