# Next Steps - Wrapper Script Solution

## Problem Summary
Environment variables (`LIBMESH_CXX`, `LIBMESH_CXXFLAGS`) are not reaching the JIT compiler through the subprocess chain (bash → Python → srun → RACCOON).

## Solution: Use a Wrapper Script

A wrapper script that sets the environment variables and then calls RACCOON is the most reliable solution.

## Setup Steps (on HPC)

### 1. Create the wrapper script

```bash
cd /lustre/roscratch1/rghill/AlSiC_2/compgen

# Create bin directory if it doesn't exist
mkdir -p ~/bin

# Copy and install the wrapper
cp raccoon-wrapper.sh ~/bin/raccoon-wrapped
chmod +x ~/bin/raccoon-wrapped
```

### 2. Update the config to use the wrapper

Edit `demos/machine_config_slurm.json` and change the RACCOON executable:

```json
"racoon": {
    "executable": "/users/rghill/bin/raccoon-wrapped",
    "options": [],
    "environment": {
        "FI_PROVIDER": "tcp"
    }
},
```

### 3. Test the wrapper manually

```bash
cd /lustre/roscratch1/rghill/AlSiC_2/compgen
source ~/miniconda3/etc/profile.d/conda.sh
conda activate racoon
module load cray-mpich

# Create minimal test input
cat > test_minimal.i << 'EOF'
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
    expression = 'x*x'
    coupled_variables = 'u'
  []
[]

[Problem]
  solve = false
[]

[Executioner]
  type = Steady
[]
EOF

# Test the wrapper
~/bin/raccoon-wrapped -i test_minimal.i
```

**Expected:** Should run without `cmath not found` error. You'll see the wrapper's debug output showing the JIT configuration.

### 4. Submit the full job

```bash
cd /lustre/roscratch1/rghill/AlSiC_2/compgen/demos
sbatch run_slurm_32rankDB
```

## Why This Works

The wrapper script:
1. Runs as the RACCOON executable
2. Sets environment variables **in its own process**
3. Uses `exec` to replace itself with the real RACCOON
4. RACCOON inherits the environment directly from the wrapper
5. No subprocess chain to lose variables

This is more reliable than trying to pass variables through Python → srun → RACCOON.

## Monitoring

```bash
# Check job status
squeue -u rghill

# Watch for the wrapper's debug output
tail -f JOB_*.out

# Watch for JIT errors
tail -f JOB_*.err | grep -i "cmath\|jit"
```

If you see:
```
[RACCOON Wrapper] LIBMESH_CXX=/users/rghill/miniconda3/envs/racoon/bin/g++
[RACCOON Wrapper] LIBMESH_CXXFLAGS=...
```

Then the wrapper is working and the variables are set.

## Files Changed/Created

### New files:
- `raccoon-wrapper.sh` - Wrapper script (install to `~/bin/raccoon-wrapped`)
- `TEST_STEPS.md` - Debugging guide
- `test_env_in_python.py` - Python environment test

### To modify:
- `demos/machine_config_slurm.json` - Change executable to wrapper

### Already updated (from previous attempts):
- `compgen/racoon.py` - Has Python-based env injection (backup)
- `compgen/moose.py` - Has Python-based env injection (backup)
- `demos/run_slurm_32rankDB` - Has bash exports (backup)
