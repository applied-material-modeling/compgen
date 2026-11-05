# 2D fracture demo

## Dependencies

- Conda environment: `/project/ai4ns_composites/fracture_code/conda_envs/raccoon`.
- Compiled RACCOON executable: `/project/ai4ns_composites/fracture_code/raccoon/raccoon-opt`.
- Compiled MOOSE: already included by the RACCOON build; not required separately at runtime.

## Paths to inspect or change after pulling

Information provided like this: 
- `Filename`
    - `Variable`:`recommendation`

- `config_machine.json`:
    - `racoon/executable`: `/project/ai4ns_composites/fracture_code/raccoon/raccoon-opt`.
    - `storage` and `log_file` are selected per case in `config_case1.json` or `config_case2.json`.
- `config_case1.json` and `config_case2.json`:
    - Store the independent material/interface parameter sets.
    - Store separate output, log, and temporary paths under `simulations/case1` or `simulations/case2`.
- `run_fracture_predefined_local.sh`: 
    - `RACCOON_DIR`: defaults to `/project/ai4ns_composites/fracture_code/raccoon`; override it for another checkout.
    - Change `which_case` at the top to `case1` or `case2` before each run.
- `plotting/plot_material_structure.py`: 
    - `H5_FILE`: set this to the result `.h5` file to plot.
- `plotting/plot_results.py`: 
    - `GRID_SIZES` and `FPS`: optionally change plot resolution and animation speed.

## Run

From this directory, run:

```bash
./run_fracture_predefined_local.sh
```

The launcher does not take a case argument. Edit `which_case` in the shell
script, run it, wait for that case to finish, then change `which_case` and run
again. Case 1 and Case 2 write to separate directories:

```text
simulations/case1/{output,logs,tmp}
simulations/case2/{output,logs,tmp}
```

## Plot

After a successful run, from this directory:

```bash
python plotting/plot_results.py
python plotting/plot_material_structure.py
```

## Access to grant on this machine

- `/project/ai4ns_composites/fracture_code/conda_envs/raccoon`: Conda environment.
- `/project/ai4ns_composites/fracture_code/raccoon`: compiled RACCOON checkout.

The launcher does not require a pre-generated `ADRealMonolithic.h`. If the
RACCOON input invokes MOOSE's runtime FParser JIT, `compgen/racoon.py`
configures the compiler and library paths from `CONDA_PREFIX`; otherwise no
JIT compilation is performed.