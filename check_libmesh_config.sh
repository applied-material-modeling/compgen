#!/bin/bash
# Check libMesh JIT configuration

echo "=== Checking libMesh configuration ==="

# Activate environment
source ~/miniconda3/etc/profile.d/conda.sh
conda activate racoon
module load cray-mpich

# Run RACCOON with --help to see if there are config flags
echo -e "\n=== Checking for libMesh config options ==="
/users/rghill/racoon/raccoon/raccoon-opt --help | grep -i "jit\|compiler\|libmesh" || echo "No JIT/compiler options in --help"

# Check if RACCOON has a way to print libMesh configuration
echo -e "\n=== Trying to print libMesh build info ==="
/users/rghill/racoon/raccoon/raccoon-opt --version 2>&1 | head -20

# Check what libMesh libraries RACCOON is linked against
echo -e "\n=== Libraries linked to RACCOON ==="
ldd /users/rghill/racoon/raccoon/raccoon-opt | grep -i "libmesh\|moose"

# Check if there's a libMesh config file
echo -e "\n=== Checking for libMesh config files ==="
find ~/racoon -name "*.conf" -o -name "libmesh_config.h" 2>/dev/null | head -5

# Try to find where libMesh was built and check its config
echo -e "\n=== Looking for libMesh build directory ==="
find ~/racoon -type d -name "libmesh" 2>/dev/null | head -3

# Check if there are any environment variables libMesh might be reading
echo -e "\n=== Current compiler-related environment ==="
env | grep -E "CXX|COMPILER|CC=" | sort
