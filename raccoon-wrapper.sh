#!/bin/bash
# Wrapper script for RACCOON that ensures JIT compiler is configured
# This guarantees the environment variables reach libMesh's JIT system
#
# Installation:
#   cp raccoon-wrapper.sh /users/rghill/bin/raccoon-wrapped
#   chmod +x /users/rghill/bin/raccoon-wrapped
#
# Then update machine_config_slurm.json:
#   "executable": "/users/rghill/bin/raccoon-wrapped"

# Detect conda environment
if [ -z "$CONDA_PREFIX" ]; then
    echo "ERROR: CONDA_PREFIX not set. Activate conda environment first." >&2
    exit 1
fi

# Configure libMesh JIT compiler
export LIBMESH_CXX="${CONDA_PREFIX}/bin/g++"

# Get GCC version dynamically
GCC_VERSION=$("${CONDA_PREFIX}/bin/g++" -dumpversion 2>/dev/null)
if [ -z "$GCC_VERSION" ]; then
    # Fallback to known version on this system
    GCC_VERSION="14.3.0"
fi

# Set compiler flags with correct include paths
CXX_INCLUDE="${CONDA_PREFIX}/lib/gcc/x86_64-conda-linux-gnu/${GCC_VERSION}/include/c++"
export LIBMESH_CXXFLAGS="-I${CXX_INCLUDE} -I${CONDA_PREFIX}/x86_64-conda-linux-gnu/sysroot/usr/include -L${CONDA_PREFIX}/lib -Wl,-rpath,${CONDA_PREFIX}/lib"

# Debug output (remove after confirming it works)
echo "[RACCOON Wrapper] LIBMESH_CXX=${LIBMESH_CXX}" >&2
echo "[RACCOON Wrapper] LIBMESH_CXXFLAGS=${LIBMESH_CXXFLAGS}" >&2

# Execute the real RACCOON with all arguments
exec /users/rghill/racoon/raccoon/raccoon-opt "$@"
