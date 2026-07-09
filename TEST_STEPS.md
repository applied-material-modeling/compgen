# Debug Steps for JIT Issue

The environment variables still aren't reaching the JIT compiler. Let's diagnose systematically.

## Step 1: Test Python environment access

```bash
cd /lustre/roscratch1/rghill/AlSiC_2/compgen
source ~/miniconda3/etc/profile.d/conda.sh
conda activate racoon
module load cray-mpich

# Export the variables in the shell
export LIBMESH_CXX="${CONDA_PREFIX}/bin/g++"
GCC_VERSION=$(${CONDA_PREFIX}/bin/g++ -dumpversion)
CXX_INCLUDE_DIR="${CONDA_PREFIX}/lib/gcc/x86_64-conda-linux-gnu/${GCC_VERSION}/include/c++"
export LIBMESH_CXXFLAGS="-I${CXX_INCLUDE_DIR} -I${CONDA_PREFIX}/x86_64-conda-linux-gnu/sysroot/usr/include -L${CONDA_PREFIX}/lib -Wl,-rpath,${CONDA_PREFIX}/lib"

# Test Python can see them
python test_env_in_python.py
```

**Expected output:** Should show CONDA_PREFIX, LIBMESH_CXX, and LIBMESH_CXXFLAGS

## Step 2: Test srun passes them

```bash
# Still in same shell with variables exported
srun -n 1 --export=ALL,LIBMESH_CXX,LIBMESH_CXXFLAGS bash -c 'echo "LIBMESH_CXX=$LIBMESH_CXX"'
```

**Expected:** Should print the g++ path

## Step 3: Test minimal RACCOON with JIT

Create a minimal test input file `test_jit.i`:
```
[Mesh]
  type = GeneratedMesh
  dim = 2
  nx = 2
  ny = 2
[]

[Variables]
  [u]
  []
[]

[Materials]
  [test]
    type = ADDerivativeParsedMaterial
    property_name = test_prop
    expression = 'x*x + y*y'
    coupled_variables = 'u'
  []
[]

[Problem]
  solve = false
[]

[Executioner]
  type = Steady
[]
```

Then run:
```bash
srun -n 1 --export=ALL,LIBMESH_CXX,LIBMESH_CXXFLAGS /users/rghill/racoon/raccoon/raccoon-opt -i test_jit.i
```

**Expected:** Should run without "cmath not found" error

## Step 4: Check what Python actually sets

Modify the job submission temporarily. In `demos/`, create `test_runner.py`:
```python
import os
import sys
sys.path.insert(0, '..')

# Print environment before loading compgen
print("=== Environment at Python start ===")
print(f"CONDA_PREFIX: {os.environ.get('CONDA_PREFIX', 'NOT SET')}")
print(f"LIBMESH_CXX: {os.environ.get('LIBMESH_CXX', 'NOT SET')}")

# Now simulate what compgen does
if 'CONDA_PREFIX' in os.environ:
    conda_prefix = os.environ['CONDA_PREFIX']
    os.environ['LIBMESH_CXX'] = f"{conda_prefix}/bin/g++"
    print(f"\n=== After manual setting ===")
    print(f"LIBMESH_CXX: {os.environ['LIBMESH_CXX']}")
```

Run with: `python test_runner.py`

## Step 5: Check if the issue is subprocess.run()

The problem might be that even though we set `run_env`, subprocess.run() might not be using it correctly with srun. Let's verify by adding a debug command before the actual RACCOON call.

## Alternative: Create a wrapper script

If environment variables aren't working, create `/users/rghill/bin/raccoon-wrapped`:
```bash
#!/bin/bash
export LIBMESH_CXX="/users/rghill/miniconda3/envs/racoon/bin/g++"
export LIBMESH_CXXFLAGS="-I/users/rghill/miniconda3/envs/racoon/lib/gcc/x86_64-conda-linux-gnu/14.3.0/include/c++ -I/users/rghill/miniconda3/envs/racoon/x86_64-conda-linux-gnu/sysroot/usr/include -L/users/rghill/miniconda3/envs/racoon/lib -Wl,-rpath,/users/rghill/miniconda3/envs/racoon/lib"
exec /users/rghill/racoon/raccoon/raccoon-opt "$@"
```

Make it executable: `chmod +x /users/rghill/bin/raccoon-wrapped`

Then update `machine_config_slurm.json` to use this wrapper:
```json
"executable": "/users/rghill/bin/raccoon-wrapped"
```
