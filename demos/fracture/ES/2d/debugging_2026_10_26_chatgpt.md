# This approximately describes how to run the code after finishing getting it running on ES server, moved from Aurora. 

# Local predefined fracture run

This is the non-Slurm equivalent of the Aurora predefined fracture run.

## Run

From the repository root:

```bash
./demos/fracture/ES/2d/run_fracture_predefined_local.sh
```

## Local changes from Aurora

- No PBS, `pbsdsh`, Slurm, or modules are used.
- The run uses the configured local Python worker count (`nthreads`).
- Each RACCOON invocation uses local `mpirun` with the configured rank count.
- Temporary JIT files are kept under the configured executable filesystem path.
- Simulation results are written under the configured output directory.
- SCULPT is disabled because this computer does not currently have a confirmed SCULPT executable at the supplied paths.

## Before running

Verify the configured executables are available on `PATH`:

```bash
command -v solid_mechanics-opt
command -v raccoon-opt
command -v mpirun
```

The launcher automatically activates
`/project/ai4ns_composites/fracture_code/conda_envs/raccoon` and adds
`/project/ai4ns_composites/fracture_code/raccoon` to `PATH`. For a different
installation, set `RACCOON_ENV_PREFIX` and `RACCOON_DIR` before running.

The launcher does not require a pre-generated `ADRealMonolithic.h`. The
CompGen RACCOON executor configures the matching conda compiler and library
paths automatically if MOOSE's runtime JIT is requested by the input.