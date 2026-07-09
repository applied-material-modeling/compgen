# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`compgen` is a Python toolkit for generating simulation data for two-phase composite materials. It generates microstructures, invokes physics codes (MOOSE/RACCOON) to simulate material response, and writes results to HDF5 format.

### Pipeline Architecture

The core workflow (`compgen.runner.run()`) chains five steps:

1. **Structure Generation** (`compgen/gen.py`): Generate composite microstructures as pixelated grids
   - `SpinodalGenerator`: Spinodal decomposition patterns
   - `TwoPointGenerator`: Two-point correlation functions
   - `RandomGenerator`: Random distributions
   - `FromNumpyGenerator`: Load pre-existing structures

2. **Filtering** (`compgen/filters.py`): Optional post-processing (smoothing, orthogonalization)

3. **Mesh Generation** (`compgen/mesh.py`): Convert pixelated structures to finite element meshes
   - 2D: `generate_mesh_2d()` - quad meshes via SCULPT or direct ExodusII
   - 3D: `generate_mesh_3d()` - hex meshes via SCULPT

4. **Physics Simulation**: Execute MOOSE/RACCOON finite element analysis
   - MOOSE executor: `compgen/moose.py`
   - RACCOON executor: `compgen/racoon.py` (for fracture mechanics)
   - Template files: `compgen/physics/{2d,3d}/{elastic,plastic,thermal_conductivity,thermal_expansion,fracture}/template.i`

5. **Post-processing** (`compgen/hdfwriter.py`): Extract results and write to HDF5

### Configuration System

Simulations are defined by JSON config files (see `demos/` for examples):

- **Problem file**: Defines generator, materials, mesh, physics type
- **Machine config**: Paths to executables (SCULPT, MOOSE, RACCOON, MPI)
- **Parallel config**: Thread/rank settings for parallel execution

The `runner.run()` function accepts multiple config files that get merged via `utils.load_json()`.

### Material Properties

Materials are defined via `compgen/materials.py`:
- `FixedMaterialGenerator`: Fixed properties (elastic moduli, density, fracture toughness, etc.)
- `RandomMaterialGenerator`: Sample properties from distributions

For fracture simulations, three materials are required:
- `material_A`: Matrix material
- `material_B`: Reinforcement material  
- `material_AB`: Interface properties (critical energy release rates, strengths)

## Development Commands

### Running Tests
```bash
# Update test configuration first
vim tests/verification/test_config.json  # Set paths to MOOSE/RACCOON/SCULPT

# Run all tests
pytest

# Run specific test
pytest tests/verification/2d/test_elastic.py
```

### Running Demos

```bash
# Basic 2D demo structure:
cd demos/complete/elasticity/2d
python demo.py  # Calls runner.run() with multiple configs

# Fracture simulations (current work)
cd demos
python run_fracture_predefined.py
```

### Slurm Execution

For HPC clusters (e.g., LANL systems):
```bash
# Submit batch job
sbatch demos/run_slurm_32rankDB

# The Slurm script:
# 1. Activates conda environment (racoon)
# 2. Loads cray-mpich module (overrides conda MPI)
# 3. Runs Python script with multiprocess parallelism
```

Key pattern: `multiprocess` library maps parallel jobs over `srun --exclusive --exact` for efficient cluster utilization.

## Working with Physics Templates

Physics templates are MOOSE input files (`.i` format) with placeholders:
- `{{youngs_modulus_A}}`, `{{youngs_modulus_B}}`: Material properties
- `{{Gc_A}}`, `{{Gc_B}}`: Fracture energy (RACCOON)
- `{{GI_c}}`, `{{GII_c}}`: Interface fracture properties

The executor substitutes values via `material_property_substitutions()`, then runs the solver.

## Key Files by Function

- **Entry point**: `compgen/runner.py` - Main orchestration logic
- **Structure generation**: `compgen/gen.py` - All microstructure generators
- **Meshing**: `compgen/mesh.py` - ExodusII mesh generation and SCULPT integration
- **Physics executors**: 
  - `compgen/moose.py` - General MOOSE simulations
  - `compgen/racoon.py` - Fracture mechanics with RACCOON
- **Utilities**:
  - `compgen/exoutil.py` - ExodusII file manipulation
  - `compgen/temp.py` - Temporary directory management
  - `compgen/utils.py` - JSON config loading

## Current Branch Context

Branch `comp_racoon_rocinante` is focused on fracture mechanics:
- Modified `compgen/physics/2d/fracture/fracture.i` - Phase field fracture model
- Working on parallel execution of predefined spinodal structures
- Uses RACCOON for phase field fracture (requires BreakMeshByBlockGenerator for interfaces)

## Dependencies

Install via: `pip install -r requirements.txt`

Key external dependencies:
- **MOOSE**: Multiphysics finite element framework
- **RACCOON**: Phase field fracture code (MOOSE-based)
- **SCULPT**: Mesh generation tool from Sandia
- **MPI**: Parallel execution (use system MPI, not conda's)

Installation notes in `racoon_moose_install_instructions.txt`.

## Common HPC Issues

**JIT Compilation Errors on Cray Systems**

If you see `fatal error: 'cmath' file not found` or `AD parsed objects require JIT compilation`:
- This happens when module swaps (openmpi → cray-mpich) break the C++ compiler environment
- The JIT compiler in libMesh (used by MOOSE/RACCOON) can't find C++ standard headers

**Solution (IMPLEMENTED)**: The executors (`compgen/racoon.py`, `compgen/moose.py`) now **automatically detect conda environments** and inject JIT configuration:
- Sets `LIBMESH_CXX` to conda's g++ compiler
- Dynamically determines GCC version and configures `LIBMESH_CXXFLAGS` with proper include paths
- This happens directly in Python before calling RACCOON/MOOSE, ensuring the variables are always present

**Why this was necessary**: After `module load cray-mpich`, the default C++ compiler becomes Cray's `CC`, which can't find conda's C++ headers. The solution forces libMesh to use conda's `g++` which has the correct paths.

**Debugging**: If issues persist, see `fix_raccoon_jit.md` and run `check_hpc_compiler.sh` to verify compiler availability.

**Important**: You cannot use `enable_jit = false` with AD materials (`CrackGeometricFunction`, `RationalDegradationFunction`, `ADDerivativeParsedMaterial`) - they require JIT.
