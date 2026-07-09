#!/bin/bash
# Test that srun passes environment variables correctly
# Run this on HPC: bash test_srun_env.sh

echo "=== Setting up environment ==="
source ~/miniconda3/etc/profile.d/conda.sh
conda activate racoon
module load cray-mpich

# Apply the same JIT configuration
export LIBMESH_CXX="${CONDA_PREFIX}/bin/g++"
GCC_VERSION=$(${CONDA_PREFIX}/bin/g++ -dumpversion)
CXX_INCLUDE_DIR="${CONDA_PREFIX}/lib/gcc/x86_64-conda-linux-gnu/${GCC_VERSION}/include/c++"
export LIBMESH_CXXFLAGS="-I${CXX_INCLUDE_DIR} -I${CONDA_PREFIX}/x86_64-conda-linux-gnu/sysroot/usr/include -L${CONDA_PREFIX}/lib -Wl,-rpath,${CONDA_PREFIX}/lib"

echo ""
echo "=== Environment in parent shell ==="
echo "LIBMESH_CXX: $LIBMESH_CXX"
echo "LIBMESH_CXXFLAGS: $LIBMESH_CXXFLAGS"

echo ""
echo "=== Testing srun without --export=ALL ==="
srun -n 1 bash -c 'echo "LIBMESH_CXX in srun: $LIBMESH_CXX"'

echo ""
echo "=== Testing srun WITH --export=ALL ==="
srun -n 1 --export=ALL bash -c 'echo "LIBMESH_CXX in srun: $LIBMESH_CXX"'

echo ""
if [ -z "$(srun -n 1 --export=ALL bash -c 'echo $LIBMESH_CXX')" ]; then
    echo "✗ ERROR: Environment variables not passed with --export=ALL"
else
    echo "✓ SUCCESS: Environment variables are passed with --export=ALL"
fi
