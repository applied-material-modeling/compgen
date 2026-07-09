#!/bin/bash
# Run this on the HPC system to find the right compiler configuration
# Usage: bash check_hpc_compiler.sh

echo "=== Step 1: Activate environment ==="
source ~/miniconda3/etc/profile.d/conda.sh
conda activate racoon
module load cray-mpich

echo ""
echo "=== Step 2: Check available compilers ==="
for compiler in cc CC gcc g++ c++ clang++ icpc; do
    if which $compiler 2>/dev/null; then
        echo "Found: $compiler at $(which $compiler)"
        $compiler --version 2>&1 | head -2
        echo ""
    fi
done

echo "=== Step 3: Test C++ standard library with each compiler ==="
cat > /tmp/test_cmath.cpp << 'EOF'
#include <cmath>
#include <iostream>
int main() {
    std::cout << "sqrt(2) = " << std::sqrt(2.0) << std::endl;
    return 0;
}
EOF

for compiler in CC g++ c++ "${CONDA_PREFIX}/bin/g++" "${CONDA_PREFIX}/bin/c++"; do
    if [ -x "$(command -v $compiler)" ]; then
        echo "--- Testing $compiler ---"
        $compiler /tmp/test_cmath.cpp -o /tmp/test_cmath 2>&1
        if [ $? -eq 0 ]; then
            echo "✓ Compilation successful!"
            /tmp/test_cmath
            rm /tmp/test_cmath
        else
            echo "✗ Compilation failed"
        fi
        echo ""
    fi
done

echo "=== Step 4: Check where C++ headers are located ==="
for search_path in "${CONDA_PREFIX}" "/opt/cray" "/usr"; do
    echo "Searching in $search_path:"
    find "$search_path" -name "cmath" -type f 2>/dev/null | head -3
done

echo ""
echo "=== Step 5: Check RACCOON build info ==="
if [ -f ~/raccoon/raccoon-opt ]; then
    echo "RACCOON executable found"
    strings ~/raccoon/raccoon-opt | grep -i "gcc\|clang\|cray" | head -10
fi

echo ""
echo "=== Recommendation ==="
echo "Use the compiler that successfully compiled test_cmath.cpp"
echo "Set LIBMESH_CXX to that compiler path"
