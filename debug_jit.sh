#!/bin/bash
# Debug script to check JIT compiler configuration
# Run this on the HPC system to diagnose the issue

echo "=== Conda Environment ==="
echo "CONDA_PREFIX: $CONDA_PREFIX"
echo ""

echo "=== Checking for C++ compiler ==="
which g++
which c++
which clang++
echo ""

echo "=== Checking C++ standard library locations ==="
find $CONDA_PREFIX -name "cmath" -o -name "iostream" 2>/dev/null | head -10
echo ""

echo "=== Current compiler flags ==="
echo "CPLUS_INCLUDE_PATH: $CPLUS_INCLUDE_PATH"
echo "CXXFLAGS: $CXXFLAGS"
echo "LIBRARY_PATH: $LIBRARY_PATH"
echo ""

echo "=== libMesh JIT environment variables ==="
echo "LIBMESH_CXX: $LIBMESH_CXX"
echo "LIBMESH_CXXFLAGS: $LIBMESH_CXXFLAGS"
echo ""

echo "=== Testing simple C++ compilation ==="
cat > /tmp/test_jit.cpp << 'EOF'
#include <cmath>
#include <iostream>
int main() { std::cout << std::sqrt(2.0) << std::endl; return 0; }
EOF

echo "Using default g++:"
g++ -v /tmp/test_jit.cpp -o /tmp/test_jit 2>&1 | tail -20
