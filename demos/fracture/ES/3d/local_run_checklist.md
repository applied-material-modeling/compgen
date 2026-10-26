# Local predefined fracture run

This is the non-Slurm equivalent of the Aurora predefined fracture run.

## Run

From the repository root:

```bash
./demos/fracture/ES/3d/run_fracture_predefined_local.sh
```

Or, after activating the environment manually, from any directory:

```bash
conda activate moose_genesis
python demos/fracture/ES/3d/run_fracture_predefined_local.py
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

The launcher automatically adds `$HOME/code/raccoon` to `PATH` when it finds
`raccoon-opt` there. For a different RACCOON checkout, set `RACCOON_DIR`
before running. The MOOSE `solid_mechanics-opt` executable must already be
built and available on `PATH`.

RACCOON also needs its matching MOOSE JIT header. The launcher automatically
uses `$RACCOON_DIR/ADRealMonolithic.h` when present; otherwise set
`MOOSE_ADFPARSER_JIT_INCLUDE` to an existing header before running:

```bash
test -f "$MOOSE_ADFPARSER_JIT_INCLUDE"
```

Generate the header using the MOOSE/RACCOON build instructions for your
environment if it is missing. The launcher intentionally does not assume a
machine-specific checkout location.