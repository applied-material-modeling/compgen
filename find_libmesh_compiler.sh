#!/bin/bash
# Find the compiler that libMesh was built with

echo "=== Searching for libMesh configuration ==="

# Activate environment
source ~/miniconda3/etc/profile.d/conda.sh
conda activate racoon

# Check the installed libMesh for config
echo -e "\n=== libmesh-config (if it exists) ==="
if [ -f ~/miniconda3/envs/racoon/libmesh/bin/libmesh-config ]; then
    ~/miniconda3/envs/racoon/libmesh/bin/libmesh-config --cxx
    ~/miniconda3/envs/racoon/libmesh/bin/libmesh-config --cxxflags
else
    echo "libmesh-config not found"
fi

# Check for Make.common which contains compiler settings
echo -e "\n=== Searching for Make.common ==="
find ~/racoon/raccoon/moose/libmesh -name "Make.common" 2>/dev/null | head -3

# Check for libmesh_config.h header
echo -e "\n=== Searching for libmesh_config.h ==="
find ~/miniconda3/envs/racoon/libmesh -name "libmesh_config.h" 2>/dev/null | head -3

# If found, check what CXX is set to
LIBMESH_CONFIG=$(find ~/miniconda3/envs/racoon/libmesh -name "libmesh_config.h" 2>/dev/null | head -1)
if [ -n "$LIBMESH_CONFIG" ]; then
    echo -e "\n=== CXX settings in libmesh_config.h ==="
    grep -E "LIBMESH_CXX|CXX_VERSION" "$LIBMESH_CONFIG" | head -10
fi

# Check MOOSE's libmesh build
echo -e "\n=== Checking MOOSE's libmesh build directory ==="
if [ -d ~/racoon/raccoon/moose/libmesh ]; then
    MAKE_COMMON="$(find ~/racoon/raccoon/moose/libmesh -name "Make.common" 2>/dev/null | head -1)"
    if [ -n "$MAKE_COMMON" ]; then
        echo "Found Make.common at: $MAKE_COMMON"
        echo -e "\n=== Compiler settings in Make.common ==="
        grep -E "^CXX|^libmesh_CXX" "$MAKE_COMMON" | head -10
    fi
fi

# Check include directory for built libMesh
echo -e "\n=== Checking libMesh include directory ==="
if [ -d ~/miniconda3/envs/racoon/libmesh/include ]; then
    find ~/miniconda3/envs/racoon/libmesh/include -name "libmesh_config.h" -exec grep -H "LIBMESH_CXX\|CXX.*=" {} \; 2>/dev/null | head -20
fi
