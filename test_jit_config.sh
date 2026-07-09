#!/bin/bash
# Quick test to verify JIT configuration before running full simulation
# Run this on HPC: bash test_jit_config.sh

echo "=== Setting up environment ==="
source ~/miniconda3/etc/profile.d/conda.sh
conda activate racoon
module load cray-mpich

# Apply the same JIT configuration as run_slurm_32rankDB
export LIBMESH_CXX="${CONDA_PREFIX}/bin/g++"
GCC_VERSION=$(${CONDA_PREFIX}/bin/g++ -dumpversion)
CXX_INCLUDE_DIR="${CONDA_PREFIX}/lib/gcc/x86_64-conda-linux-gnu/${GCC_VERSION}/include/c++"
export LIBMESH_CXXFLAGS="-I${CXX_INCLUDE_DIR} -I${CONDA_PREFIX}/x86_64-conda-linux-gnu/sysroot/usr/include -L${CONDA_PREFIX}/lib -Wl,-rpath,${CONDA_PREFIX}/lib"

echo ""
echo "=== JIT Configuration ==="
echo "LIBMESH_CXX: $LIBMESH_CXX"
echo "GCC_VERSION: $GCC_VERSION"
echo "CXX_INCLUDE_DIR: $CXX_INCLUDE_DIR"
echo ""

echo "=== Verifying compiler exists ==="
if [ -x "$LIBMESH_CXX" ]; then
    echo "✓ Compiler found: $LIBMESH_CXX"
    $LIBMESH_CXX --version | head -1
else
    echo "✗ ERROR: Compiler not found at $LIBMESH_CXX"
    exit 1
fi
echo ""

echo "=== Verifying C++ headers exist ==="
if [ -f "${CXX_INCLUDE_DIR}/cmath" ]; then
    echo "✓ Found cmath header: ${CXX_INCLUDE_DIR}/cmath"
else
    echo "✗ ERROR: cmath header not found at ${CXX_INCLUDE_DIR}/cmath"
    echo "Searching for cmath..."
    find ${CONDA_PREFIX}/lib/gcc -name "cmath" 2>/dev/null
    exit 1
fi
echo ""

echo "=== Testing JIT compilation manually ==="
cat > /tmp/test_jit_libmesh.cpp << 'EOF'
#include <cmath>
#include <iostream>
int main() {
    double x = std::sqrt(2.0);
    std::cout << "JIT test successful: sqrt(2) = " << x << std::endl;
    return 0;
}
EOF

eval "$LIBMESH_CXX $LIBMESH_CXXFLAGS /tmp/test_jit_libmesh.cpp -o /tmp/test_jit_libmesh"
if [ $? -eq 0 ]; then
    echo "✓ JIT compilation successful!"
    /tmp/test_jit_libmesh
    rm /tmp/test_jit_libmesh /tmp/test_jit_libmesh.cpp
else
    echo "✗ JIT compilation failed"
    echo "This means the configuration is still wrong."
    exit 1
fi

echo ""
echo "=== SUCCESS ==="
echo "JIT configuration is correct. You can now submit your job."
echo "The run_slurm_32rankDB script should work."
