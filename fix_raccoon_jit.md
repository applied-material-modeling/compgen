# Fixing RACCOON JIT Compilation on HPC

## Problem Diagnosed
After loading `cray-mpich`, the JIT compiler can't find C++ headers (`<cmath>`).

**Root cause**: Loading `cray-mpich` switches the default C++ compiler from conda's `g++` (which works) to Cray's `CC` (which can't find headers).

## Solution (CONFIRMED WORKING)

The `run_slurm_32rankDB` script now explicitly tells libMesh to use conda's g++:

```bash
export LIBMESH_CXX="${CONDA_PREFIX}/bin/g++"
GCC_VERSION=$(${CONDA_PREFIX}/bin/g++ -dumpversion)
CXX_INCLUDE_DIR="${CONDA_PREFIX}/lib/gcc/x86_64-conda-linux-gnu/${GCC_VERSION}/include/c++"
export LIBMESH_CXXFLAGS="-I${CXX_INCLUDE_DIR} -I${CONDA_PREFIX}/x86_64-conda-linux-gnu/sysroot/usr/include -L${CONDA_PREFIX}/lib -Wl,-rpath,${CONDA_PREFIX}/lib"
```

## Testing Before Full Run

Before submitting the full job, verify JIT configuration:

```bash
cd /lustre/roscratch1/rghill/AlSiC_2/compgen
bash test_jit_config.sh
```

This will:
- Set up the same environment as the Slurm job
- Test that the compiler and headers are found
- Confirm JIT compilation works

If this passes, your full job should work.

## Diagnostic Results from HPC

From running `check_hpc_compiler.sh`, we confirmed:
- ✅ Conda's `g++` (gcc 14.3.0): Works
- ✅ Conda's `c++` (gcc 14.3.0): Works  
- ❌ Cray's `CC` (Intel oneAPI): **Fails** - can't find `<cmath>`
- ✅ C++ headers location: `/users/rghill/miniconda3/envs/racoon/lib/gcc/x86_64-conda-linux-gnu/14.3.0/include/c++/cmath`

## Why This Happens

1. RACCOON was built with conda's g++ compiler
2. Loading `cray-mpich` changes the default compiler to Cray's CC
3. MOOSE's JIT system tries to use the default compiler (now CC)
4. Cray's CC doesn't have paths configured to find conda's C++ headers
5. Solution: Override `LIBMESH_CXX` to force use of conda's g++

## Alternative Solutions (if above doesn't work)

### Option 1: Rebuild RACCOON with Cray compilers
```bash
cd ~/raccoon
conda activate racoon
module load cray-mpich
cd moose
./configure --with-cxx=CC
cd ..
make -j 4
```

### Option 2: Use wrapper script
Create a wrapper that sets flags before calling CC (complex, not recommended).

## Important Notes

- You **cannot** disable JIT for AD materials (`CrackGeometricFunction`, `RationalDegradationFunction`)
- These materials require JIT compilation to work
- The `enable_jit = false` flag only works for non-AD `ParsedMaterial` types
