# Local predefined fracture run

This is the non-Slurm equivalent of the Aurora predefined fracture run.

## Run

From any directory:

```bash
/home/bbrunsvik/projects/ai4ns/compgen/demos/3D_ES/run_fracture_predefined_local.sh
```

Or, after activating the environment manually:

```bash
conda activate moose_genesis
cd /home/bbrunsvik/projects/ai4ns/compgen/demos/3D_ES
python run_fracture_predefined_local.py
```

## Local changes from Aurora

- No PBS, `pbsdsh`, Slurm, or modules are used.
- The run uses the configured local Python worker count (`nthreads`).
- Each RACCOON invocation uses local `mpirun` with the configured rank count.
- Temporary JIT files are kept under the configured executable filesystem path.
- Simulation results are written under the configured output directory.
- SCULPT is disabled because this computer does not currently have a confirmed SCULPT executable at the supplied paths.

## Before running

Verify the MOOSE executable configured in `local_machine_config.json` exists:

```bash
test -x /home/bbrunsvik/code/MOOSE_genesis/moose/modules/solid_mechanics/solid_mechanics-opt
test -x /home/bbrunsvik/code/raccoon/raccoon-opt
command -v mpirun
```

RACCOON also needs its matching MOOSE JIT header. The launcher checks that
`MOOSE_ADFPARSER_JIT_INCLUDE` points to an existing `ADRealMonolithic.h` file.
The local launcher defaults this variable to the header generated in the
embedded RACCOON/MOOSE tree:

```bash
test -f /home/bbrunsvik/code/raccoon/ADRealMonolithic.h
```

If it is missing, generate it from that same tree (not from `MOOSE_genesis`):

```bash
conda activate moose_genesis
cd /home/bbrunsvik/code/raccoon
make ADRealMonolithic.h
```

If the MOOSE build is located elsewhere inside `MOOSE_genesis`, update only the `moose.executable` value in `local_machine_config.json`.